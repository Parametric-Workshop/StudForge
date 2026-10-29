"""Tests for census/condense.py, on the sample census (see conftest.py)."""

import sqlite3

import pytest

import condense
import folding
import usage
from condensed_census import Assembly, Shape


@pytest.fixture(scope="module")
def shapes_and_assemblies(
    db: sqlite3.Connection, rules: folding.FoldingRules, per_set: usage.PerSetUsage
) -> tuple[dict[str, Shape], dict[str, Assembly]]:
    """Shapes and assemblies from the sample census, keyed by part number."""
    sets = condense.load_sets(db)
    images, _ = condense.load_images(db, rules)
    shapes, assemblies = condense.make_shapes_and_assemblies(
        db, rules, per_set, sets, images
    )
    return {s.part_num: s for s in shapes}, {a.part_num: a for a in assemblies}


@pytest.fixture(scope="module")
def shapes(
    shapes_and_assemblies: tuple[dict[str, Shape], dict[str, Assembly]],
) -> dict[str, Shape]:
    """The sample census's shapes, keyed by part number."""
    return shapes_and_assemblies[0]


def test_unlisted_shape_gets_a_census_row(shapes: dict[str, Shape]) -> None:
    """The unlisted shape takes its first decorated shape's details, flagged."""
    wings = shapes["01642"]
    assert (wings.name, wings.unlisted) == ("Wings with Stripes Print", True)
    assert (wings.category, wings.design) == ("Minifig Accessories", "01642")
    assert (wings.usage, wings.reach) == (2, 1)


def test_census_holds_every_undecorated_shape(
    shapes_and_assemblies: tuple[dict[str, Shape], dict[str, Assembly]],
) -> None:
    """Only decorated shapes fold away; assemblies are kept apart from shapes."""
    shapes, assemblies = shapes_and_assemblies
    assert set(shapes) == {
        "3001",
        "3068a",
        "3068b",
        "4624",
        "3641",
        "973",
        "0001",
        "970c00",
        "250",
        "250pr0001",
        "3814",
        "01642",
    }
    assert set(assemblies) == {"4624c01"}


def test_shape_values(shapes: dict[str, Shape]) -> None:
    """A shape carries its usage, reach, years, LDraw IDs and scope."""
    brick = shapes["3001"]
    assert (brick.name, brick.category, brick.design) == (
        "Brick 2 x 4",
        "Bricks",
        "3001",
    )
    assert (brick.usage, brick.reach, brick.years) == (7, 2, "1999-2005")
    assert brick.ldraw_ids == "3001"
    assert (brick.brick_system, brick.excluded) == ("standard", None)
    assert brick.image == "https://img.test/3001.jpg"


def test_rubber_is_a_candidate_and_paper_is_excluded(shapes: dict[str, Shape]) -> None:
    """Rubber tires print in TPU; a paper sticker sheet can't be printed."""
    assert shapes["3641"].excluded is None
    assert (shapes["0001"].excluded, shapes["0001"].excluded_detail) == (
        "not 3D printable",
        "cardboard/paper",
    )


def test_assemblies_list_their_shapes(
    shapes_and_assemblies: tuple[dict[str, Shape], dict[str, Assembly]],
) -> None:
    """The wheel assembly holds the wheel and the tire, and has no usage (ADR 0001)."""
    wheel = shapes_and_assemblies[1]["4624c01"]
    assert wheel.members == ["3641", "4624"]


def test_shape_images_fall_back_to_a_decorated_shape_then_an_element(
    db: sqlite3.Connection, rules: folding.FoldingRules
) -> None:
    """3001 keeps its own photo over its element's; 3068b borrows a decorated one's.

    The wheel 4624 only reaches sets inside its assembly, so no inventory line
    gives it a photo; it gets its highest-numbered (newest) element's photo.
    """
    shapes, decorated = condense.load_images(db, rules)
    assert decorated["3068bpr0001"] == "https://img.test/3068bpr0001.jpg"
    assert shapes == {
        "3001": "https://img.test/3001.jpg",
        "3068b": "https://img.test/3068bpr0001.jpg",
        "01642": "https://img.test/01642pr0002.jpg",
        "4624": "https://cdn.rebrickable.com/media/parts/elements/462401.jpg",
    }


def test_decorated_shapes_carry_their_own_usage(
    db: sqlite3.Connection, rules: folding.FoldingRules, per_set: usage.PerSetUsage
) -> None:
    """A decorated shape keeps its own name, usage and photo."""
    _, images = condense.load_images(db, rules)
    sets = condense.load_sets(db)
    decorated = {
        d.part_num: d
        for d in condense.make_decorated_shapes(db, rules, per_set, sets, images)
    }
    tile = decorated["3068bpr0001"]
    assert (tile.folds_into, tile.folded_by) == ("3068b", "relationship")
    assert (tile.usage, tile.reach) == (1, 1)
    assert tile.image == "https://img.test/3068bpr0001.jpg"


def test_condense_writes_its_tables_and_leaves_the_census_alone(
    db: sqlite3.Connection,
) -> None:
    """Condensing twice gives the same tables, and the census tables stay."""
    first = condense.condense(db)
    assert condense.condense(db) == first
    assert db.execute("SELECT COUNT(*) FROM parts").fetchone()[0] == 21
    count = db.execute("SELECT COUNT(*) FROM condensed_shape").fetchone()[0]
    assert count == first[0]
    meta = dict(db.execute("SELECT key, value FROM meta"))
    assert (meta["snapshot_date"], meta["part_numbers"]) == ("2026-10-23", "21")


def test_condensing_records_the_rules_it_used(db: sqlite3.Connection) -> None:
    """A fresh census needs condensing; once condensed, no rule counts as changed."""
    assert condense.changed_rule_files({}) == condense.RULE_FILES
    condense.condense(db)
    meta = dict(db.execute("SELECT key, value FROM meta"))
    assert condense.changed_rule_files(meta) == []
