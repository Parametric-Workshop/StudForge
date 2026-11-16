"""What changed between one downloaded snapshot and the one before it.

After a download, the client prints the row counts that changed and the part
numbers added, removed and renamed, and saves every change to changes.txt in the
new snapshot's folder.
"""

import csv
from pathlib import Path

from census.importing.snapshot import SOURCE_FILES, count_rows
from census.store.files import DOWNLOAD_DIR, REPO

EXAMPLES = 3  # changes shown on screen of each kind; changes.txt has them all


def previous_snapshot(folder: Path) -> Path | None:
    """Return the newest downloaded snapshot older than this one, if any.

    Snapshot folders are named by date, so sorting their names sorts them by age.
    """
    older = [p for p in DOWNLOAD_DIR.iterdir() if p.is_dir() and p.name < folder.name]
    return max(older, default=None)


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
