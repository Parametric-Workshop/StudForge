"""Coverage: how far StudForge has got with each shape, decorated shape and assembly.

Statuses are recorded by hand in coverage/coverage.csv, which is committed so
that everyone sees the same coverage and changes show up in pull requests.
load() reads and checks that file, and works out the statuses that follow from
it. write_table() copies them all into the census database, as a working copy
for SQL; the file stays the source.

The rules (see GLOSSARY.md and docs/adr/0001-assemblies-are-not-shapes.md):
  - A shape has the status recorded for it, if any.
  - An assembly has the status of its least advanced shape, so it is covered
    only when all its shapes are.
  - A decorated shape has the status recorded for it, if any; otherwise it is
    "shape modeled" once the shape or assembly it folds into is modeled.
"""

import csv
import sqlite3
from pathlib import Path

from census import REPO
from condensed_census import Assembly, CondensedCensus, DecoratedShape, Shape

COVERAGE_PATH = REPO / "coverage" / "coverage.csv"

# The statuses coverage.csv can record, from least to most advanced.
STATUSES = ["planned", "modeled", "validated", "print-tested"]
# How statuses roll up. Something is covered once it is validated.
STATUS_GROUPS = {
    "in progress": ["planned", "modeled"],
    "covered": ["validated", "print-tested"],
}
MODELED_OR_LATER = {"modeled", "validated", "print-tested"}
# The status a decorated shape gets from its shape, before one of its own.
SHAPE_MODELED = "shape modeled"
DECORATED_STATUSES = [SHAPE_MODELED, *STATUSES]

# Each tracked part number's status. Untracked part numbers are absent.
Statuses = dict[str, str]


# --- Reading the coverage file ---------------------------------------------------


def read_file(path: Path) -> Statuses:
    """Return the status recorded for each part number in a coverage file."""
    with open(path, newline="", encoding="utf-8") as f:
        recorded = {r["part_num"]: r["status"] for r in csv.DictReader(f)}
    unknown = {p: s for p, s in recorded.items() if s not in STATUSES}
    if unknown:
        raise SystemExit(f"Unknown status in {path.name}: {unknown}")
    return recorded


def check_part_numbers(recorded: Statuses, census: CondensedCensus) -> None:
    """Stop if the coverage file tracks anything but candidates.

    A row is either a candidate shape or a decorated shape on one.
    """
    candidates = [s for s in census.shapes if s.excluded is None]
    trackable = {s.part_num for s in candidates}
    trackable |= {d.part_num for s in candidates for d in s.decorated}
    untracked = sorted(p for p in recorded if p not in trackable)
    if untracked:
        raise SystemExit(
            f"{COVERAGE_PATH.name} lists part numbers that aren't candidate shapes "
            "or decorated shapes on them: " + ", ".join(untracked)
        )


# --- Working out statuses --------------------------------------------------------


def assembly_status(assembly: Assembly, recorded: Statuses) -> str | None:
    """Return the status of the assembly's least advanced shape.

    None if any of its shapes has no status yet, or it lists no shapes.
    """
    member_statuses = [recorded.get(m) for m in assembly.members]
    if not member_statuses or None in member_statuses:
        return None
    return min((s for s in member_statuses if s), key=STATUSES.index)


def decorated_status(recorded: str | None, holder_status: str | None) -> str | None:
    """Return a decorated shape's status: its own, else whether its holder is modeled.

    The holder is the shape or assembly the decorated shape folds into.
    """
    if recorded is not None:
        return recorded
    return SHAPE_MODELED if holder_status in MODELED_OR_LATER else None


def load(census: CondensedCensus, path: Path = COVERAGE_PATH) -> Statuses:
    """Read and check the coverage file, and return every status it leads to."""
    recorded = read_file(path)
    check_part_numbers(recorded, census)
    statuses = dict(recorded)
    for assembly in census.assemblies:
        status = assembly_status(assembly, recorded)
        if status is not None:
            statuses[assembly.part_num] = status
    for d in census.decorated:
        status = decorated_status(recorded.get(d.part_num), statuses.get(d.folds_into))
        if status is not None:
            statuses[d.part_num] = status
    return statuses


# --- Using statuses --------------------------------------------------------------


def group_by_status[T: (Shape, DecoratedShape)](
    items: list[T], statuses: list[str], status_of: Statuses
) -> dict[str, list[T]]:
    """Group shapes or decorated shapes by status; untracked ones are "not started"."""
    by_status: dict[str, list[T]] = {"not started": []}
    by_status.update({status: [] for status in statuses})
    for item in items:
        by_status[status_of.get(item.part_num, "not started")].append(item)
    return by_status


def in_group[T](by_status: dict[str, list[T]], group: str) -> list[T]:
    """Return the items, from group_by_status(), in one of STATUS_GROUPS."""
    return [item for status in STATUS_GROUPS[group] for item in by_status[status]]


def write_table(db: sqlite3.Connection, status_of: Statuses) -> None:
    """Replace the coverage table with these statuses (commit afterwards)."""
    db.execute("DROP TABLE IF EXISTS coverage")
    db.execute("CREATE TABLE coverage (part_num TEXT PRIMARY KEY, status TEXT)")
    db.executemany("INSERT INTO coverage VALUES (?, ?)", sorted(status_of.items()))
