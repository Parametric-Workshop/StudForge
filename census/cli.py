"""The census client: reads the command line and calls the Census service API.

Usage, from the repo folder:
  python3 -m census import <path/to/rebrickable_csvs> [--date YYYY-MM-DD]
  python3 -m census import --download
  python3 -m census condense
  python3 -m census coverage [--out PATH]

Each command first brings what it depends on up to date, so any of them works on
a fresh clone: condense imports the manifest's snapshot if the census doesn't
hold it, and coverage also condenses again if a rule file changed.

Reads and writes:
  build/census.sqlite            the census database (local only)
  build/census_changes.log       what each condense changed (local only)
  build/census_viewer.html       the viewer page (loads its libraries from jsDelivr)
  downloads/rebrickable/<date>/  the CSVs, when downloaded, and changes.txt (local only)
  archive/census/                dated archives of each snapshot and census (local only)
  census/census-manifest.json    which snapshot the census should hold (committed)
  coverage/coverage.csv          status of each shape and decorated shape tracked
"""

import argparse
import datetime
from pathlib import Path

from census import api
from census.condensing.condense import changed_rule_files
from census.importing.snapshot import SOURCE_FILES, manifest_snapshot
from census.store.census_db import read_meta
from census.store.files import DB_PATH, MANIFEST_PATH, REPO, sha256

VIEWER_PATH = REPO / "build" / "census_viewer.html"


# --- The commands ---------------------------------------------------------------


def main() -> None:
    """Run the command named on the command line."""
    parser = argparse.ArgumentParser(
        prog="python3 -m census", description="Build and read the Rebrickable Census."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    importing = commands.add_parser(
        "import",
        help="build the census database from a Rebrickable snapshot",
        epilog="The source folder must contain:"
        + "".join(f"\n   {f}" for f in SOURCE_FILES),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    importing.add_argument(
        "source", type=Path, nargs="?", help="folder of Rebrickable CSV downloads"
    )
    importing.add_argument(
        "--download",
        action="store_true",
        help="download the latest snapshot instead (at most once a day)",
    )
    importing.add_argument(
        "--date",
        help="snapshot date (YYYY-MM-DD); defaults to when parts.csv was exported",
    )
    commands.add_parser("condense", help="turn the census's part numbers into shapes")
    covering = commands.add_parser(
        "coverage", help="work out coverage, print the summary and write the viewer"
    )
    covering.add_argument(
        "--out", type=Path, default=VIEWER_PATH, help="where to write the viewer"
    )

    args = parser.parse_args()
    if args.command == "import":
        if args.download == (args.source is not None):
            importing.error("give either a folder of Rebrickable CSVs or --download")
        api.import_snapshot(args.source, args.date)
    elif args.command == "condense":
        bring_census_up_to_date()
        api.condense()
    else:
        bring_census_up_to_date()
        check_condensed(read_meta())
        api.coverage(args.out)


# --- Application logic: what needs running first --------------------------------

# Rebrickable updates its downloads daily, but shapes change slowly, so the
# client only suggests a new download once the snapshot is this old.
OLD_SNAPSHOT_DAYS = 30


def bring_census_up_to_date() -> None:
    """Report the census's state, and rebuild it if it doesn't match the manifest.

    The condense and coverage commands call this before they read the census,
    so either one works on a fresh clone.
    """
    if not census_is_current(read_meta()):
        api.import_pinned_snapshot()
    warn_if_old(read_meta())


def census_is_current(meta: dict[str, str]) -> bool:
    """Report whether the census was built from the snapshot in the manifest.

    The manifest is committed, so after pulling a new snapshot's manifest the
    local census no longer matches it.
    """
    if not meta:
        print(f"Census: {DB_PATH.relative_to(REPO)} not found; building it")
        return False
    snapshot = meta["snapshot_date"]
    if meta.get("manifest sha256") != sha256(MANIFEST_PATH):
        print(
            f"Census: built from the {snapshot} snapshot, but {MANIFEST_PATH.name} "
            f"records the {manifest_snapshot()} snapshot; rebuilding"
        )
        return False
    age = snapshot_age(meta)
    print(
        f"Census: Rebrickable snapshot {snapshot} ({age} {days(age)} old), built "
        f"{meta['built_at']}; matches {MANIFEST_PATH.name}, no rebuild needed"
    )
    return True


def snapshot_age(meta: dict[str, str]) -> int:
    """Return how many days ago Rebrickable exported the census's snapshot."""
    exported = datetime.date.fromisoformat(meta["snapshot_date"])
    return (datetime.date.today() - exported).days


def days(count: int) -> str:
    """Return "day" or "days" to follow a count."""
    return "day" if count == 1 else "days"


def warn_if_old(meta: dict[str, str]) -> None:
    """Suggest downloading a newer snapshot once the census's is a month old."""
    age = snapshot_age(meta)
    if age > OLD_SNAPSHOT_DAYS:
        print(
            f"Census: the snapshot is {age} days old; run "
            "python3 -m census import --download for the latest"
        )


def check_condensed(meta: dict[str, str]) -> dict[str, str]:
    """Condense the census again if it never was, or a rule file changed.

    Returns the census details (the meta table), read again after condensing.
    """
    changed = changed_rule_files(meta)
    if "condensed_at" not in meta:
        reason = "not condensed yet"
    elif changed:
        reason = f"changed since {meta['condensed_at']}: {', '.join(changed)}"
    else:
        print(
            f"Condensed census: condensed {meta['condensed_at']}; "
            "rule files unchanged, no condensing needed\n"
        )
        return meta
    print(f"Condensed census: {reason}; condensing again")
    api.condense()
    print()
    return read_meta()
