"""Write the census viewer: a drill-down page of the census tree.

The page is viewer_template.html, in this folder, with the tree's cards and the
glossary's definitions filled in. It loads its libraries from jsDelivr.
"""

import json
import re
from pathlib import Path

from census.coverage.statuses import (
    DECORATED_STATUSES,
    STATUSES,
    Statuses,
    group_by_status,
    in_group,
)
from census.coverage.tree import Node, find
from census.store.census_db import Assembly, DecoratedShape, Shape
from census.store.files import REPO

TEMPLATE_PATH = Path(__file__).with_name("viewer_template.html")
GLOSSARY_PATH = REPO / "GLOSSARY.md"

# A GLOSSARY.md entry: "**Term**:" on one line, its definition on the next.
GLOSSARY_ENTRY = re.compile(r"^\*\*(.+?)\*\*:\n(.+)$", re.MULTILINE)


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
