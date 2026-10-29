"""Tests for census/folding.py, on the sample census (see conftest.py)."""

import pytest

import folding


def test_decorated_shapes_fold_into_their_shape(rules: folding.FoldingRules) -> None:
    """A decorated shape and a decorated assembly both fold to the plain shape."""
    assert rules.shape_of("3068bpr0001") == "3068b"
    assert rules.shape_of("67401") == "3068b"
    assert rules.shape_of("3001") == "3001"


def test_decorated_assembly_does_not_make_its_base_an_assembly(
    rules: folding.FoldingRules,
) -> None:
    """67401 is an assembly, but the plain 3068b it decorates is not."""
    assert rules.assemblies["67401"] == ["3068b"]
    assert "3068b" not in rules.assemblies


def test_assembly_loop_stops_and_is_recorded() -> None:
    """Two assemblies that contain each other expand a limited depth, then stop."""
    rules = folding.FoldingRules(
        assemblies={"loop-a": ["loop-b"], "loop-b": ["loop-a"]}
    )
    assert list(rules.expand("loop-a")) == ["loop-b"]
    assert rules.depth_limited == {"loop-b"}


@pytest.mark.parametrize(
    ("part_num", "shape", "folded_by"),
    [
        ("970c00pr0001", "970c00", "stem"),
        ("973c04h02pr0001", "3814", "torso"),
        ("973d14pr0001", "3814", "torso"),
        ("01642pr0001", "01642", "unlisted"),
    ],
)
def test_decorated_shapes_without_a_relationship_fold_by_part_number(
    rules: folding.FoldingRules, part_num: str, shape: str, folded_by: str
) -> None:
    """Each decorated shape records its shape and how it was found."""
    assert rules.shape_of(part_num) == shape
    assert rules.folded_by[part_num] == folded_by


def test_a_stem_in_another_category_does_not_fold(rules: folding.FoldingRules) -> None:
    """The HO Scale truck 250pr0001 is not a decorated Duplo brick 250."""
    assert rules.shape_of("250pr0001") == "250pr0001"
    assert "250pr0001" not in rules.folded_by


def test_mold_variants_share_a_design(rules: folding.FoldingRules) -> None:
    """Variants are grouped under the alphabetically first part number."""
    designs = folding.group_designs(rules)
    assert designs["3068b"] == "3068a"
    assert designs["3068a"] == "3068a"
