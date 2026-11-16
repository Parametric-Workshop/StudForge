"""Tests for census/census.py: a plain copy of a Rebrickable snapshot."""

import csv
import datetime
import sqlite3
from pathlib import Path

import pytest

import census
import condense

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


def test_a_new_snapshot_replaces_the_old_ones_tables(tmp_path: Path) -> None:
    """A second build replaces the copied tables rather than adding to them."""
    db_path = tmp_path / "census.sqlite"
    census.create_census(SNAPSHOT, db_path, "2026-10-23")
    counts = census.create_census(SNAPSHOT, db_path, "2026-10-24")
    db = sqlite3.connect(db_path)
    assert db.execute("SELECT COUNT(*) FROM parts").fetchone()[0] == counts["parts"]
    snapshot = db.execute("SELECT value FROM meta WHERE key = 'snapshot_date'")
    assert snapshot.fetchone()[0] == "2026-10-24"
    db.close()


def test_a_new_snapshot_removes_what_was_worked_out_from_the_old_one(
    tmp_path: Path,
) -> None:
    """The condensed tables and their details go, so the census is condensed again."""
    db_path = tmp_path / "census.sqlite"
    census.create_census(SNAPSHOT, db_path, "2026-10-23")
    db = sqlite3.connect(db_path)
    condense.condense(db)
    db.close()

    census.create_census(SNAPSHOT, db_path, "2026-10-24")
    db = sqlite3.connect(db_path)
    tables = {name for (name,) in db.execute("SELECT name FROM sqlite_master")}
    meta = dict(db.execute("SELECT key, value FROM meta"))
    db.close()
    assert "condensed_shape" not in tables
    assert "condensed_at" not in meta


def test_a_new_snapshot_keeps_tables_that_are_not_from_a_snapshot(
    tmp_path: Path,
) -> None:
    """A table of StudForge's own survives a new snapshot, rows and all."""
    db_path = tmp_path / "census.sqlite"
    census.create_census(SNAPSHOT, db_path, "2026-10-23")
    db = sqlite3.connect(db_path)
    db.execute("CREATE TABLE library (part_num TEXT, build_key TEXT)")
    db.execute("INSERT INTO library VALUES ('3001', 'abc')")
    db.commit()
    db.close()

    census.create_census(SNAPSHOT, db_path, "2026-10-24")
    db = sqlite3.connect(db_path)
    assert db.execute("SELECT * FROM library").fetchall() == [("3001", "abc")]
    db.close()


def test_a_failed_import_leaves_the_previous_snapshot(tmp_path: Path) -> None:
    """If a CSV is missing, the census still holds the old snapshot, whole."""
    db_path = tmp_path / "census.sqlite"
    census.create_census(SNAPSHOT, db_path, "2026-10-23")
    with pytest.raises(FileNotFoundError):
        census.create_census(tmp_path / "no_such_folder", db_path, "2026-10-24")

    db = sqlite3.connect(db_path)
    snapshot = db.execute("SELECT value FROM meta WHERE key = 'snapshot_date'")
    assert snapshot.fetchone()[0] == "2026-10-23"
    assert db.execute("SELECT COUNT(*) FROM parts").fetchone()[0] > 0
    db.close()


def test_an_import_that_copies_the_wrong_number_of_rows_is_not_saved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each table's row count is checked against its CSV before anything is saved."""
    db_path = tmp_path / "census.sqlite"
    census.create_census(SNAPSHOT, db_path, "2026-10-23")

    def a_million(_path: Path) -> int:
        return 1_000_000

    monkeypatch.setattr(census, "count_rows", a_million)
    with pytest.raises(SystemExit, match="the census is left as it was"):
        census.create_census(SNAPSHOT, db_path, "2026-10-24")

    db = sqlite3.connect(db_path)
    snapshot = db.execute("SELECT value FROM meta WHERE key = 'snapshot_date'")
    assert snapshot.fetchone()[0] == "2026-10-23"
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
