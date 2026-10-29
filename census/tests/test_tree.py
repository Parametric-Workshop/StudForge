"""Tests for census/tree.py, using a handful of made-up shapes."""

from dataclasses import replace

import tree
from condensed_census import Assembly, DecoratedShape, Shape
from coverage import Statuses

GROUPINGS = tree.Groupings(
    groups={"Plates": "Plates", "Bricks": "Bricks"},
    families={
        "Plates": [
            ("Corner plate", ["Corner"]),
            ("Rectangular plate", []),
        ]
    },
)


# A plain, untracked standard plate; each test shape changes only what it needs.
PLATE = Shape(
    part_num="",
    name="",
    category="Plates",
    design="",
    usage=1,
    reach=1,
    first_year=None,
    last_year=None,
    ldraw_ids="",
    brick_system="standard",
    excluded=None,
    excluded_detail=None,
    image="",
)


def decorated(part_num: str, folds_into: str, usage: int) -> DecoratedShape:
    """Return a decorated shape with only the details these tests need."""
    return DecoratedShape(
        part_num, "", folds_into, "relationship", usage, 1, None, None, ""
    )


HINGE = Assembly(
    "2429c01",
    "Hinge Plate 1 x 4",
    "Hinges",
    "",
    ["3023", "3024"],
    [decorated("2429c01pr0001", "2429c01", 1)],
)

SHAPES = [
    replace(
        PLATE,
        part_num="3023",
        design="3023",
        name="Plate 1 x 2",
        usage=100,
        decorated=[
            decorated("3023pr0001", "3023", 2),
            decorated("3023pr0002", "3023", 5),
        ],
        assemblies=[HINGE],
    ),
    replace(
        PLATE,
        part_num="3024",
        design="3024",
        name="Plate 1 x 1",
        usage=60,
        assemblies=[HINGE],
    ),
    replace(PLATE, part_num="3020", design="3020", name="Plate 2 x 4", usage=40),
    replace(PLATE, part_num="2420", design="2420", name="Plate 2 x 2 Corner", usage=30),
    replace(
        PLATE, part_num="3023a", design="3023", name="Plate 1 x 2 [Old Style Bottom]"
    ),
    replace(
        PLATE,
        part_num="3001",
        design="3001",
        name="Brick 2 x 4",
        category="Bricks",
        usage=50,
    ),
    replace(
        PLATE,
        part_num="3437",
        design="3437",
        name="Duplo Brick 2 x 2",
        category="Duplo, Quatro and Primo",
        usage=5,
        brick_system="duplo",
    ),
    replace(
        PLATE,
        part_num="0001",
        design="0001",
        name="Sticker Sheet",
        category="Stickers",
        usage=2,
        excluded="not 3D printable",
        excluded_detail="Stickers",
        decorated=[decorated("0001pr0001", "0001", 1)],
    ),
]

# The coverage statuses these tests track.
STATUSES: Statuses = {"3023": "planned", "3024": "validated"}

LEAF_KINDS = {"shape", "decorated", "assembly"}


def build() -> tree.Node:
    """Build a tree from SHAPES: 8 shapes, 7 of them candidates."""
    return tree.build_tree(SHAPES, "Part numbers", "test", "", GROUPINGS)


def check_sums(node: tree.Node) -> None:
    """Assert that every node's count is the sum of its children's, down to shapes."""
    if node.kind not in LEAF_KINDS:
        assert node.shape_count == sum(c.shape_count for c in node.children), node.label
        for child in node.children:
            check_sums(child)


def test_every_parent_is_the_sum_of_its_children() -> None:
    """Counts add up at every level, starting from all shapes."""
    root = build()
    assert [c.label for c in root.children] == ["Candidates", "Excluded"]
    assert root.shape_count == 8
    assert [c.shape_count for c in root.children] == [7, 1]
    check_sums(root)


def test_decorated_shapes_sit_under_their_shape_most_used_first() -> None:
    """3023's decorated shapes come first, then the assembly it is in."""
    plate = tree.find(tree.find(build(), "Candidates"), "3023")
    assert [(c.label, c.kind) for c in plate.children] == [
        ("3023pr0002", "decorated"),
        ("3023pr0001", "decorated"),
        ("2429c01", "assembly"),
    ]
    assert tree.find(build(), "Candidates").decorated[0].part_num == "3023pr0001"


def test_assemblies_sit_under_each_member_shape() -> None:
    """The hinge appears under both its plates, with its decorated shape below."""
    candidates = tree.find(build(), "Candidates")
    for member in ("3023", "3024"):
        hinge = tree.find(tree.find(candidates, member), "2429c01")
        assert hinge.record is HINGE
        assert [c.label for c in hinge.children] == ["2429c01pr0001"]


def test_levels_under_candidates() -> None:
    """Candidates split by brick system, then group and category for standard."""
    root = build()
    standard = tree.find(root, "Standard")
    assert [g.label for g in standard.children] == ["Plates", "Bricks"]
    assert [c.label for c in tree.find(root, "Duplo").children] == [
        "Duplo, Quatro and Primo"
    ]
    assert tree.find(root, "Excluded").children[0].note == "not 3D printable"


def test_families_sort_shapes_by_size_with_old_variants_after() -> None:
    """1x1 before 1x2, the old 1x2 right after it, then 2x4."""
    family = tree.find(build(), "Rectangular plate")
    assert [s.label for s in family.children] == ["3024", "3023", "3023a", "3020"]
    assert tree.find(build(), "Corner plate").shape_count == 1


def test_family_rules() -> None:
    """The first matching rule wins; regex words start with "re:"."""
    rules: list[tree.FamilyRule] = [
        ("Tall brick", [r"re:\d+ x \d+ x \d+"]),
        ("Corner brick", ["Corner"]),
        ("Rectangular brick", []),
    ]
    assert tree.family_of(rules, "Brick 1 x 2 x 5") == "Tall brick"
    assert tree.family_of(rules, "Brick 2 x 2 Corner") == "Corner brick"
    assert tree.family_of(rules, "Brick 2 x 4") == "Rectangular brick"
