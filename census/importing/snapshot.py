"""Turn a folder of Rebrickable CSVs into the census database.

Each CSV becomes one table with the same name and columns, holding the values
exactly as downloaded (as text). No rules are applied here;
census/condensing/condense.py turns the census into the condensed census.

The manifest (census/census-manifest.json, committed) records which snapshot the
census was built from, with a checksum of every CSV.

Data source: Rebrickable (https://rebrickable.com), free for personal and
commercial use with attribution.
"""

import csv
import datetime
import json
from pathlib import Path

from census.store.census_db import (
    Census,
    add_index,
    commit,
    now_text,
    open_census,
    start_snapshot,
    write_meta,
    write_table,
)
from census.store.files import MANIFEST_PATH, sha256

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


def check_complete(names: list[str], where: str) -> None:
    """Stop unless every file in SOURCE_FILES is among these file names."""
    missing = [f for f in SOURCE_FILES if f not in names]
    if missing:
        raise SystemExit(f"Missing in {where}: {', '.join(missing)}")


def check_snapshot_folder(source: Path) -> str:
    """Stop if a folder lacks any CSV; return when its parts.csv was exported."""
    check_complete([p.name for p in source.glob("*")], str(source))
    modified = (source / "parts.csv").stat().st_mtime
    return datetime.date.fromtimestamp(modified).isoformat()


def write_manifest(source: Path, snapshot_date: str) -> None:
    """Record a snapshot in the manifest: its date and a checksum of every CSV."""
    manifest = {
        "source": "Rebrickable (https://rebrickable.com/downloads/)",
        "snapshot_date": snapshot_date,
        "files": {f: sha256(source / f) for f in SOURCE_FILES},
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n")


def manifest_snapshot() -> str:
    """Return the date of the snapshot the committed manifest records."""
    return json.loads(MANIFEST_PATH.read_text())["snapshot_date"]


def load_csv(db: Census, path: Path) -> int:
    """Copy one CSV into a table named after the file; return its row count."""
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        return write_table(db, path.stem, next(reader), reader)


def count_rows(path: Path) -> int:
    """Return how many rows a CSV holds, not counting its header."""
    with open(path, newline="", encoding="utf-8") as f:
        return sum(1 for _ in csv.reader(f)) - 1


def create_census(
    source: Path, db_path: Path, snapshot_date: str, manifest_sha256: str = ""
) -> dict[str, int]:
    """Create the census database from a snapshot; return each table's row count.

    In a census that already exists, this replaces the tables copied from
    Rebrickable and removes everything worked out from the old snapshot (the
    condensed tables, coverage and the build details), so nothing stale survives.
    Tables that don't come from a snapshot are kept. If the copy fails partway,
    the census is left holding the previous snapshot.
    manifest_sha256 is the checksum of the manifest written for this snapshot,
    which the client compares with the committed one.
    """
    db_path.parent.mkdir(exist_ok=True)
    db = open_census(db_path)
    try:
        start_snapshot(db, [Path(name).stem for name in SOURCE_FILES])
        counts = {Path(name).stem: load_csv(db, source / name) for name in SOURCE_FILES}
        for name in SOURCE_FILES:
            copied, listed = counts[Path(name).stem], count_rows(source / name)
            if copied != listed:
                raise SystemExit(
                    f"{name} has {listed:,} rows but {copied:,} were copied; "
                    "the census is left as it was"
                )
        for table, column in INDEXES:
            add_index(db, table, column)
        write_meta(
            db,
            {
                "source": "Rebrickable",
                "snapshot_date": snapshot_date,
                "built_at": now_text(),
                "manifest sha256": manifest_sha256,
            },
        )
        commit(db)  # until this, the census still holds the previous snapshot
    finally:
        db.close()  # closing without a commit undoes a failed import
    return counts
