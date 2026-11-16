"""Tests for census/changes.py, on made-up condensed censuses."""

from dataclasses import replace

import changes
from condensed_census import Assembly, CondensedCensus, DecoratedShape, Shape

BRICK = Shape(
    part_num="3001",
    name="Brick 2 x 4",
    category="Bricks",
    design="3001",
    usage=100,
    reach=50,
    first_year=1958,
    last_year=2026,
    ldraw_ids="3001.dat",
    brick_system="standard",
    excluded=None,
    excluded_detail=None,
    image="",
)
TILE = replace(BRICK, part_num="3068b", name="Tile 2 x 2", category="Tiles")
PRINTED = DecoratedShape(
    part_num="3068bpr0001",
    name="Tile 2 x 2 with a print",
    folds_into="3068b",
    folded_by="relationship",
    usage=3,
    reach=2,
    first_year=2001,
    last_year=2003,
    image="",
)
WHEEL = Assembly("4624c01", "Wheel with tire", "Wheels", "", members=["3641", "4624"])


def census(*records: Shape | DecoratedShape | Assembly) -> CondensedCensus:
    """A condensed census holding these records."""
    return CondensedCensus(
        [r for r in records if isinstance(r, Shape)],
        [r for r in records if isinstance(r, DecoratedShape)],
        [r for r in records if isinstance(r, Assembly)],
    )


def titles(sections: list[changes.Section]) -> dict[str, list[str]]:
    """Each section's lines, by its title."""
    return {s.title: s.lines for s in sections}


def test_the_same_census_twice_has_no_changes() -> None:
    """Nothing is reported, and the summary says so."""
    old = census(BRICK, TILE, PRINTED, WHEEL)
    sections = changes.compare(old, census(BRICK, TILE, PRINTED, WHEEL), set())
    assert sections == []
    assert changes.summary(sections) == "no changes"
    assert changes.report("today", sections) == ["== today", "No changes.", ""]


def test_added_and_removed_records_are_listed_by_kind() -> None:
    """A new shape, a dropped decorated shape and a dropped assembly each show."""
    old = census(BRICK, PRINTED, WHEEL)
    found = titles(changes.compare(old, census(BRICK, TILE), set()))
    assert found == {
        "Shapes added": ["3068b  Tile 2 x 2"],
        "Decorated shapes removed": ["3068bpr0001  Tile 2 x 2 with a print"],
        "Assemblies removed": ["4624c01  Wheel with tire"],
    }


def test_a_shape_that_stops_being_a_candidate_is_reported_with_the_reason() -> None:
    """Exclusion changes show in both directions."""
    paper = replace(TILE, excluded="material")
    found = titles(changes.compare(census(TILE), census(paper), set()))
    assert found == {
        "Shapes that are no longer candidates": [
            "3068b  Tile 2 x 2  (now excluded: material)"
        ]
    }
    found = titles(changes.compare(census(paper), census(TILE), set()))
    assert list(found) == ["Shapes that became candidates"]


def test_refolding_and_new_members_are_reported() -> None:
    """A decorated shape that folds elsewhere, and an assembly with other shapes."""
    moved = replace(PRINTED, folds_into="3068a")
    regrouped = replace(WHEEL, members=["3641", "4624", "59895"])
    old = census(PRINTED, WHEEL)
    found = titles(changes.compare(old, census(moved, regrouped), set()))
    assert found == {
        "Decorated shapes that now fold into a different shape": [
            "3068bpr0001  3068b -> 3068a"
        ],
        "Assemblies whose shapes changed": ["4624c01  3641 4624 -> 3641 4624 59895"],
    }


def test_a_rename_is_listed_apart_from_other_field_changes() -> None:
    """Rebrickable renames many parts at once, so renames get their own section."""
    renamed = replace(TILE, name="Tile 2 x 2 with Groove", category="Tiles, Special")
    found = titles(changes.compare(census(TILE), census(renamed), set()))
    assert found == {
        "Shapes whose category, design or brick system changed": [
            "3068b  category: Tiles -> Tiles, Special"
        ],
        "Shapes renamed": ["3068b  Tile 2 x 2 -> Tile 2 x 2 with Groove"],
    }


def test_usage_changes_are_counted_not_listed() -> None:
    """Usage moves with every snapshot, so it gets one line."""
    busier = replace(BRICK, usage=130)
    found = titles(changes.compare(census(BRICK, TILE), census(busier, TILE), set()))
    assert found == {"Usage": ["1 shapes changed usage; total 200 -> 230"]}


def test_changes_to_tracked_part_numbers_come_first() -> None:
    """A removed shape that coverage.csv tracks is pulled to the top."""
    sections = changes.compare(census(BRICK, TILE), census(TILE), {"3001"})
    assert sections[0] == changes.Section(
        "Tracked in coverage.csv and affected",
        ["3001  Brick 2 x 4   [shapes removed]"],
    )


def test_the_report_lists_each_section_with_its_count() -> None:
    """The log entry has a heading, then a counted title and indented lines."""
    sections = changes.compare(census(BRICK), census(BRICK, TILE), set())
    assert changes.report("today", sections) == [
        "== today",
        "",
        "Shapes added (1)",
        "  3068b  Tile 2 x 2",
        "",
    ]
    assert changes.report("today", None)[1].startswith("First condensed census")
