"""Download a snapshot: the latest from Rebrickable, or one this project published.

Rebrickable allows downloading its archive automatically at most once a day
(scraping its web pages is banned), so the time of each download is saved and a
second one within a day is refused.
"""

import datetime
import os
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from census.importing.snapshot import SOURCE_FILES, check_complete
from census.store import archive
from census.store.files import ARCHIVE_DIR, DOWNLOAD_DIR, MB

# Rebrickable's archive of every CSV.
ARCHIVE_URL = "https://cdn.rebrickable.com/media/downloads/all_downloads.zip"
LAST_DOWNLOAD_PATH = DOWNLOAD_DIR / "last_download.txt"
DOWNLOAD_INTERVAL = datetime.timedelta(days=1)
# Where the daily update publishes each snapshot's archive (see store/archive.py).
RELEASE_URL = (
    "https://github.com/Parametric-Workshop/StudForge/releases/download/"
    "census-{date}/snapshot-{date}.tar.gz"
)


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
    zipped = DOWNLOAD_DIR / "all_downloads.zip"
    start = time.perf_counter()
    try:
        urllib.request.urlretrieve(ARCHIVE_URL, zipped, show_progress)
    except urllib.error.URLError as error:
        raise SystemExit(
            f"\nCouldn't download {ARCHIVE_URL} ({error.reason})"
        ) from error
    LAST_DOWNLOAD_PATH.write_text(now.isoformat())
    size = zipped.stat().st_size / MB
    print(f"\nDownloaded {size:.1f} MB in {time.perf_counter() - start:.1f} s")

    with zipfile.ZipFile(zipped) as zip_file:
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
    zipped.unlink()  # the extracted CSVs are the copy we keep
    return folder, snapshot_date.isoformat()


def fetch_published_snapshot(snapshot_date: str) -> bool:
    """Download a snapshot's archive from its GitHub release, if it isn't here.

    Returns whether the archive is now in the archive folder. The daily update
    publishes one release per snapshot and thins old ones, so an old date may be
    gone.
    """
    target = archive.archive_path(ARCHIVE_DIR, archive.SNAPSHOT, snapshot_date)
    if target.exists():
        return True
    url = RELEASE_URL.format(date=snapshot_date)
    part = target.with_name(target.name + ".part")
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        urllib.request.urlretrieve(url, part)
    except urllib.error.URLError:
        part.unlink(missing_ok=True)
        return False
    part.replace(target)
    print(f"Census: fetched the {snapshot_date} snapshot from its GitHub release")
    return True
