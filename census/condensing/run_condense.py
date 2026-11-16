"""The condense operation, start to finish.

Builds the condensed census (condense.py), says what changed from the one
before (changes.py), logs it and archives the result.
"""

from dataclasses import dataclass

from census.condensing import changes
from census.condensing.condense import changed_rule_files
from census.condensing.condense import condense as condense_tables
from census.store import archive, census_db
from census.store.coverage_file import read_coverage_file
from census.store.files import ARCHIVE_DIR, CHANGES_PATH, DB_PATH, REPO


@dataclass(frozen=True)
class CondenseState:
    """Whether the census needs condensing: what a client decides from."""

    condensed_at: str  # when it was last condensed; empty if it never was
    changed_rule_files: list[str]  # rule files changed since then


def condense_state() -> CondenseState:
    """Read when the census was last condensed. Changes nothing."""
    meta = census_db.read_meta()
    return CondenseState(
        condensed_at=meta.get("condensed_at", ""),
        changed_rule_files=changed_rule_files(meta),
    )


def condense() -> None:
    """Build the condensed census, print what it holds and log what changed."""
    db = census_db.open_census()
    previous = census_db.read_previous(db)
    shapes, candidates, assemblies, official_sets = condense_tables(db)
    sections = None
    if previous is not None:
        tracked = set(read_coverage_file())
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
