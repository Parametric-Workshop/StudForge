"""Tests for census/census.py: a plain copy of a Rebrickable snapshot."""

import csv
import datetime
import sqlite3
from pathlib import Path

import pytest

import census

SNAPSHOT = Path(__file__).parent / "fixtures" / "sample_snapshot"


def test_every_csv_becomes_a_table_exactly_as_downloaded(tmp_path: Path) -> None:
    """Each table has its CSV's columns and rows, values unchanged."""
    db_path = tmp_path / "census.sqlite"
    counts = census.create_census(SNAPSHOT, db_path, "2026-10-23")
    assert set(counts) == {Path(name).stem for name in census.SOURCE_FILES}

    db = sqlite3.connect(db_path)
    for name in census.SOURCE_FILES:
        with open(SNAPSHOT / name, newline="", encoding="utf-8") as f:
            header, *lines = list(csv.reader(f))
        cursor = db.execute(f'SELECT * FROM "{Path(name).stem}"')
        assert [c[0] for c in cursor.description] == header, name
        assert [list(row) for row in cursor] == lines, name
    meta = dict(db.execute("SELECT key, value FROM meta"))
    db.close()
    built_at = meta.pop("built_at")  # the local time, which changes every run
    assert len(built_at) == len("2026-10-26 22:19")
    assert meta == {
        "source": "Rebrickable",
        "snapshot_date": "2026-10-23",
        "manifest sha256": "",
    }


def test_rebuilding_replaces_the_old_database(tmp_path: Path) -> None:
    """A second build starts from scratch rather than adding to the first."""
    db_path = tmp_path / "census.sqlite"
    census.create_census(SNAPSHOT, db_path, "2026-10-23")
    counts = census.create_census(SNAPSHOT, db_path, "2026-10-24")
    db = sqlite3.connect(db_path)
    assert db.execute("SELECT COUNT(*) FROM parts").fetchone()[0] == counts["parts"]
    db.close()


def test_part_number_changes_between_snapshots(tmp_path: Path) -> None:
    """A new snapshot's part numbers are sorted into added, removed and renamed."""
    for folder, rows in [
        ("old", ["3001,Brick 2 x 4", "3002,Brick 2 x 3", "3003,Brick 2 x 2"]),
        ("new", ["3001,Brick 2 x 4", "3002,Brick 2 x 3 Renamed", "3004,Brick"]),
    ]:
        (tmp_path / folder).mkdir()
        lines = ["part_num,name", *rows]
        (tmp_path / folder / "parts.csv").write_text("\n".join(lines) + "\n")
    assert census.part_number_changes(tmp_path / "old", tmp_path / "new") == {
        "New part numbers": ["3004  Brick"],
        "Removed part numbers": ["3003  Brick 2 x 2"],
        "Renamed part numbers": ["3002  Brick 2 x 3 -> Brick 2 x 3 Renamed"],
    }


def test_a_second_download_within_a_day_is_refused() -> None:
    """Rebrickable allows one automated download of its archive a day."""
    last = datetime.datetime(2026, 10, 26, 8, 0, tzinfo=datetime.UTC)
    census.check_download_allowed(last + datetime.timedelta(days=1), last)
    census.check_download_allowed(last, None)  # never downloaded
    with pytest.raises(SystemExit, match="from 2026-10-27 08:00 UTC"):
        census.check_download_allowed(last + datetime.timedelta(hours=23), last)
