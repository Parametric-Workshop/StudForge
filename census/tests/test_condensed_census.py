"""Tests for census/condensed_census.py, on the sample census (see conftest.py)."""

import sqlite3
from pathlib import Path

import condense
import condensed_census
import folding
import usage


def test_what_is_written_reads_back_the_same(
    db: sqlite3.Connection, rules: folding.FoldingRules, per_set: usage.PerSetUsage
) -> None:
    """Every record survives a save and load, with its links filled in.

    This fails if a table and the class it stores ever disagree.
    """
    sets = condense.load_sets(db)
    shape_images, decorated_images = condense.load_images(db, rules)
    shapes, assemblies = condense.make_shapes_and_assemblies(
        db, rules, per_set, sets, shape_images
    )
    decorated = condense.make_decorated_shapes(
        db, rules, per_set, sets, decorated_images
    )
    shape_sets = condense.make_shape_sets(shapes, per_set)
    written = condensed_census.CondensedCensus(shapes, decorated, assemblies)
    condensed_census.write(db, written, shape_sets)

    read = condensed_census.read(db)
    assert [vars(s) | {"decorated": [], "assemblies": []} for s in read.shapes] == [
        vars(s) for s in shapes
    ]
    assert read.decorated == decorated
    assert [(a.part_num, a.members) for a in read.assemblies] == [
        (a.part_num, a.members) for a in assemblies
    ]
    assert condensed_census.read_shape_sets(db) == shape_sets


def test_read_links_each_shape_to_what_it_holds(db: sqlite3.Connection) -> None:
    """3068b holds its decorated tile; the wheel and tire know their assembly."""
    condense.condense(db)
    census = condensed_census.read(db)
    shapes = {s.part_num: s for s in census.shapes}
    assert "3068bpr0001" in [d.part_num for d in shapes["3068b"].decorated]
    assert [a.part_num for a in shapes["4624"].assemblies] == ["4624c01"]
    wheel = census.assemblies[0]
    assert [d.part_num for d in wheel.decorated] == ["4624c01pr0001"]


def test_coverage_is_saved_for_a_later_reader(tmp_path: Path) -> None:
    """Statuses written to a census are there when it is opened again."""
    path = tmp_path / "census.sqlite"
    db = condensed_census.open_census(path)
    condensed_census.write_coverage(db, {"3001": "modeled", "3003": "planned"})
    db.close()

    db = condensed_census.open_census(path)
    saved = dict(db.execute("SELECT part_num, status FROM coverage"))
    db.close()
    assert saved == {"3001": "modeled", "3003": "planned"}


def test_a_write_that_is_not_committed_can_be_undone(db: sqlite3.Connection) -> None:
    """Until a commit, the previous condensed census is one rollback away."""
    condense.condense(db)
    before = len(condensed_census.read(db).shapes)
    condensed_census.write(db, condensed_census.CondensedCensus([], [], []), [])
    assert condensed_census.read(db).shapes == []
    db.rollback()
    assert len(condensed_census.read(db).shapes) == before


def test_broken_links_are_found(db: sqlite3.Connection) -> None:
    """A sound condensed census has none; a decorated shape with no holder is one."""
    condense.condense(db)
    assert condensed_census.broken_links(db) == []
    db.execute("UPDATE decorated_shape SET folds_into = 'nothing' WHERE rowid = 1")
    assert condensed_census.broken_links(db) == [
        "1 decorated shapes that fold into nothing"
    ]
    db.rollback()
