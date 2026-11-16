"""Archive what an import used and made, and thin what is no longer kept."""

from collections.abc import Iterable
from pathlib import Path

from census.store import archive
from census.store.files import ARCHIVE_DIR, DB_PATH, DOWNLOAD_DIR, REPO


def archive_import(source: Path, snapshot_date: str) -> None:
    """Archive the snapshot and the census just built from it, then thin old ones.

    Also archives any dated snapshot folder that has no archive yet, so none is
    thinned away before it was ever archived.
    """
    print("Archiving...", flush=True)
    archive.archive_snapshot(source, ARCHIVE_DIR, snapshot_date)
    have = archive.archived(ARCHIVE_DIR, archive.SNAPSHOT)
    for folder in sorted(p for p in DOWNLOAD_DIR.glob("*-*-*") if p.is_dir()):
        if folder.name not in {day.isoformat() for day in have}:
            archive.archive_snapshot(folder, ARCHIVE_DIR, folder.name)
    copy = archive.archive_census(DB_PATH, ARCHIVE_DIR, snapshot_date)
    removed = archive.thin(ARCHIVE_DIR) + archive.thin_folders(
        DOWNLOAD_DIR, ARCHIVE_DIR
    )
    print(f"  archive: {copy.parent.relative_to(REPO)}")
    for path in removed:
        print(f"  thinned: {path.relative_to(REPO)}")


def releases_to_drop(tags: Iterable[str]) -> list[str]:
    """Return the census release tags that the thinning schedule drops.

    The daily update publishes each snapshot as a release tagged census-<date>;
    tags of any other form are ignored.
    """
    return archive.names_to_drop(tags, archive.RELEASE_PREFIX)
