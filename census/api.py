"""The Census service API: everything a client may ask of the census.

  census_state()      what the census holds now, for deciding what to run
  import_snapshot()   a Rebrickable snapshot becomes the census database
  condense()          the census's part numbers become shapes
  coverage()          statuses, the census tree, the summary and the viewer

A client imports this file and nothing else from the census. Each operation's
function is the list of its steps, in order; the work is in census/importing/,
census/condensing/ and census/coverage/. None of them decides whether it is
needed: the client (census/cli.py) reads census_state() and decides.
"""

import time
from dataclasses import dataclass
from pathlib import Path

from census.condensing import changes
from census.condensing.condense import changed_rule_files
from census.condensing.condense import condense as condense_tables
from census.coverage import statuses
from census.coverage.summary import print_summary
from census.coverage.tree import build_tree, load_groupings
from census.coverage.viewer import write_viewer
from census.importing import download, snapshot, snapshot_changes
from census.importing.archiving import archive_import
from census.store import archive, census_db
from census.store.files import (
    ARCHIVE_DIR,
    CHANGES_PATH,
    DB_PATH,
    DOWNLOAD_DIR,
    MANIFEST_PATH,
    REPO,
    sha256,
)

# The CSVs a snapshot folder must hold, for a client's help text.
SOURCE_FILES = snapshot.SOURCE_FILES
# Where coverage() writes the viewer unless the client names another place.
VIEWER_PATH = REPO / "build" / "census_viewer.html"

# --- state ------------------------------------------------------------------------


@dataclass(frozen=True)
class CensusState:
    """What the census holds now: what a client needs to decide what to run.

    Text that has no value yet is empty: snapshot_date and built_at before the
    first import, condensed_at before the first condense.
    """

    database: str  # the census database's path, from the repo folder
    manifest: str  # the manifest's file name
    snapshot_date: str  # the snapshot the census was built from
    built_at: str  # when it was imported
    pinned_snapshot: str  # the snapshot the committed manifest records
    matches_manifest: bool  # whether the census was built from that manifest
    condensed_at: str  # when it was last condensed
    changed_rule_files: list[str]  # rule files changed since then


def census_state() -> CensusState:
    """Read what the census holds now. Changes nothing."""
    meta = census_db.read_meta()
    return CensusState(
        database=str(DB_PATH.relative_to(REPO)),
        manifest=MANIFEST_PATH.name,
        snapshot_date=meta.get("snapshot_date", ""),
        built_at=meta.get("built_at", ""),
        pinned_snapshot=snapshot.manifest_snapshot(),
        matches_manifest=meta.get("manifest sha256") == sha256(MANIFEST_PATH),
        condensed_at=meta.get("condensed_at", ""),
        changed_rule_files=changed_rule_files(meta),
    )


# --- import -----------------------------------------------------------------------


def import_snapshot(
    source: Path | None = None, snapshot_date: str | None = None
) -> None:
    """Import a snapshot: a folder of Rebrickable CSVs, or the latest one downloaded.

    snapshot_date defaults to when the snapshot's parts.csv was exported.
    """
    if source is None:
        source, exported = download.download_snapshot()
        snapshot_changes.report_changes(source)
    else:
        exported = snapshot.check_snapshot_folder(source)
    build_census(source, snapshot_date or exported)


def import_pinned_snapshot() -> None:
    """Build the census from the manifest's snapshot, wherever it can be found.

    The snapshot's folder is used if it is here. If not, it is restored from the
    archive, which is first topped up from the snapshot the daily update
    published. Failing that, the latest snapshot is downloaded from Rebrickable.

    Rebrickable only offers its latest snapshot, so a download can bring a newer
    one than the manifest records; the manifest is then rewritten to match.
    """
    expected = snapshot.manifest_snapshot()
    local_copy = DOWNLOAD_DIR / expected
    if not local_copy.exists():
        download.fetch_published_snapshot(expected)
        if archive.restore_snapshot(ARCHIVE_DIR, expected, DOWNLOAD_DIR):
            print(f"Census: restored the {expected} snapshot from the archive")
    if local_copy.exists():
        print(f"Census: building from {local_copy.relative_to(REPO)}")
        snapshot.check_snapshot_folder(local_copy)
        build_census(local_copy, expected)
    else:
        print(
            f"Census: no local CSVs for the {expected} snapshot; "
            "downloading the latest instead."
        )
        folder, downloaded = download.download_snapshot()
        snapshot_changes.report_changes(folder)
        build_census(folder, downloaded)
        if downloaded != expected:
            print(
                f"Downloaded the {downloaded} snapshot; {MANIFEST_PATH.name} "
                "now differs from the committed one."
            )
    print()


def build_census(source: Path, snapshot_date: str) -> None:
    """Write the manifest for a folder of CSVs, then build the census from it."""
    snapshot.write_manifest(source, snapshot_date)

    print("Building the census database...", flush=True)
    start = time.perf_counter()
    counts = snapshot.create_census(
        source, DB_PATH, snapshot_date, sha256(MANIFEST_PATH)
    )
    seconds = time.perf_counter() - start

    print(
        f"Rebrickable Census {snapshot_date}: {len(counts)} tables, "
        f"{sum(counts.values()):,} rows, built in {seconds:.1f} s"
    )
    print(f"  database: {DB_PATH.relative_to(REPO)}")
    print(f"  manifest: {MANIFEST_PATH.relative_to(REPO)}")
    archive_import(source, snapshot_date)


# --- condense ---------------------------------------------------------------------


def condense() -> None:
    """Build the condensed census, print what it holds and log what changed."""
    db = census_db.open_census()
    previous = census_db.read_previous(db)
    shapes, candidates, assemblies, official_sets = condense_tables(db)
    sections = None
    if previous is not None:
        tracked = set(statuses.read_file(statuses.COVERAGE_PATH))
        sections = changes.compare(previous, census_db.read(db), tracked)
    db.close()
    meta = census_db.read_meta()
    print(
        f"Condensed census {meta['snapshot_date']}: {shapes:,} shapes ({candidates:,} "
        f"candidates) and {assemblies:,} assemblies, from {official_sets:,} "
        "official sets"
    )
    print(f"  database: {DB_PATH.relative_to(REPO)}")
    heading = f"Condensed {meta['condensed_at']}, snapshot {meta['snapshot_date']}"
    with open(CHANGES_PATH, "a", encoding="utf-8") as log:
        log.write("\n".join(changes.report(heading, sections)) + "\n")
    if sections is not None:
        print(f"  changes: {changes.summary(sections)}")
        print(f"  log: {CHANGES_PATH.relative_to(REPO)}")
    # The archived copy for a snapshot is the census as last condensed.
    archive.archive_census(DB_PATH, ARCHIVE_DIR, meta["snapshot_date"])


# --- coverage ---------------------------------------------------------------------


def coverage(out_path: Path = VIEWER_PATH) -> None:
    """Work out coverage, build the census tree, print the summary, write the viewer."""
    meta = census_db.read_meta()
    db = census_db.open_census()
    census = census_db.read(db)
    status_of = statuses.load(census)
    census_db.write_coverage(db, status_of)
    db.close()
    numbers = census_db.count_part_numbers(census)
    # The root card: what the condensed census made of every part number.
    title = f"Rebrickable part numbers: {numbers.total:,}"
    note = "\n".join(
        [
            f"{numbers.shapes:,} shapes",
            f"{numbers.decorated:,} decorated shapes",
            f"{numbers.assemblies:,} assemblies",
        ]
    )
    footer = f"Rebrickable snapshot {meta['snapshot_date']}"
    root = build_tree(census.shapes, title, note, footer, load_groupings())

    print_summary(root, numbers, status_of)
    write_viewer(root, status_of, out_path)
    print(f"\nViewer: {out_path}")
