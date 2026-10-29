"""Print a short summary of the census tree and candidate coverage.

The viewer page has the full breakdown; this is the quick check after a run.
"""

from condensed_census import PartNumbers
from coverage import (
    DECORATED_STATUSES,
    SHAPE_MODELED,
    STATUSES,
    Statuses,
    group_by_status,
    in_group,
)
from tree import Node, find

LABEL_WIDTH = 48


def print_summary(root: Node, numbers: PartNumbers, status_of: Statuses) -> None:
    """Print where every part number went, the shapes, and candidate coverage."""
    print_count("Part numbers", numbers.total)
    print_count("  shapes", numbers.shapes)
    print_count("  decorated shapes (folded into their shape)", numbers.decorated)
    print_count("  assemblies", numbers.assemblies)
    print_count("Unlisted shapes (added, no part number)", numbers.unlisted)
    print()
    print_count("Shapes", root.shape_count)
    for child in root.children:
        print_count(f"  {child.label.lower()}", child.shape_count)
    print()
    print_coverage(find(root, "Candidates"), status_of)


def print_count(label: str, count: int) -> None:
    """Print one label and its count."""
    print(f"{label:<{LABEL_WIDTH}}{count:>7,}")


def print_coverage(candidates: Node, status_of: Statuses) -> None:
    """Print one line of coverage for the candidate shapes, one for their decorated."""
    shapes_by_status = group_by_status(candidates.shapes, STATUSES, status_of)
    in_progress = in_group(shapes_by_status, "in progress")
    covered = in_group(shapes_by_status, "covered")
    usage = candidates.usage
    print(
        f"Coverage: {len(in_progress):,} of {candidates.shape_count:,} candidate "
        f"shapes in progress, {len(covered):,} covered "
        f"({sum(s.usage for s in in_progress) / usage:.2%} of usage in progress, "
        f"{sum(s.usage for s in covered) / usage:.2%} covered)"
    )

    decorated_by_status = group_by_status(
        candidates.decorated, DECORATED_STATUSES, status_of
    )
    in_progress_count = len(in_group(decorated_by_status, "in progress"))
    covered_count = len(in_group(decorated_by_status, "covered"))
    print(
        f"Decorated: {len(decorated_by_status[SHAPE_MODELED]):,} of "
        f"{len(candidates.decorated):,} decorated shapes on candidates shape "
        f"modeled, {in_progress_count:,} in progress, {covered_count:,} covered"
    )
