"""The condensed census tables: what they hold, and how to save and load them.

census/condense.py builds the records below and saves them with write();
census/census_viewer.py loads them with read(). This is the only file that
knows the condensed tables' SQL. Each table's CREATE TABLE sits beside the
class it stores, with the same names for columns and fields, so a table can
be read straight back into its class.

Terms follow GLOSSARY.md.
"""

import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any


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


def write(
    db: sqlite3.Connection, census: CondensedCensus, shape_sets: list[ShapeSet]
) -> None:
    """Replace the condensed tables with these records (commit afterwards)."""
    for table in TABLES:
        db.execute(f"DROP TABLE IF EXISTS {table}")
    db.executescript(SCHEMA)
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


def rows(db: sqlite3.Connection, sql: str) -> Iterator[dict[str, Any]]:
    """Yield each row of a query as a dict keyed by column name."""
    cursor = db.execute(sql)
    columns = [c[0] for c in cursor.description]
    for row in cursor:
        yield dict(zip(columns, row, strict=True))


def read(db: sqlite3.Connection) -> CondensedCensus:
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


def read_shape_sets(db: sqlite3.Connection) -> list[ShapeSet]:
    """Load the usage of each shape in each official set."""
    return [ShapeSet(**r) for r in rows(db, "SELECT * FROM shape_set")]
