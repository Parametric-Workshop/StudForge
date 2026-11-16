"""The block family's table of real shapes, and coverage.csv, agree."""

import csv
from pathlib import Path

from freecad_generator.families.block_shapes import load_block_shapes

COVERAGE_CSV = Path(__file__).parents[2] / "coverage" / "coverage.csv"
SHAPES = load_block_shapes()


def test_every_row_is_a_sensible_size() -> None:
    """At least one stud each way, Width the shorter side, at least one plate tall."""
    for part_num, size in SHAPES.items():
        assert 1 <= size.Width <= size.Length, part_num
        assert size.Height >= 1, part_num


def test_the_table_and_coverage_list_the_same_shapes() -> None:
    """Each shape here is in coverage.csv as family "block", and each such row is here.

    coverage.csv's part numbers are checked against the census when the census
    viewer loads it, so this also holds the table to real part numbers.
    """
    with COVERAGE_CSV.open(newline="", encoding="utf-8") as file:
        block = {
            row["part_num"] for row in csv.DictReader(file) if row["family"] == "block"
        }
    assert set(SHAPES) == block
