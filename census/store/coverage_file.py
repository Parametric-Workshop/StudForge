"""The coverage file, coverage/coverage.csv: the status of each tracked part number."""

import csv
from pathlib import Path

from census.store.files import REPO

COVERAGE_PATH = REPO / "coverage" / "coverage.csv"


def read_coverage_file(path: Path = COVERAGE_PATH) -> dict[str, str]:
    """Return the status the file records for each part number, as written."""
    with open(path, newline="", encoding="utf-8") as f:
        return {row["part_num"]: row["status"] for row in csv.DictReader(f)}
