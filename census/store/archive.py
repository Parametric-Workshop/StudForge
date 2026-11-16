"""Dated, compressed archives of the census, thinned as they age.

After every import, census/importing/archiving.py archives two things under
archive/census/:

  snapshot-2026-10-28.tar.gz    the Rebrickable CSVs, which can't be downloaded again
  census-2026-10-28.sqlite.gz   the census database as the import left it

Each archive is checked against its source before it counts as written. Archives are
then thinned on a fixed schedule (dates_to_keep), so their number stays small: recent
ones are kept close together and older ones further apart.

The daily update (.github/workflows/census.yml) publishes the same two files as a
GitHub release for each date, and thins the releases by the same schedule: run as a
script, this file reads release tags and prints the ones to delete.

Nothing here knows where the census keeps its files: every function is given its
folders, so the tests can run it all in a temporary one.
"""

import datetime
import gzip
import hashlib
import shutil
import tarfile
from collections.abc import Callable, Iterable
from pathlib import Path

# How many archives each rule keeps: the newest ones, then the newest of each recent
# month, quarter and half year. The newest of every year is kept for good.
KEEP_NEWEST = 3
KEEP_MONTHS = 3
KEEP_QUARTERS = 2
KEEP_HALF_YEARS = 2
# Uncompressed snapshot folders kept beside the archives: the current one, and the
# one before it, which the import compares it with.
KEEP_FOLDERS = 2

SNAPSHOT = ("snapshot-", ".tar.gz")
CENSUS = ("census-", ".sqlite.gz")
MB = 1024 * 1024
# The daily update publishes each date's archives as a GitHub release with this tag.
RELEASE_PREFIX = "census-"

Date = datetime.date
# A period a date falls in, such as (2026, 4) for the fourth quarter of 2026.
Period = tuple[int, int]


def month(day: Date) -> Period:
    """Return the month a date falls in."""
    return day.year, day.month


def quarter(day: Date) -> Period:
    """Return the quarter a date falls in."""
    return day.year, (day.month - 1) // 3


def half_year(day: Date) -> Period:
    """Return the half year a date falls in."""
    return day.year, (day.month - 1) // 6


def year(day: Date) -> Period:
    """Return the year a date falls in."""
    return day.year, 0


def dates_to_keep(dates: Iterable[Date]) -> set[Date]:
    """Return which archive dates the schedule keeps; the rest can go.

    Kept: the newest KEEP_NEWEST; the newest in each of the latest KEEP_MONTHS
    months, KEEP_QUARTERS quarters and KEEP_HALF_YEARS half years that have an
    archive; and the newest in every year. One date can satisfy several rules.
    """
    newest_first = sorted(set(dates), reverse=True)
    keep = set(newest_first[:KEEP_NEWEST])
    rules: list[tuple[Callable[[Date], Period], int | None]] = [
        (month, KEEP_MONTHS),
        (quarter, KEEP_QUARTERS),
        (half_year, KEEP_HALF_YEARS),
        (year, None),
    ]
    for period_of, limit in rules:
        periods: list[Period] = []
        for day in newest_first:
            if period_of(day) in periods:
                continue
            if limit is not None and len(periods) == limit:
                break
            periods.append(period_of(day))
            keep.add(day)
    return keep


# --- Writing and checking archives ----------------------------------------------


def archive_path(archive_dir: Path, kind: tuple[str, str], snapshot_date: str) -> Path:
    """Return where the archive of one kind and date goes."""
    prefix, suffix = kind
    return archive_dir / f"{prefix}{snapshot_date}{suffix}"


def archived(archive_dir: Path, kind: tuple[str, str]) -> dict[Date, Path]:
    """Return the archives of one kind that exist, by date."""
    prefix, suffix = kind
    found: dict[Date, Path] = {}
    for path in archive_dir.glob(f"{prefix}*{suffix}"):
        text = path.name.removeprefix(prefix).removesuffix(suffix)
        try:
            found[Date.fromisoformat(text)] = path
        except ValueError:
            continue  # not one of ours
    return found


def archive_snapshot(folder: Path, archive_dir: Path, snapshot_date: str) -> Path:
    """Archive a folder of Rebrickable CSVs, and check the archive holds them all.

    Returns the archive's path. An archive that fails its check is not kept.
    """
    target = archive_path(archive_dir, SNAPSHOT, snapshot_date)
    files = {p.name: p.stat().st_size for p in sorted(folder.iterdir()) if p.is_file()}
    part = target.with_name(target.name + ".part")
    archive_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(part, "w:gz") as tar:
        for name in files:
            tar.add(folder / name, arcname=name)
    with tarfile.open(part, "r:gz") as tar:
        stored = {member.name: member.size for member in tar.getmembers()}
    if stored != files:
        part.unlink()
        raise SystemExit(f"The archive of {folder} doesn't match it; not kept")
    part.replace(target)
    return target


def archive_census(db_path: Path, archive_dir: Path, snapshot_date: str) -> Path:
    """Archive the census database, and check the archive unpacks to the same bytes.

    Returns the archive's path. An archive that fails its check is not kept.
    """
    target = archive_path(archive_dir, CENSUS, snapshot_date)
    part = target.with_name(target.name + ".part")
    archive_dir.mkdir(parents=True, exist_ok=True)
    with open(db_path, "rb") as source, gzip.open(part, "wb") as packed:
        shutil.copyfileobj(source, packed, MB)
    with open(db_path, "rb") as source, gzip.open(part, "rb") as packed:
        same = checksum(source) == checksum(packed)
    if not same:
        part.unlink()
        raise SystemExit(f"The archive of {db_path} doesn't match it; not kept")
    part.replace(target)
    return target


def checksum(stream: Iterable[bytes]) -> str:
    """Return the SHA-256 of everything a file gives, read a piece at a time."""
    digest = hashlib.sha256()
    for piece in stream:
        digest.update(piece)
    return digest.hexdigest()


def restore_snapshot(
    archive_dir: Path, snapshot_date: str, download_dir: Path
) -> Path | None:
    """Unpack an archived snapshot into its dated folder; None if it isn't archived."""
    source = archive_path(archive_dir, SNAPSHOT, snapshot_date)
    if not source.exists():
        return None
    folder = download_dir / snapshot_date
    with tarfile.open(source, "r:gz") as tar:
        tar.extractall(folder, filter="data")
    return folder


# --- Thinning --------------------------------------------------------------------


def thin(archive_dir: Path) -> list[Path]:
    """Delete the archives the schedule no longer keeps; return what was deleted."""
    removed: list[Path] = []
    for kind in (SNAPSHOT, CENSUS):
        found = archived(archive_dir, kind)
        keep = dates_to_keep(found)
        for day, path in sorted(found.items()):
            if day not in keep:
                path.unlink()
                removed.append(path)
    return removed


def thin_folders(download_dir: Path, archive_dir: Path) -> list[Path]:
    """Delete old uncompressed snapshot folders; return what was deleted.

    The newest KEEP_FOLDERS stay. An older folder goes once it is archived, or once
    the schedule has stopped keeping its date. A folder that was never archived and
    whose date the schedule would keep is left alone.
    """
    folders: dict[Date, Path] = {}
    if not download_dir.exists():  # nothing was ever downloaded here
        return []
    for path in download_dir.iterdir():
        if path.is_dir():
            try:
                folders[Date.fromisoformat(path.name)] = path
            except ValueError:
                continue  # not a snapshot folder
    archives = archived(archive_dir, SNAPSHOT)
    wanted = dates_to_keep([*folders, *archives])
    removed: list[Path] = []
    for day in sorted(folders, reverse=True)[KEEP_FOLDERS:]:
        if day in archives or day not in wanted:
            shutil.rmtree(folders[day])
            removed.append(folders[day])
    return removed


def names_to_drop(names: Iterable[str], prefix: str) -> list[str]:
    """Return the names, of the form prefix + date, that the schedule drops.

    For thinning things kept somewhere else under dated names, such as the
    releases the daily update publishes. Names of any other form are ignored.
    """
    dated: dict[Date, str] = {}
    for name in names:
        try:
            dated[Date.fromisoformat(name.removeprefix(prefix))] = name
        except ValueError:
            continue
    keep = dates_to_keep(dated)
    return [name for day, name in sorted(dated.items()) if day not in keep]
