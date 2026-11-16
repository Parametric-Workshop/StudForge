"""Reading the census database: where it is, and how to load and save what it holds.

Everything that reads or writes the census goes through this file. It is the only
one that holds SQL or knows the census is SQLite (census/tests/test_sql_in_one_place.py
checks that), so a change of database is a change to this file alone:
  - open_census() opens it; start_snapshot() and commit() replace a snapshot's
    tables, keeping any others; read_meta() says which snapshot it was built from and
    when, from the details the build steps save with write_meta().
  - write_table() and add_index() copy a table in from Rebrickable; read_table()
    yields its rows and row_count() counts them.
  - read() and read_shape_sets() load the condensed tables as the records below,
    which census/condense.py builds and saves with write().
  - write_coverage() saves the statuses census/coverage.py works out.

Every change is all-or-nothing: begin() starts one, and until it is committed the
census still holds what it held before. broken_links() and commit() check the
result, so a census that fails a check is never the one that is saved.

Each condensed table's CREATE TABLE sits beside the class it stores, with the same
names for columns and fields, so a table can be read straight back into its class.

Terms follow GLOSSARY.md.
"""

import sqlite3
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# build/ is local only: the census is built from a snapshot, never committed.
DB_PATH = Path(__file__).resolve().parent.parent / "build" / "census.sqlite"


def year_text(first_year: int | None, last_year: int | None) -> str:
    """Return a year range such as "1999-2005", or "" if never in a set."""
    return f"{first_year}-{last_year}" if first_year else ""


# --- Decorated shapes ------------------------------------------------------------


@dataclass
class DecoratedShape:
    """A shape with a decoration applied, under its own part number."""

    part_num: str
    name: str
    folds_into: str  # part number of the shape (or assembly) it folds into
    folded_by: str  # how that was found: relationship, stem, torso or unlisted
    usage: int  # its own; also counted in its shape's
    reach: int
    first_year: int | None
    last_year: int | None
    image: str

    @property
    def years(self) -> str:
        """The years it was in sets, such as "1999-2005"."""
        return year_text(self.first_year, self.last_year)


DECORATED_SHAPE_TABLE = """
CREATE TABLE decorated_shape (
    part_num   TEXT PRIMARY KEY,
    name       TEXT,
    folds_into TEXT,
    folded_by  TEXT,
    usage      INTEGER,
    reach      INTEGER,
    first_year INTEGER,
    last_year  INTEGER,
    image      TEXT               -- photo on Rebrickable
);
"""
INSERT_DECORATED_SHAPE = """
INSERT INTO decorated_shape VALUES (:part_num, :name, :folds_into, :folded_by,
    :usage, :reach, :first_year, :last_year, :image)
"""


# --- Assemblies ------------------------------------------------------------------


@dataclass
class Assembly:
    """A factory-combined group of shapes under its own part number (ADR 0001)."""

    part_num: str
    name: str
    category: str  # Rebrickable Category
    image: str
    # Not columns of the assembly table: members are stored in assembly_member,
    # and read() fills in the decorated shapes that fold into the assembly.
    members: list[str] = field(default_factory=list)
    decorated: list[DecoratedShape] = field(default_factory=list)


ASSEMBLY_TABLE = """
CREATE TABLE assembly (
    part_num TEXT PRIMARY KEY,
    name     TEXT,
    category TEXT,
    image    TEXT                 -- photo on Rebrickable
);
CREATE TABLE assembly_member (assembly TEXT, part_num TEXT);
"""
INSERT_ASSEMBLY = "INSERT INTO assembly VALUES (:part_num, :name, :category, :image)"
INSERT_ASSEMBLY_MEMBER = "INSERT INTO assembly_member VALUES (?, ?)"


# --- Shapes ----------------------------------------------------------------------


@dataclass
class Shape:
    """One distinct geometry StudForge models, with decorated shapes folded in."""

    part_num: str
    name: str
    category: str  # Rebrickable Category
    design: str  # the Design this shape is a Variant of
    usage: int
    reach: int
    first_year: int | None  # earliest set release containing it
    last_year: int | None  # latest set release containing it
    ldraw_ids: str  # space-separated LDraw file names
    brick_system: str  # standard, duplo, quatro, primo or modulex
    excluded: str | None  # why StudForge won't make it; None for a candidate
    excluded_detail: str | None  # the specific material, system or category
    image: str
    unlisted: bool = False  # Rebrickable lists only its decorated shapes
    # Not columns of the shape table: read() fills these in from the other tables.
    decorated: list[DecoratedShape] = field(default_factory=list)
    assemblies: list[Assembly] = field(default_factory=list)  # ones it's in

    @property
    def years(self) -> str:
        """The years it was in sets, such as "1999-2005"."""
        return year_text(self.first_year, self.last_year)


SHAPE_TABLE = """
CREATE TABLE condensed_shape (
    part_num        TEXT PRIMARY KEY,
    name            TEXT,
    category        TEXT,
    design          TEXT,
    usage           INTEGER,
    reach           INTEGER,
    first_year      INTEGER,
    last_year       INTEGER,
    ldraw_ids       TEXT,
    brick_system    TEXT,
    excluded        TEXT,         -- NULL for a candidate
    excluded_detail TEXT,
    image           TEXT,         -- photo on Rebrickable
    unlisted        INTEGER       -- 1 if Rebrickable has no part number for it
);
"""
INSERT_SHAPE = """
INSERT INTO condensed_shape VALUES (:part_num, :name, :category, :design, :usage,
    :reach, :first_year, :last_year, :ldraw_ids, :brick_system, :excluded,
    :excluded_detail, :image, :unlisted)
"""


# --- Usage by set ----------------------------------------------------------------


@dataclass
class ShapeSet:
    """How many of one shape one official set uses; kept for future set search."""

    part_num: str
    set_num: str
    quantity: int


SHAPE_SET_TABLE = """
CREATE TABLE shape_set (part_num TEXT, set_num TEXT, quantity INTEGER);
"""
INSERT_SHAPE_SET = "INSERT INTO shape_set VALUES (:part_num, :set_num, :quantity)"


# --- Saving and loading ----------------------------------------------------------

TABLES = [
    "condensed_shape",
    "decorated_shape",
    "assembly",
    "assembly_member",
    "shape_set",
]
SCHEMA = SHAPE_TABLE + DECORATED_SHAPE_TABLE + ASSEMBLY_TABLE + SHAPE_SET_TABLE


@dataclass
class CondensedCensus:
    """Every shape, decorated shape and assembly, linked to one another."""

    shapes: list[Shape]
    decorated: list[DecoratedShape]
    assemblies: list[Assembly]


@dataclass
class PartNumbers:
    """What the condensed census made of every part number Rebrickable lists."""

    shapes: int  # listed by Rebrickable; unlisted shapes come on top
    decorated: int
    assemblies: int
    unlisted: int  # shapes the condensed census adds, with no part number

    @property
    def total(self) -> int:
        """Every part number Rebrickable lists."""
        return self.shapes + self.decorated + self.assemblies


def count_part_numbers(census: CondensedCensus) -> PartNumbers:
    """Count what the condensed census made of Rebrickable's part numbers."""
    unlisted = sum(1 for shape in census.shapes if shape.unlisted)
    return PartNumbers(
        shapes=len(census.shapes) - unlisted,
        decorated=len(census.decorated),
        assemblies=len(census.assemblies),
        unlisted=unlisted,
    )


# An open census database. Other modules pass one along under this name, so this
# file is the only one that knows the census is SQLite.
type Census = sqlite3.Connection


def open_census(path: Path = DB_PATH) -> Census:
    """Open the census database, to pass to the functions below (close it after)."""
    return sqlite3.connect(path)


def start_snapshot(db: Census, copied_tables: Iterable[str]) -> None:
    """Begin replacing a snapshot: remove what came from the old one, keep the rest.

    Drops the tables copied from Rebrickable (copied_tables), and everything worked
    out from them: the condensed tables, the coverage table and the meta table. Any
    other table in the census is left as it is.

    Nothing changes for other readers until commit(): if the import fails before
    then, the census still holds the previous snapshot, whole.
    """
    begin(db)
    for table in (*copied_tables, *TABLES, "coverage", "meta"):
        db.execute(f'DROP TABLE IF EXISTS "{table}"')


def begin(db: Census) -> None:
    """Start a change that is saved whole by a commit, or not at all.

    Without this, dropping or making a table takes effect at once and can't be
    undone, so a failure partway would leave the census half changed. Does
    nothing if such a change is already under way.
    """
    if not db.in_transaction:
        db.execute("BEGIN")


def commit(db: Census) -> None:
    """Save everything written since begin(), then tidy and check the file.

    Gives back unused space, and stops if SQLite finds the file damaged.
    """
    db.commit()
    # Dropped tables leave empty pages; without this the file only grows.
    db.execute("VACUUM")
    verdict = [row[0] for row in db.execute("PRAGMA integrity_check")]
    if verdict != ["ok"]:
        raise SystemExit(f"The census file is damaged: {'; '.join(verdict[:5])}")


def read_meta() -> dict[str, str]:
    """Return the census's meta table, or an empty dict if there's no census yet."""
    if not DB_PATH.exists():
        return {}
    db = open_census()
    meta = dict(db.execute("SELECT key, value FROM meta"))
    db.close()
    return meta


def write_meta(db: Census, details: dict[str, str]) -> None:
    """Add these details to the meta table, replacing any already there.

    Makes the table in a new census. Commit afterwards.
    """
    db.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
    db.executemany("INSERT OR REPLACE INTO meta VALUES (?,?)", details.items())


def write_table(
    db: Census, table: str, columns: Sequence[str], rows: Iterable[Sequence[str]]
) -> int:
    """Make a table with these columns, fill it with the rows, and return its row count.

    For the tables copied from Rebrickable, whose columns are the CSV's header.
    """
    db.execute(f'CREATE TABLE "{table}" ({", ".join(columns)})')
    placeholders = ",".join("?" * len(columns))
    db.executemany(f'INSERT INTO "{table}" VALUES ({placeholders})', rows)
    return row_count(db, table)


def add_index(db: Census, table: str, column: str) -> None:
    """Index a table by one column, so looking rows up by it is fast."""
    db.execute(f"CREATE INDEX {table}_{column} ON {table} ({column})")


def row_count(db: Census, table: str) -> int:
    """Return how many rows a table holds."""
    return db.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]


def read_table(db: Census, table: str) -> Iterator[dict[str, str]]:
    """Yield each row of a Rebrickable table as a dict keyed by column name."""
    return rows(db, f'SELECT * FROM "{table}"')


def write(db: Census, census: CondensedCensus, shape_sets: list[ShapeSet]) -> None:
    """Replace the condensed tables with these records.

    Nothing is saved until a commit, so the caller can check the result first,
    and a failure or a rollback leaves the previous condensed census whole.
    """
    begin(db)
    for table in TABLES:
        db.execute(f"DROP TABLE IF EXISTS {table}")
    # One statement at a time: sqlite3's executescript() would save what has been
    # done so far, and the change could no longer be undone as a whole.
    for statement in statements(SCHEMA):
        db.execute(statement)
    # vars() gives each record's fields by name, which the :name placeholders
    # pick from; the linked lists (decorated, members) are simply not used.
    db.executemany(INSERT_SHAPE, [vars(s) for s in census.shapes])
    db.executemany(INSERT_DECORATED_SHAPE, [vars(d) for d in census.decorated])
    db.executemany(INSERT_ASSEMBLY, [vars(a) for a in census.assemblies])
    db.executemany(
        INSERT_ASSEMBLY_MEMBER,
        [(a.part_num, m) for a in census.assemblies for m in a.members],
    )
    db.executemany(INSERT_SHAPE_SET, [vars(s) for s in shape_sets])


def statements(script: str) -> list[str]:
    """Split SQL text holding several statements into the statements."""
    found: list[str] = []
    current = ""
    for line in script.splitlines(keepends=True):
        current += line
        if sqlite3.complete_statement(current):
            found.append(current)
            current = ""
    return found


def broken_links(db: Census) -> list[str]:
    """Return what is wrong with how the condensed tables point at each other.

    Empty when every decorated shape folds into a shape or an assembly, every
    assembly member belongs to an assembly and is a shape or an assembly, and
    every usage row is for a shape. The tables can't declare these as rules,
    because a part number may be found in either of two tables.
    """
    checks = {
        "decorated shapes that fold into nothing": """
            SELECT COUNT(*) FROM decorated_shape
            WHERE folds_into NOT IN (SELECT part_num FROM condensed_shape)
              AND folds_into NOT IN (SELECT part_num FROM assembly)""",
        "assembly members whose assembly is missing": """
            SELECT COUNT(*) FROM assembly_member
            WHERE assembly NOT IN (SELECT part_num FROM assembly)""",
        "assembly members that are neither a shape nor an assembly": """
            SELECT COUNT(*) FROM assembly_member
            WHERE part_num NOT IN (SELECT part_num FROM condensed_shape)
              AND part_num NOT IN (SELECT part_num FROM assembly)""",
        "usage rows for a part number that is not a shape": """
            SELECT COUNT(*) FROM shape_set
            WHERE part_num NOT IN (SELECT part_num FROM condensed_shape)""",
    }
    counts = {what: db.execute(sql).fetchone()[0] for what, sql in checks.items()}
    return [f"{count:,} {what}" for what, count in counts.items() if count]


def rows(db: Census, sql: str) -> Iterator[dict[str, Any]]:
    """Yield each row of a query as a dict keyed by column name."""
    cursor = db.execute(sql)
    columns = [c[0] for c in cursor.description]
    for row in cursor:
        yield dict(zip(columns, row, strict=True))


def read(db: Census) -> CondensedCensus:
    """Load the condensed tables, with each record linked to the ones it holds.

    Each shape gets its decorated shapes and the assemblies it's in; each
    assembly gets its members and its decorated shapes.
    """
    shapes = [Shape(**r) for r in rows(db, "SELECT * FROM condensed_shape")]
    decorated = [DecoratedShape(**r) for r in rows(db, "SELECT * FROM decorated_shape")]
    assemblies = [
        Assembly(**r) for r in rows(db, "SELECT * FROM assembly ORDER BY part_num")
    ]
    shape_by_num = {s.part_num: s for s in shapes}
    assembly_by_num = {a.part_num: a for a in assemblies}

    for d in decorated:
        holder = shape_by_num.get(d.folds_into) or assembly_by_num[d.folds_into]
        holder.decorated.append(d)
    members = db.execute(
        "SELECT assembly, part_num FROM assembly_member ORDER BY assembly, part_num"
    )
    for assembly_num, member in members:
        assembly = assembly_by_num[assembly_num]
        assembly.members.append(member)
        if member in shape_by_num:  # a few members are assemblies themselves
            shape_by_num[member].assemblies.append(assembly)
    return CondensedCensus(shapes, decorated, assemblies)


def read_shape_sets(db: Census) -> list[ShapeSet]:
    """Load the usage of each shape in each official set."""
    return [ShapeSet(**r) for r in rows(db, "SELECT * FROM shape_set")]


def write_coverage(db: Census, status_of: dict[str, str]) -> None:
    """Replace the coverage table with each part number's status, and save it.

    A working copy for SQL of what census/coverage.py works out;
    coverage/coverage.csv stays the source.
    """
    begin(db)
    db.execute("DROP TABLE IF EXISTS coverage")
    db.execute("CREATE TABLE coverage (part_num TEXT PRIMARY KEY, status TEXT)")
    db.executemany("INSERT INTO coverage VALUES (?, ?)", sorted(status_of.items()))
    db.commit()  # without this, sqlite discards the table when the census is closed
