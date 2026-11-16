"""The census client: reads the command line and calls the census's API.

Usage, from the repo folder:
  python3 -m census import <path/to/rebrickable_csvs> [--date YYYY-MM-DD]
  python3 -m census import --download
  python3 -m census condense
  python3 -m census coverage [--out PATH]
  python3 -m census thin-releases < tags   (used by the daily update)

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
import sys
from pathlib import Path

import census
from census import CondenseState, ImportState

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
        + "".join(f"\n   {f}" for f in census.SOURCE_FILES),
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
        "--out", type=Path, default=census.VIEWER_PATH, help="where to write the viewer"
    )

    commands.add_parser(
        "thin-releases",
        help="read release tags, one a line, and print the census ones to delete",
    )

    args = parser.parse_args()
    if args.command == "import":
        if args.download == (args.source is not None):
            importing.error("give either a folder of Rebrickable CSVs or --download")
        census.import_snapshot(args.source, args.date)
    elif args.command == "condense":
        bring_census_up_to_date()
        census.condense()
    elif args.command == "coverage":
        bring_census_up_to_date()
        check_condensed(census.condense_state())
        census.report_coverage(args.out)
    else:
        for tag in census.releases_to_drop(sys.stdin.read().split()):
            print(tag)


# --- Application logic: what needs running first --------------------------------

# Rebrickable updates its downloads daily, but shapes change slowly, so the
# client only suggests a new download once the snapshot is this old.
OLD_SNAPSHOT_DAYS = 30


def bring_census_up_to_date() -> None:
    """Report the census's state, and rebuild it if it doesn't match the manifest.

    The condense and coverage commands call this before they read the census,
    so either one works on a fresh clone.
    """
    if not census_is_current(census.import_state()):
        census.import_pinned_snapshot()
    warn_if_old(census.import_state())


def census_is_current(state: ImportState) -> bool:
    """Report whether the census was built from the snapshot in the manifest.

    The manifest is committed, so after pulling a new snapshot's manifest the
    local census no longer matches it.
    """
    if not state.snapshot_date:
        print(f"Census: {state.database} not found; building it")
        return False
    if not state.matches_manifest:
        print(
            f"Census: built from the {state.snapshot_date} snapshot, but "
            f"{state.manifest} records the {state.pinned_snapshot} snapshot; "
            "rebuilding"
        )
        return False
    age = snapshot_age(state)
    print(
        f"Census: Rebrickable snapshot {state.snapshot_date} ({age} {days(age)} "
        f"old), built {state.built_at}; matches {state.manifest}, no rebuild needed"
    )
    return True


def snapshot_age(state: ImportState) -> int:
    """Return how many days ago Rebrickable exported the census's snapshot."""
    exported = datetime.date.fromisoformat(state.snapshot_date)
    return (datetime.date.today() - exported).days


def days(count: int) -> str:
    """Return "day" or "days" to follow a count."""
    return "day" if count == 1 else "days"


def warn_if_old(state: ImportState) -> None:
    """Suggest downloading a newer snapshot once the census's is a month old."""
    age = snapshot_age(state)
    if age > OLD_SNAPSHOT_DAYS:
        print(
            f"Census: the snapshot is {age} days old; run "
            "python3 -m census import --download for the latest"
        )


def check_condensed(state: CondenseState) -> None:
    """Condense the census again if it never was, or a rule file changed."""
    if not state.condensed_at:
        reason = "not condensed yet"
    elif state.changed_rule_files:
        changed = ", ".join(state.changed_rule_files)
        reason = f"changed since {state.condensed_at}: {changed}"
    else:
        print(
            f"Condensed census: condensed {state.condensed_at}; "
            "rule files unchanged, no condensing needed\n"
        )
        return
    print(f"Condensed census: {reason}; condensing again")
    census.condense()
    print()
