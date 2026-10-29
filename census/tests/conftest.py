"""Shared fixtures: a census built from the sample snapshot, and its rules.

The snapshot in census/tests/fixtures/sample_snapshot/ has one example of each rule:

- 3068bpr0001 is a decorated 3068b.
- 67401 is a decorated 3068b that is also an assembly containing 3068bpr0002.
  It must not turn the plain 3068b into an assembly.
- 3068b is a mold variant of 3068a, so both belong to the design 3068a.
- 4624c01 is an assembly of a wheel (4624) and a rubber tire (3641).
- 4624c01pr0001 is a decorated 4624c01 with no sub-parts of its own, so it
  expands like 4624c01.
- Five decorated shapes have no relationship row and fold by part number:
  970c00pr0001 into its plain 970c00, torsos 973c04h02pr0001 and
  973d14pr0001 into 3814, and 01642pr0001 and 01642pr0002 into an unlisted
  shape 01642. 250pr0001 (an HO Scale truck) stays, because 250 is an
  unrelated Duplo brick.
- Set 2000-1 has two inventory versions; only version 2 counts.
- Set 1000-1 lists one spare 3001, which doesn't count.
- Set 2000-1 contains two of minifig fig-000001, whose torso is 973.
- 3641 is a rubber tire (a candidate) and 0001 a paper sticker sheet (excluded).
"""

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

import census
import folding
import usage

SNAPSHOT = Path(__file__).parent / "fixtures" / "sample_snapshot"


@pytest.fixture(scope="module")
def db(tmp_path_factory: pytest.TempPathFactory) -> Iterator[sqlite3.Connection]:
    """A census database built from the sample snapshot."""
    db_path = tmp_path_factory.mktemp("census") / "census.sqlite"
    census.create_census(SNAPSHOT, db_path, "2026-10-23")
    connection = sqlite3.connect(db_path)
    yield connection
    connection.close()


@pytest.fixture(scope="module")
def rules(db: sqlite3.Connection) -> folding.FoldingRules:
    """Folding rules loaded from the sample census."""
    return folding.load_folding_rules(db)


@pytest.fixture(scope="module")
def per_set(db: sqlite3.Connection, rules: folding.FoldingRules) -> usage.PerSetUsage:
    """Usage per shape per set, counted from the sample census."""
    per_set, _ = usage.count_usage(db, rules)
    return per_set
