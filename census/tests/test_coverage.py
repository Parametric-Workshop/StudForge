"""Tests for census/coverage.py, on made-up shapes and assemblies."""

from pathlib import Path

from test_tree import HINGE, SHAPES, decorated

import coverage
from condensed_census import CondensedCensus


def test_an_assembly_takes_its_least_advanced_shapes_status() -> None:
    """The hinge is covered only once both its plates are."""
    assert coverage.assembly_status(HINGE, {}) is None
    assert coverage.assembly_status(HINGE, {"3023": "validated"}) is None
    both = {"3023": "validated", "3024": "print-tested"}
    assert coverage.assembly_status(HINGE, both) == "validated"
    assert coverage.assembly_status(HINGE, {**both, "3023": "planned"}) == "planned"


def test_load_works_out_assembly_and_decorated_statuses(tmp_path: Path) -> None:
    """Both plates modeled: the hinge is modeled, and its decorated version follows."""
    path = tmp_path / "coverage.csv"
    path.write_text(
        "part_num,status\n3023,modeled\n3024,validated\n3023pr0001,planned\n"
    )
    printed_hinge = decorated("2429c01pr0001", "2429c01", 1)
    census = CondensedCensus(SHAPES, [printed_hinge], [HINGE])
    statuses = coverage.load(census, path)
    assert statuses["2429c01"] == "modeled"
    assert statuses["2429c01pr0001"] == "shape modeled"
    assert statuses["3023pr0001"] == "planned"
    assert coverage.decorated_status(None, "planned") is None  # not modeled yet
