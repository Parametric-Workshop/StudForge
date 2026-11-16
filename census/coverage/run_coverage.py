"""The coverage operation, start to finish.

Works out each shape's status, builds the census tree, prints the summary and
writes the viewer. Each step's work is in its own module of this folder.
"""

from pathlib import Path

from census.coverage import statuses
from census.coverage.summary import print_summary
from census.coverage.tree import build_tree, load_groupings
from census.coverage.viewer import write_viewer
from census.store import census_db
from census.store.files import VIEWER_PATH


def report_coverage(out_path: Path = VIEWER_PATH) -> None:
    """Work out coverage, build the census tree, print the summary, write the viewer."""
    meta = census_db.read_meta()
    db = census_db.open_census()
    census = census_db.read(db)
    status_of = statuses.load(census)
    census_db.write_coverage(db, status_of)
    db.close()
    numbers = census_db.count_part_numbers(census)
    # The root card: what the condensed census made of every part number.
    title = f"Rebrickable part numbers: {numbers.total:,}"
    note = "\n".join(
        [
            f"{numbers.shapes:,} shapes",
            f"{numbers.decorated:,} decorated shapes",
            f"{numbers.assemblies:,} assemblies",
        ]
    )
    footer = f"Rebrickable snapshot {meta['snapshot_date']}"
    root = build_tree(census.shapes, title, note, footer, load_groupings())

    print_summary(root, numbers, status_of)
    write_viewer(root, status_of, out_path)
    print(f"\nViewer: {out_path}")
