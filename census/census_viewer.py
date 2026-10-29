"""Build the census viewer: a drill-down page of the census tree.

Loads the condensed census, builds the census tree (census/tree.py), prints
a summary (census/summary.py) and writes the viewer page.

Before building, it brings the census up to date (see
bring_census_up_to_date in census/census.py). Then, if a rule file in
census/condense.py's RULE_FILES changed since the census was last condensed,
it condenses it again.

Reads:
  build/census.sqlite          (built by census/census.py, then census/condense.py)
  census/census-manifest.json  the snapshot the census should hold
  census/groups.toml          category groups
  census/families.toml        family rules
  coverage/coverage.csv       status of each shape and decorated shape tracked
  census/viewer_template.html the page, before the data goes in

Writes:
  build/census_viewer.html     the viewer page (loads its libraries from jsDelivr)

Usage:
  python3 census/census_viewer.py [--out PATH]
"""

import argparse
import json
import re
import sqlite3
from pathlib import Path

import condense
import condensed_census
import coverage
from census import DB_PATH, REPO, bring_census_up_to_date, read_meta
from condensed_census import Assembly, DecoratedShape, Shape, count_part_numbers
from coverage import (
    DECORATED_STATUSES,
    STATUSES,
    Statuses,
    group_by_status,
    in_group,
)
from summary import print_summary
from tree import Node, build_tree, find, load_groupings

TEMPLATE_PATH = REPO / "census" / "viewer_template.html"
GLOSSARY_PATH = REPO / "GLOSSARY.md"

# A GLOSSARY.md entry: "**Term**:" on one line, its definition on the next.
GLOSSARY_ENTRY = re.compile(r"^\*\*(.+?)\*\*:\n(.+)$", re.MULTILINE)
OUT_PATH = REPO / "build" / "census_viewer.html"


# --- Keeping the condensed census current ---------------------------------------


def check_condensed(meta: dict[str, str]) -> dict[str, str]:
    """Condense the census again if it never was, or a rule file changed.

    Returns the census details (the meta table), read again after condensing.
    """
    changed = condense.changed_rule_files(meta)
    if "condensed_at" not in meta:
        reason = "not condensed yet"
    elif changed:
        reason = f"changed since {meta['condensed_at']}: {', '.join(changed)}"
    else:
        print(
            f"Condensed census: condensed {meta['condensed_at']}; "
            "rule files unchanged, no condensing needed\n"
        )
        return meta
    print(f"Condensed census: {reason}; condensing again")
    condense.condense_census()
    print()
    return read_meta()


# --- Output: viewer --------------------------------------------------------------

# One viewer card, as JSON for d3-org-chart.
ViewerNode = dict[str, str | int | float | list[str] | None]


def share(part: float, whole: float) -> float:
    """Return part as a fraction of whole, or 0 when whole is 0."""
    return part / whole if whole else 0.0


def group_fields(
    node: Node, candidates: Node | None, status_of: Statuses
) -> ViewerNode:
    """Return a group card's counts, shares and coverage.

    Shares are out of all candidates, so only cards under Candidates get them.
    """
    by_status = group_by_status(node.shapes, STATUSES, status_of)
    covered = in_group(by_status, "covered")
    decorated = node.decorated
    decorated_by_status = group_by_status(decorated, DECORATED_STATUSES, status_of)
    fields: ViewerNode = {
        "shapes": node.shape_count,
        "usage": node.usage,
        "inProgress": len(in_group(by_status, "in progress")),
        "covered": len(covered),
        "decorated": len(decorated),
        "decoratedCovered": len(in_group(decorated_by_status, "covered")),
    }
    if candidates is not None:
        fields |= {
            "shapeShare": share(node.shape_count, candidates.shape_count),
            "usageShare": share(node.usage, candidates.usage),
            "coveredUsageShare": share(
                sum(shape.usage for shape in covered), candidates.usage
            ),
        }
    return fields


def shape_fields(
    shape: Shape, candidates: Node | None, status_of: Statuses
) -> ViewerNode:
    """Return a shape card's details."""
    fields: ViewerNode = {
        "status": status_of.get(shape.part_num),
        "usage": shape.usage,
        "reach": shape.reach,
        "years": shape.years,
        "decorated": len(shape.decorated),
        "assemblies": len(shape.assemblies),
    }
    if shape.unlisted:
        fields["unlisted"] = True
    if candidates is not None:
        fields["usageShare"] = share(shape.usage, candidates.usage)
    return fields


def decorated_fields(d: DecoratedShape, status_of: Statuses) -> ViewerNode:
    """Return a decorated shape card's details."""
    return {
        "status": status_of.get(d.part_num),
        "usage": d.usage,
        "reach": d.reach,
        "years": d.years,
    }


def assembly_fields(assembly: Assembly, status_of: Statuses) -> ViewerNode:
    """Return an assembly card's details."""
    return {
        "status": status_of.get(assembly.part_num),
        "members": assembly.members,
        "decorated": len(assembly.decorated),
    }


def node_record(
    node: Node,
    node_id: str,
    parent_id: str | None,
    candidates: Node | None,
    status_of: Statuses,
) -> ViewerNode:
    """Return one card's record. Pass candidates only for cards under Candidates."""
    item = node.record
    card: ViewerNode = {
        "id": node_id,
        "parentId": parent_id,
        "label": node.label,
        "sub": node.note,
        **({"footer": node.footer} if node.footer else {}),
        "kind": node.kind,
        "image": (item.image or None) if item else None,
    }
    if isinstance(item, Shape):
        return card | shape_fields(item, candidates, status_of)
    if isinstance(item, DecoratedShape):
        return card | decorated_fields(item, status_of)
    if isinstance(item, Assembly):
        return card | assembly_fields(item, status_of)
    return card | group_fields(node, candidates, status_of)


def viewer_nodes(root: Node, status_of: Statuses) -> list[ViewerNode]:
    """Flatten the tree into the id/parentId records d3-org-chart expects."""
    candidates = find(root, "Candidates")
    out: list[ViewerNode] = []

    def visit(node: Node, parent_id: str | None, in_candidates: bool) -> None:
        node_id = str(len(out))
        in_candidates = in_candidates or node is candidates
        share_base = candidates if in_candidates else None
        out.append(node_record(node, node_id, parent_id, share_base, status_of))
        for child in node.children:
            visit(child, node_id, in_candidates)

    visit(root, None, False)
    return out


def load_glossary(path: Path = GLOSSARY_PATH) -> dict[str, str]:
    """Return each GLOSSARY.md term, in lower case, with its definition.

    The page shows these as tooltips on the terms its cards use.
    """
    text = path.read_text(encoding="utf-8")
    return {
        term.lower(): definition.replace("`", "")
        for term, definition in GLOSSARY_ENTRY.findall(text)
    }


def write_viewer(root: Node, status_of: Statuses, out_path: Path) -> None:
    """Write the viewer page: the template with the tree data filled in."""
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    template = template.replace("/*GLOSSARY*/null", json.dumps(load_glossary()))
    page = template.replace("/*DATA*/null", json.dumps(viewer_nodes(root, status_of)))
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(page, encoding="utf-8")


def main() -> None:
    """Build the tree, print the summary and write the viewer."""
    parser = argparse.ArgumentParser(description="Build the census tree and viewer.")
    parser.add_argument(
        "--out", type=Path, default=OUT_PATH, help="where to write the viewer"
    )
    args = parser.parse_args()
    bring_census_up_to_date()
    meta = check_condensed(read_meta())
    db = sqlite3.connect(DB_PATH)
    census = condensed_census.read(db)
    status_of = coverage.load(census)
    coverage.write_table(db, status_of)
    db.commit()  # without this, sqlite discards the coverage table on close
    db.close()
    numbers = count_part_numbers(census)
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
    write_viewer(root, status_of, args.out)
    print(f"\nViewer: {args.out}")


if __name__ == "__main__":
    main()
