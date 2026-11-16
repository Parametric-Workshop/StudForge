"""Where the census keeps its files, and a checksum to tell when one changed."""

import hashlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CENSUS_DIR = REPO / "census"
# The census database. build/ is local only: built from a snapshot, never committed.
DB_PATH = REPO / "build" / "census.sqlite"
# Committed: records which snapshot the census should be built from.
MANIFEST_PATH = CENSUS_DIR / "census-manifest.json"
# Rebrickable snapshots, one folder per date. Local only.
DOWNLOAD_DIR = REPO / "downloads" / "rebrickable"
# Dated, compressed copies of every snapshot and census (see archive.py). Local only.
ARCHIVE_DIR = REPO / "archive" / "census"
# Each condense adds what it changed to this log (local only, like the census).
CHANGES_PATH = REPO / "build" / "census_changes.log"
# Where the viewer page is written unless a client names another place.
VIEWER_PATH = REPO / "build" / "census_viewer.html"
MB = 1_000_000  # bytes, for progress messages and reading files to hash


def sha256(path: Path) -> str:
    """Return the SHA-256 hash of a file, read 1 MB at a time."""
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(MB), b""):
            digest.update(chunk)
    return digest.hexdigest()
