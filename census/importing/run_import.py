"""The import operation, start to finish.

A folder of Rebrickable CSVs, or the latest snapshot downloaded, becomes the
census database; the manifest records which snapshot, and both are archived.
Each step's work is in its own module of this folder.
"""

import time
from dataclasses import dataclass
from pathlib import Path

from census.importing import download, snapshot, snapshot_changes
from census.importing.archiving import archive_import
from census.store import archive, census_db
from census.store.files import (
    ARCHIVE_DIR,
    DB_PATH,
    DOWNLOAD_DIR,
    MANIFEST_PATH,
    REPO,
    sha256,
)


@dataclass(frozen=True)
class ImportState:
    """Which snapshot the census holds: what a client decides from."""

    database: str  # the census database's path, from the repo folder
    manifest: str  # the manifest's file name
    snapshot_date: str  # the snapshot the census was built from; empty if no census
    built_at: str  # when it was imported; empty if no census
    pinned_snapshot: str  # the snapshot the committed manifest records
    matches_manifest: bool  # whether the census was built from that manifest


def import_state() -> ImportState:
    """Read which snapshot the census holds. Changes nothing."""
    meta = census_db.read_meta()
    return ImportState(
        database=str(DB_PATH.relative_to(REPO)),
        manifest=MANIFEST_PATH.name,
        snapshot_date=meta.get("snapshot_date", ""),
        built_at=meta.get("built_at", ""),
        pinned_snapshot=snapshot.manifest_snapshot(),
        matches_manifest=meta.get("manifest sha256") == sha256(MANIFEST_PATH),
    )


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
