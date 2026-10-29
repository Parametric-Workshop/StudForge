"""The census tree: every shape, grouped level by level.

The levels, from the top:

  Part numbers (its note says what the condensed census made of them all)
    candidates / excluded
      brick system (candidates) or exclusion reason (excluded)
        category group (standard brick system only, from groups.toml)
          Rebrickable category
            family (only for categories listed in families.toml)
              shape
                decorated shape (each one that folds into the shape)
                assembly (each one the shape is in)
                  decorated shape (each one that folds into the assembly)

Down to the shapes, every node's shape count is the sum of its children's.
Shape share and usage share are always out of all candidate shapes, and
decorated shape share out of all decorated shapes on candidate shapes (see
GLOSSARY.md).

census/census_viewer.py builds the tree from the condensed census and shows it;
census/summary.py prints its top levels.
"""

import re
import tomllib
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from census import REPO
from condensed_census import Assembly, DecoratedShape, Shape

GROUPS_PATH = REPO / "census" / "groups.toml"
FAMILIES_PATH = REPO / "census" / "families.toml"

# The first "W x L" in a shape's name, used to order shapes by size in a family.
SIZE = re.compile(r"(\d+) x (\d+)")
# The size given to shapes with no "W x L" in their name, so they sort last.
UNSIZED = 999


@dataclass
class Node:
    """One box in the tree. Its shapes are every shape at or below it."""

    label: str
    kind: str  # root, candidates, group, family, shape, decorated or assembly
    note: str = ""
    shapes: list[Shape] = field(default_factory=list)
    children: list["Node"] = field(default_factory=list)
    record: Shape | DecoratedShape | Assembly | None = None  # what a leaf card shows
    footer: str = ""  # small print at the bottom of the card

    @property
    def shape_count(self) -> int:
        """Number of shapes at or below this node."""
        return len(self.shapes)

    @property
    def usage(self) -> int:
        """Total usage of the shapes at or below this node."""
        return sum(s.usage for s in self.shapes)

    @property
    def decorated(self) -> list[DecoratedShape]:
        """The decorated shapes on the shapes at or below this node."""
        return [d for s in self.shapes for d in s.decorated]

    def add(self, child: "Node") -> "Node":
        """Attach a child and return it."""
        self.children.append(child)
        return child


# --- Groupings -------------------------------------------------------------------


def load_groups(path: Path = GROUPS_PATH) -> dict[str, str]:
    """Return the category group of each Rebrickable category in groups.toml."""
    with open(path, "rb") as f:
        groups: dict[str, list[str]] = tomllib.load(f)["groups"]
    return {
        category: group
        for group, categories in groups.items()
        for category in categories
    }


# A family rule: (family name, words that select it). No words means "the rest".
FamilyRule = tuple[str, list[str]]


def load_family_rules(path: Path = FAMILIES_PATH) -> dict[str, list[FamilyRule]]:
    """Return the ordered family rules for each category in families.toml."""
    with open(path, "rb") as f:
        families: dict[str, list[dict[str, str | list[str]]]] = tomllib.load(f)[
            "family"
        ]
    rules: dict[str, list[FamilyRule]] = {}
    for category, entries in families.items():
        rules[category] = [(str(e["name"]), list(e["words"])) for e in entries]
    return rules


# --- Ordering and families -------------------------------------------------------


# A family rule word starting with this is a regular expression.
REGEX_PREFIX = "re:"


def word_matches(word: str, name: str) -> bool:
    """A rule word matches if it appears in the name, or as a regex matches it."""
    if word.startswith(REGEX_PREFIX):
        return re.search(word.removeprefix(REGEX_PREFIX), name) is not None
    return word in name


def family_of(rules: list[FamilyRule], name: str) -> str:
    """Return the first family whose words match the name (the last is the rest)."""
    for family, words in rules:
        if not words or any(word_matches(w, name) for w in words):
            return family
    return rules[-1][0]


def by_usage(shape: Shape) -> tuple[int, str]:
    """Order shapes from most to least used."""
    return (-shape.usage, shape.part_num)


def by_size(shape: Shape) -> tuple[int, int, int, str]:
    """Order by narrow side, then long side: 1x1, 1x2, 1x3 ... 2x2, 2x3 ...

    Old mold variants sort just after the current shape of the same size.
    """
    is_old_variant = shape.design != shape.part_num
    match = SIZE.search(shape.name)
    if not match:
        return (UNSIZED, UNSIZED, int(is_old_variant), shape.part_num)
    first, second = int(match.group(1)), int(match.group(2))
    return (min(first, second), max(first, second), int(is_old_variant), shape.part_num)


def split[T](items: list[T], key: Callable[[T], str]) -> dict[str, list[T]]:
    """Split items by a key, keeping their order within each piece."""
    pieces: dict[str, list[T]] = {}
    for item in items:
        pieces.setdefault(key(item), []).append(item)
    return pieces


def grouped(
    shapes: list[Shape], key: Callable[[Shape], str]
) -> list[tuple[str, list[Shape]]]:
    """Split shapes by a key, largest total usage first."""
    groups = split(shapes, key)
    return sorted(groups.items(), key=lambda kv: -sum(s.usage for s in kv[1]))


# --- Building the tree -----------------------------------------------------------

# How to order a list of shapes: by_usage or by_size.
SortKey = Callable[[Shape], tuple[int | str, ...]]


@dataclass
class Groupings:
    """The hand-maintained groupings: category groups and family rules."""

    groups: dict[str, str]  # Rebrickable category -> category group
    families: dict[str, list[FamilyRule]]  # Rebrickable category -> family rules


def load_groupings() -> Groupings:
    """Read groups.toml and families.toml."""
    return Groupings(load_groups(), load_family_rules())


def add_decorated_leaves(parent: Node, decorated: list[DecoratedShape]) -> None:
    """Attach one card per decorated shape, most used first."""
    for d in sorted(decorated, key=lambda d: (-d.usage, d.part_num)):
        parent.add(Node(d.part_num, "decorated", note=d.name, record=d))


def add_shape_leaves(parent: Node, shapes: list[Shape], order: SortKey) -> None:
    """Attach one card per shape, in the given order.

    Under each shape go its decorated shapes, then the assemblies it is in,
    each with the decorated shapes that fold into that assembly.
    """
    for shape in sorted(shapes, key=order):
        node = parent.add(
            Node(shape.part_num, "shape", note=shape.name, shapes=[shape], record=shape)
        )
        add_decorated_leaves(node, shape.decorated)
        for assembly in shape.assemblies:
            assembly_node = node.add(
                Node(assembly.part_num, "assembly", note=assembly.name, record=assembly)
            )
            add_decorated_leaves(assembly_node, assembly.decorated)


def add_category(
    parent: Node,
    category: str,
    shapes: list[Shape],
    groupings: Groupings,
) -> None:
    """Attach a category, with a family level if families.toml lists it."""
    node = parent.add(Node(category, "group", shapes=shapes))
    if category not in groupings.families:
        add_shape_leaves(node, shapes, by_usage)
        return
    rules = groupings.families[category]
    for family, family_shapes in grouped(shapes, lambda s: family_of(rules, s.name)):
        family_node = node.add(
            Node(
                family,
                "family",
                note="family: one parametric generator",
                shapes=family_shapes,
            )
        )
        add_shape_leaves(family_node, family_shapes, by_size)


def add_categories(parent: Node, shapes: list[Shape], groupings: Groupings) -> None:
    """Attach shapes by category."""
    for category, cat_shapes in grouped(shapes, lambda s: s.category):
        add_category(parent, category, cat_shapes, groupings)


def add_groups(parent: Node, shapes: list[Shape], groupings: Groupings) -> None:
    """Attach shapes by category group, then category."""
    for group, group_shapes in grouped(
        shapes, lambda s: groupings.groups.get(s.category, "Ungrouped")
    ):
        group_node = parent.add(Node(group, "group", shapes=group_shapes))
        add_categories(group_node, group_shapes, groupings)


def add_candidates(
    parent: Node,
    candidates: list[Shape],
    groupings: Groupings,
) -> None:
    """Attach candidates by brick system, then group (standard only) and category."""
    node = parent.add(Node("Candidates", "candidates", shapes=candidates))
    for system, system_shapes in grouped(candidates, lambda s: s.brick_system):
        system_node = node.add(Node(system.capitalize(), "group", shapes=system_shapes))
        if system == "standard":
            add_groups(system_node, system_shapes, groupings)
        else:
            add_categories(system_node, system_shapes, groupings)


def add_excluded(parent: Node, excluded: list[Shape]) -> None:
    """Attach excluded shapes by what they are, noting why they're excluded."""
    node = parent.add(Node("Excluded", "group", shapes=excluded))
    details = grouped(excluded, lambda s: s.excluded_detail or "")
    most_first = sorted(details, key=lambda detail: -len(detail[1]))
    for detail, detail_shapes in most_first:
        reason = detail_shapes[0].excluded or ""
        detail_node = node.add(
            Node(
                f"{detail[:1].upper()}{detail[1:]}",
                "group",
                note=reason,
                shapes=detail_shapes,
            )
        )
        add_shape_leaves(detail_node, detail_shapes, by_usage)


def build_tree(
    shapes: list[Shape], title: str, note: str, footer: str, groupings: Groupings
) -> Node:
    """Build the whole tree from the condensed shapes, under a root card."""
    root = Node(title, "root", note=note, shapes=shapes, footer=footer)
    add_candidates(root, [s for s in shapes if s.excluded is None], groupings)
    add_excluded(root, [s for s in shapes if s.excluded is not None])
    return root


def find(node: Node, label: str) -> Node:
    """Return the first node with this label, searching breadth-first."""
    queue = [node]
    while queue:
        current = queue.pop(0)
        if current.label == label:
            return current
        queue.extend(current.children)
    raise KeyError(label)
