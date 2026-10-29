"""Tests for census/usage.py, on the sample census (see conftest.py)."""

from collections import Counter

import usage


def test_usage_leaves_out_spares_and_old_versions(
    per_set: usage.PerSetUsage,
) -> None:
    """3001: 2 in set 1000-1 (its spare left out), and 5 in set 2000-1.

    Set 2000-1 has two inventory versions; only the latest counts, so the old
    version's 99 never shows up.
    """
    assert per_set["3001"] == Counter({"1000-1": 2, "2000-1": 5})


def test_assembly_usage_flows_to_its_shapes(per_set: usage.PerSetUsage) -> None:
    """Four wheel assemblies count as four wheels and four tires (ADR 0001)."""
    assert per_set["4624"]["1000-1"] == 4
    assert per_set["3641"]["1000-1"] == 4
    assert "4624c01" not in per_set


def test_decorated_assembly_without_its_own_sub_parts_expands_like_its_base(
    per_set: usage.PerSetUsage,
) -> None:
    """Three decorated 4624c01pr0001 count as three wheels and three tires."""
    assert per_set["4624"]["2000-1"] == 3
    assert per_set["3641"]["2000-1"] == 3


def test_decorated_and_assembled_tiles_both_count_as_the_shape(
    per_set: usage.PerSetUsage,
) -> None:
    """3068bpr0001 and the tile inside assembly 67401 each add one 3068b."""
    assert per_set["3068b"] == Counter({"1000-1": 2})


def test_shapes_folded_by_part_number_count_as_their_shape(
    per_set: usage.PerSetUsage,
) -> None:
    """Decorated legs count as plain legs, and a decorated torso as the plain torso."""
    assert per_set["970c00"] == Counter({"1000-1": 1})
    assert per_set["3814"] == Counter({"1000-1": 1})


def test_decorated_shapes_also_get_their_own_usage(
    per_set: usage.PerSetUsage,
) -> None:
    """The decorated torso counts toward 3814, and on its own too."""
    assert per_set["973c04h02pr0001"] == Counter({"1000-1": 1})
    assert per_set["4624c01pr0001"] == Counter({"2000-1": 3})


def test_minifig_shapes_are_multiplied_by_minifig_quantity(
    per_set: usage.PerSetUsage,
) -> None:
    """Set 2000-1 has two minifigs, so two torsos."""
    assert per_set["973"] == Counter({"2000-1": 2})
