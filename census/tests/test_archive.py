"""Tests for census/store/archive.py, in a temporary folder."""

import datetime
import gzip
from pathlib import Path

import pytest

from census.store import archive

Date = datetime.date


def days(start: Date, count: int) -> list[Date]:
    """A run of consecutive dates."""
    return [start + datetime.timedelta(days=n) for n in range(count)]


def test_the_schedule_keeps_recent_archives_close_and_old_ones_far_apart() -> None:
    """Two years of daily archives thin to eight, spaced out as they age."""
    keep = archive.dates_to_keep(days(Date(2025, 1, 1), 730))
    assert sorted(keep, reverse=True) == [
        Date(2026, 12, 31),  # the newest three; also this month, quarter, half, year
        Date(2026, 12, 30),
        Date(2026, 12, 29),
        Date(2026, 11, 30),  # the newest of each of the two months before
        Date(2026, 10, 31),
        Date(2026, 9, 30),  # the quarter before
        Date(2026, 6, 30),  # the half year before
        Date(2025, 12, 31),  # the year before
    ]


def test_a_few_archives_are_all_kept() -> None:
    """Nothing is thinned until there are more than the newest three."""
    few = days(Date(2026, 10, 26), 3)
    assert archive.dates_to_keep(few) == set(few)


def snapshot_folder(folder: Path) -> Path:
    """A made-up snapshot folder with two small files."""
    folder.mkdir(parents=True)
    (folder / "parts.csv").write_text("part_num,name\n3001,Brick 2 x 4\n")
    (folder / "colors.csv").write_text("id,name\n0,Black\n")
    return folder


def test_an_archived_snapshot_restores_to_the_same_files(tmp_path: Path) -> None:
    """What goes into a snapshot archive comes back out, byte for byte."""
    folder = snapshot_folder(tmp_path / "downloads" / "2026-10-28")
    target = archive.archive_snapshot(folder, tmp_path / "archive", "2026-10-28")
    assert target.name == "snapshot-2026-10-28.tar.gz"

    restored = archive.restore_snapshot(
        tmp_path / "archive", "2026-10-28", tmp_path / "restored"
    )
    assert restored is not None
    for name in ("parts.csv", "colors.csv"):
        assert (restored / name).read_bytes() == (folder / name).read_bytes()
    missing = archive.restore_snapshot(tmp_path / "archive", "2020-01-01", tmp_path)
    assert missing is None


def test_an_archived_census_unpacks_to_the_same_bytes(tmp_path: Path) -> None:
    """The database copy is checked when written, and reads back unchanged."""
    db_path = tmp_path / "census.sqlite"
    db_path.write_bytes(bytes(range(256)) * 4000)
    target = archive.archive_census(db_path, tmp_path / "archive", "2026-10-28")
    assert target.name == "census-2026-10-28.sqlite.gz"
    with gzip.open(target, "rb") as packed:
        assert packed.read() == db_path.read_bytes()
    assert not list((tmp_path / "archive").glob("*.part"))


def test_an_archive_that_does_not_match_its_source_is_not_kept(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed check stops the run and leaves no archive behind."""
    db_path = tmp_path / "census.sqlite"
    db_path.write_bytes(b"census")
    answers = iter(["one", "another"])

    def differing(_stream: object) -> str:
        return next(answers)

    monkeypatch.setattr(archive, "checksum", differing)
    with pytest.raises(SystemExit, match="doesn't match"):
        archive.archive_census(db_path, tmp_path / "archive", "2026-10-28")
    assert list((tmp_path / "archive").iterdir()) == []


def test_thinning_deletes_only_what_the_schedule_drops(tmp_path: Path) -> None:
    """Of five daily archives, the newest three stay; other files are untouched."""
    archive_dir = tmp_path / "archive"
    archive_dir.mkdir()
    for day in days(Date(2026, 10, 24), 5):
        archive.archive_path(archive_dir, archive.CENSUS, day.isoformat()).touch()
    (archive_dir / "notes.txt").touch()

    removed = archive.thin(archive_dir)
    assert [p.name for p in removed] == [
        "census-2026-10-24.sqlite.gz",
        "census-2026-10-25.sqlite.gz",
    ]
    assert len(list(archive_dir.iterdir())) == 4


def test_old_folders_go_only_once_archived(tmp_path: Path) -> None:
    """The two newest folders stay; an older one stays too until it is archived."""
    downloads, archive_dir = tmp_path / "downloads", tmp_path / "archive"
    for day in ("2026-10-26", "2026-10-27", "2026-10-28"):
        snapshot_folder(downloads / day)
    (downloads / "last_download.txt").touch()
    archive_dir.mkdir()

    assert archive.thin_folders(downloads, archive_dir) == []
    archive.archive_snapshot(downloads / "2026-10-26", archive_dir, "2026-10-26")
    removed = archive.thin_folders(downloads, archive_dir)
    assert [p.name for p in removed] == ["2026-10-26"]
    assert sorted(p.name for p in downloads.iterdir()) == [
        "2026-10-27",
        "2026-10-28",
        "last_download.txt",
    ]


def test_only_dated_names_with_the_prefix_are_thinned() -> None:
    """Release tags thin by the same schedule; other tags are never listed."""
    tags = [f"census-{day}" for day in days(Date(2026, 10, 24), 5)]
    dropped = archive.names_to_drop([*tags, "v1.0", "census-notes"], "census-")
    assert dropped == ["census-2026-10-24", "census-2026-10-25"]
