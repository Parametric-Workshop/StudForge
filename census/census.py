"""Build the Rebrickable Census: a local SQLite copy of Rebrickable's data.

Reads a folder of Rebrickable CSV downloads (https://rebrickable.com/downloads/),
or downloads the latest one with --download, and writes:

  build/census.sqlite            (gitignored; rebuilt from the CSVs at any time)
  downloads/rebrickable/<date>/  (gitignored; the CSVs, when downloaded, and
                                 changes.txt, every change since the
                                 previous download)
  census/census-manifest.json    (committed; records which snapshot was used)

Each CSV becomes one table with the same name and columns, holding the values
exactly as downloaded (as text). No rules are applied here; census/condense.py
turns the census into the condensed census.

Usage:
  python3 census/census.py <path/to/rebrickable_csvs> [--date YYYY-MM-DD]
  python3 census/census.py --download

Data source: Rebrickable (https://rebrickable.com), free for personal and
commercial use with attribution.
"""

import argparse
import csv
import datetime
import hashlib
import json
import os
import sqlite3
import time
import urllib.error
import urllib.request
import zipfile
from collections.abc import Iterator
from pathlib import Path

# The repository root and the census database; the other census scripts
# import these from here.
REPO = Path(__file__).resolve().parent.parent
DB_PATH = REPO / "build" / "census.sqlite"
MANIFEST_PATH = REPO / "census" / "census-manifest.json"

# Rebrickable's archive of every CSV. Rebrickable allows downloading it
# automatically at most once a day (scraping its web pages is banned), so the
# time of each download is saved and a second one within a day is refused.
ARCHIVE_URL = "https://cdn.rebrickable.com/media/downloads/all_downloads.zip"
DOWNLOAD_DIR = REPO / "downloads" / "rebrickable"
LAST_DOWNLOAD_PATH = DOWNLOAD_DIR / "last_download.txt"
DOWNLOAD_INTERVAL = datetime.timedelta(days=1)
MB = 1_000_000  # bytes, for progress messages and reading files to hash
EXAMPLES = 3  # changes shown on screen of each kind; changes.txt has them all

# Every CSV in Rebrickable's downloads; each becomes a table of the same name.
SOURCE_FILES = [
    "color_mappings.csv",
    "colors.csv",
    "elements.csv",
    "inventories.csv",
    "inventory_minifigs.csv",
    "inventory_parts.csv",
    "inventory_sets.csv",
    "minifigs.csv",
    "part_categories.csv",
    "part_mappings.csv",
    "part_relationships.csv",
    "parts.csv",
    "set_mappings.csv",
    "sets.csv",
    "themes.csv",
]

# Columns that queries look up often: (table, column).
INDEXES = [
    ("inventory_parts", "inventory_id"),
    ("inventory_parts", "part_num"),
    ("inventory_minifigs", "inventory_id"),
    ("part_relationships", "child_part_num"),
    ("part_relationships", "parent_part_num"),
    ("elements", "part_num"),
]


def sha256(path: Path) -> str:
    """Return the SHA-256 hash of a file, read 1 MB at a time."""
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(MB), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_csv(db: sqlite3.Connection, path: Path) -> int:
    """Copy one CSV into a table named after the file; return its row count."""
    table = path.stem
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        columns = next(reader)
        db.execute(f'CREATE TABLE "{table}" ({", ".join(columns)})')
        placeholders = ",".join("?" * len(columns))
        db.executemany(f'INSERT INTO "{table}" VALUES ({placeholders})', reader)
    return db.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]


def read_table(db: sqlite3.Connection, table: str) -> Iterator[dict[str, str]]:
    """Yield each row of a census table as a dict keyed by column name."""
    cursor = db.execute(f'SELECT * FROM "{table}"')
    columns = [c[0] for c in cursor.description]
    for row in cursor:
        yield dict(zip(columns, row, strict=True))


def now_text() -> str:
    """Return the local date and time to the minute, such as 2026-10-26 22:19."""
    return datetime.datetime.now().isoformat(sep=" ", timespec="minutes")


def create_census(
    source: Path, db_path: Path, snapshot_date: str, manifest_sha256: str = ""
) -> dict[str, int]:
    """Create the census database from a snapshot; return each table's row count.

    The census is always rebuilt from scratch, so stale rows can't survive.
    manifest_sha256 is the checksum of the manifest written for this snapshot,
    which census_viewer.py compares with the committed one.
    """
    db_path.parent.mkdir(exist_ok=True)
    db_path.unlink(missing_ok=True)
    db = sqlite3.connect(db_path)
    counts = {Path(name).stem: load_csv(db, source / name) for name in SOURCE_FILES}
    for table, column in INDEXES:
        db.execute(f"CREATE INDEX {table}_{column} ON {table} ({column})")
    db.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    db.executemany(
        "INSERT INTO meta VALUES (?,?)",
        [
            ("source", "Rebrickable"),
            ("snapshot_date", snapshot_date),
            ("built_at", now_text()),
            ("manifest sha256", manifest_sha256),
        ],
    )
    db.commit()  # without this, sqlite discards everything on close
    db.close()
    return counts


def check_download_allowed(
    now: datetime.datetime, last_download: datetime.datetime | None
) -> None:
    """Stop if the archive was downloaded less than a day ago."""
    if last_download is not None and now - last_download < DOWNLOAD_INTERVAL:
        allowed = last_download + DOWNLOAD_INTERVAL
        raise SystemExit(
            f"The archive was last downloaded at {last_download:%Y-%m-%d %H:%M} UTC. "
            "Rebrickable allows one download a day, so the next one is allowed "
            f"from {allowed:%Y-%m-%d %H:%M} UTC."
        )


def check_complete(names: list[str], where: str) -> None:
    """Stop unless every file in SOURCE_FILES is among these file names."""
    missing = [f for f in SOURCE_FILES if f not in names]
    if missing:
        raise SystemExit(f"Missing in {where}: {', '.join(missing)}")


def show_progress(blocks: int, block_size: int, total_size: int) -> None:
    """Print how much of the archive has arrived, rewriting one line.

    urllib calls this after each block it downloads. total_size is -1 when
    the server doesn't say how big the file is.
    """
    done = blocks * block_size
    if total_size > 0:
        done = min(done, total_size)
        status = f"{done / MB:.1f} of {total_size / MB:.1f} MB"
    else:
        status = f"{done / MB:.1f} MB"
    # "\r" returns to the start of the line, so each message replaces the last.
    print(f"\rDownloading {ARCHIVE_URL}: {status}", end="", flush=True)


def download_snapshot() -> tuple[Path, str]:
    """Download Rebrickable's archive and unzip it; return its folder and date."""
    last_download = None
    if LAST_DOWNLOAD_PATH.exists():
        last_download = datetime.datetime.fromisoformat(LAST_DOWNLOAD_PATH.read_text())
    now = datetime.datetime.now(datetime.UTC)
    check_download_allowed(now, last_download)

    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    archive = DOWNLOAD_DIR / "all_downloads.zip"
    start = time.perf_counter()
    try:
        urllib.request.urlretrieve(ARCHIVE_URL, archive, show_progress)
    except urllib.error.URLError as error:
        raise SystemExit(
            f"\nCouldn't download {ARCHIVE_URL} ({error.reason})"
        ) from error
    LAST_DOWNLOAD_PATH.write_text(now.isoformat())
    size = archive.stat().st_size / MB
    print(f"\nDownloaded {size:.1f} MB in {time.perf_counter() - start:.1f} s")

    with zipfile.ZipFile(archive) as zip_file:
        check_complete(zip_file.namelist(), "the archive")
        # Rebrickable stamps each file in the archive with when it exported it.
        snapshot_date = datetime.date(*zip_file.getinfo("parts.csv").date_time[:3])
        folder = DOWNLOAD_DIR / snapshot_date.isoformat()
        # Extract only the files the census reads, by name. Unzipping stamps
        # each file with the current time, so give it back its export time:
        # building from this folder later finds the snapshot date by itself.
        for name in SOURCE_FILES:
            exported = datetime.datetime(*zip_file.getinfo(name).date_time).timestamp()
            os.utime(zip_file.extract(name, folder), (exported, exported))
    archive.unlink()  # the extracted CSVs are the copy we keep
    report_changes(folder)
    return folder, snapshot_date.isoformat()


def previous_snapshot(folder: Path) -> Path | None:
    """Return the newest downloaded snapshot older than this one, if any.

    Snapshot folders are named by date, so sorting their names sorts them by age.
    """
    older = [p for p in DOWNLOAD_DIR.iterdir() if p.is_dir() and p.name < folder.name]
    return max(older, default=None)


def count_rows(path: Path) -> int:
    """Return how many rows a CSV holds, not counting its header."""
    with open(path, newline="", encoding="utf-8") as f:
        return sum(1 for _ in csv.reader(f)) - 1


def part_names(folder: Path) -> dict[str, str]:
    """Return each part number in a snapshot, with its name."""
    with open(folder / "parts.csv", newline="", encoding="utf-8") as f:
        return {row["part_num"]: row["name"] for row in csv.DictReader(f)}


def part_number_changes(old: Path, new: Path) -> dict[str, list[str]]:
    """Return the part numbers added, removed and renamed between two snapshots."""
    before, after = part_names(old), part_names(new)
    kept = sorted(before.keys() & after.keys())
    return {
        "New part numbers": [
            f"{p}  {after[p]}" for p in sorted(after.keys() - before.keys())
        ],
        "Removed part numbers": [
            f"{p}  {before[p]}" for p in sorted(before.keys() - after.keys())
        ],
        "Renamed part numbers": [
            f"{p}  {before[p]} -> {after[p]}" for p in kept if before[p] != after[p]
        ],
    }


def report_changes(new: Path) -> None:
    """Print how a snapshot differs from the one before, and save every change.

    changes.txt in the new snapshot's folder gets the row counts and the full
    lists of part number changes.
    """
    old = previous_snapshot(new)
    if old is None:
        print("No earlier snapshot in downloads/rebrickable/ to compare with")
        return
    lines = [f"Changes since the {old.name} snapshot:"]
    print(lines[0])
    for name in SOURCE_FILES:
        before, after = count_rows(old / name), count_rows(new / name)
        if before != after:
            line = f"  {Path(name).stem}: {before:,} -> {after:,} ({after - before:+,})"
            print(line)
            lines.append(line)
    lines.append("")
    for kind, changes in part_number_changes(old, new).items():
        print(f"  {kind}: {len(changes):,}")
        for change in changes[:EXAMPLES]:
            print(f"    {change}")
        lines += [f"{kind} ({len(changes):,}):", *changes, ""]
    changes_path = new / "changes.txt"
    changes_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  Every change: {changes_path.relative_to(REPO)}")


def check_snapshot_folder(source: Path) -> str:
    """Stop if a folder lacks any CSV; return when its parts.csv was exported."""
    check_complete([p.name for p in source.glob("*")], str(source))
    modified = (source / "parts.csv").stat().st_mtime
    return datetime.date.fromtimestamp(modified).isoformat()


def build_census(source: Path, snapshot_date: str) -> None:
    """Write the manifest for a folder of CSVs, then build the census from it."""
    manifest = {
        "source": "Rebrickable (https://rebrickable.com/downloads/)",
        "snapshot_date": snapshot_date,
        "files": {f: sha256(source / f) for f in SOURCE_FILES},
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n")

    print("Building the census database...", flush=True)
    start = time.perf_counter()
    counts = create_census(source, DB_PATH, snapshot_date, sha256(MANIFEST_PATH))
    seconds = time.perf_counter() - start

    print(
        f"Rebrickable Census {snapshot_date}: {len(counts)} tables, "
        f"{sum(counts.values()):,} rows, built in {seconds:.1f} s"
    )
    print(f"  database: {DB_PATH.relative_to(REPO)}")
    print(f"  manifest: {MANIFEST_PATH.relative_to(REPO)}")


# --- Keeping the census current -------------------------------------------------

# Rebrickable updates its downloads daily, but shapes change slowly, so the
# scripts only suggest a new download once the snapshot is this old.
OLD_SNAPSHOT_DAYS = 30


def bring_census_up_to_date() -> None:
    """Report the census's state, and rebuild it if it doesn't match the manifest.

    census/condense.py and census/census_viewer.py call this before they read
    the census, so either one works on a fresh clone.
    """
    if not census_is_current(read_meta()):
        rebuild_census()
    warn_if_old(read_meta())


def read_meta() -> dict[str, str]:
    """Return the census's meta table, or an empty dict if there's no census yet."""
    if not DB_PATH.exists():
        return {}
    db = sqlite3.connect(DB_PATH)
    meta = dict(db.execute("SELECT key, value FROM meta"))
    db.close()
    return meta


def manifest_snapshot() -> str:
    """Return the date of the snapshot the committed manifest records."""
    return json.loads(MANIFEST_PATH.read_text())["snapshot_date"]


def census_is_current(meta: dict[str, str]) -> bool:
    """Report whether the census was built from the snapshot in the manifest.

    The manifest is committed, so after pulling a new snapshot's manifest the
    local census no longer matches it.
    """
    if not meta:
        print(f"Census: {DB_PATH.relative_to(REPO)} not found; building it")
        return False
    snapshot = meta["snapshot_date"]
    if meta.get("manifest sha256") != sha256(MANIFEST_PATH):
        print(
            f"Census: built from the {snapshot} snapshot, but {MANIFEST_PATH.name} "
            f"records the {manifest_snapshot()} snapshot; rebuilding"
        )
        return False
    age = snapshot_age(meta)
    print(
        f"Census: Rebrickable snapshot {snapshot} ({age} {days(age)} old), built "
        f"{meta['built_at']}; matches {MANIFEST_PATH.name}, no rebuild needed"
    )
    return True


def snapshot_age(meta: dict[str, str]) -> int:
    """Return how many days ago Rebrickable exported the census's snapshot."""
    exported = datetime.date.fromisoformat(meta["snapshot_date"])
    return (datetime.date.today() - exported).days


def days(count: int) -> str:
    """Return "day" or "days" to follow a count."""
    return "day" if count == 1 else "days"


def warn_if_old(meta: dict[str, str]) -> None:
    """Suggest downloading a newer snapshot once the census's is a month old."""
    age = snapshot_age(meta)
    if age > OLD_SNAPSHOT_DAYS:
        print(
            f"Census: the snapshot is {age} days old; run "
            "python3 census/census.py --download for the latest"
        )


def rebuild_census() -> None:
    """Build the census from the manifest's snapshot, downloading if it isn't here.

    Rebrickable only offers its latest snapshot, so a download can bring a newer
    one than the manifest records; the manifest is then rewritten to match.
    """
    expected = manifest_snapshot()
    local_copy = DOWNLOAD_DIR / expected
    if local_copy.exists():
        print(f"Census: building from {local_copy.relative_to(REPO)}")
        check_snapshot_folder(local_copy)
        build_census(local_copy, expected)
    else:
        print(
            f"Census: no local CSVs for the {expected} snapshot; "
            "downloading the latest instead."
        )
        folder, downloaded = download_snapshot()
        build_census(folder, downloaded)
        if downloaded != expected:
            print(
                f"Downloaded the {downloaded} snapshot; {MANIFEST_PATH.name} "
                "now differs from the committed one."
            )
    print()


def main() -> None:
    """Parse arguments, create the census database and write the manifest."""
    parser = argparse.ArgumentParser(
        description="Build the Rebrickable Census database.",
        epilog="The source folder must contain:"
        + "".join(f"\n   {f}" for f in SOURCE_FILES),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "source", type=Path, nargs="?", help="folder of Rebrickable CSV downloads"
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="download the latest snapshot instead (at most once a day)",
    )
    parser.add_argument(
        "--date",
        help="snapshot date (YYYY-MM-DD); defaults to when parts.csv was exported",
    )
    args = parser.parse_args()
    if args.download == (args.source is not None):
        parser.error("give either a folder of Rebrickable CSVs or --download")

    if args.download:
        source, exported = download_snapshot()
    else:
        source = args.source
        exported = check_snapshot_folder(source)
    build_census(source, args.date or exported)


if __name__ == "__main__":
    main()
