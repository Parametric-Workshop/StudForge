"""Folding: which Rebrickable part numbers count as one shape.

Decorated shapes fold into their shape, mold variants and alternates group into
a Design, and Assemblies stand for the shapes inside them (see GLOSSARY.md and
docs/adr/0001-assemblies-are-not-shapes.md). census/condense.py applies these
rules to the census.
"""

import re
import sqlite3
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass, field

from census import read_table

# Rebrickable relationship types (part_relationships: rel_type, child, parent)
DECORATION_RELS = {"P", "T"}  # print, pattern: child is the parent, decorated
DESIGN_RELS = {"M", "A"}  # mold variant, alternate: same Design, different shape
ASSEMBLY_REL = "B"  # sub-part: child is a shape inside the parent Assembly

# Many decorated shapes have no relationship row. Their part number is still
# their shape's part number (the stem) plus Rebrickable's print (pr) or pattern
# (pat) suffix: 01642pr0001.
DECORATION_SUFFIX = re.compile(r"(.+?)(?:pr|pat)\d")
# Torso stems like 973c04h02 (arm and hand colors), 973d14 (odd arms) or
# 973g28c01h01 (dual-molded arms) are all the same molded torso, so they fold
# into the plain torso.
TORSO_STEM = re.compile(r"973[a-z][a-z0-9]*")
PLAIN_TORSO = "3814"

# Assemblies can contain Assemblies. Stop expanding past this depth, in case
# the data ever contains a loop. The deepest real nesting is 2 levels
# (2026-10-23 snapshot), so hitting this limit means the data has changed.
MAX_ASSEMBLY_DEPTH = 5


@dataclass
class FoldingRules:
    """How raw Rebrickable part numbers map onto condensed shapes."""

    # decorated shape's part number -> the part number it decorates
    decoration_parent: dict[str, str] = field(default_factory=dict)
    # decorated shape's part number -> how its shape was found: "relationship"
    # (a Rebrickable row), or by part number: "stem", "torso" or "unlisted"
    folded_by: dict[str, str] = field(default_factory=dict)
    # Unlisted shape the condensed census adds -> the decorated shape it copies
    unlisted_shapes: dict[str, str] = field(default_factory=dict)
    # pairs of part numbers that belong to the same Design
    design_links: list[tuple[str, str]] = field(default_factory=list)
    # Assembly part number (as written, not folded) -> its member shapes
    assemblies: dict[str, list[str]] = field(default_factory=dict)
    # Assemblies that hit MAX_ASSEMBLY_DEPTH while expanding (reported as warnings)
    depth_limited: set[str] = field(default_factory=set)

    def shape_of(self, part_num: str) -> str:
        """Follow decoration links up to the undecorated shape."""
        seen: set[str] = set()
        while part_num in self.decoration_parent and part_num not in seen:
            seen.add(part_num)  # guards against a loop in the data
            part_num = self.decoration_parent[part_num]
        return part_num

    def assembly_of(self, part_num: str) -> str | None:
        """Return the first Assembly on part_num's decoration chain, if any.

        A decorated assembly often has no sub-parts of its own (973c27h01pr5192
        is a decorated 973c27h01), so it stands for its base Assembly's members.
        """
        seen: set[str] = set()
        while part_num not in seen:
            if part_num in self.assemblies:
                return part_num
            seen.add(part_num)  # guards against a loop in the data
            if part_num not in self.decoration_parent:
                return None
            part_num = self.decoration_parent[part_num]
        return None

    def expand(self, part_num: str, depth: int = 0) -> Iterator[str]:
        """Yield the shapes that one unit of part_num stands for.

        An Assembly, or a decorated one, yields each of the Assembly's
        members (recursively); anything else yields its shape.
        """
        assembly = self.assembly_of(part_num)
        if assembly is None:
            yield self.shape_of(part_num)
        elif depth >= MAX_ASSEMBLY_DEPTH:
            # Deeper than any real assembly, most likely a loop in the data.
            # Count it as a plain shape, and record it for a warning.
            self.depth_limited.add(assembly)
            yield self.shape_of(assembly)
        else:
            for member in self.assemblies[assembly]:
                yield from self.expand(member, depth + 1)


def load_folding_rules(db: sqlite3.Connection) -> FoldingRules:
    """Sort part_relationships into decorated shapes, Designs and Assemblies."""
    rules = FoldingRules()
    members: defaultdict[str, list[str]] = defaultdict(list)
    for r in read_table(db, "part_relationships"):
        child, parent, rel = r["child_part_num"], r["parent_part_num"], r["rel_type"]
        if rel in DECORATION_RELS:
            rules.decoration_parent.setdefault(child, parent)
            rules.folded_by.setdefault(child, "relationship")
        elif rel in DESIGN_RELS:
            rules.design_links.append((child, parent))
        elif rel == ASSEMBLY_REL:
            members[parent].append(child)
    fold_by_part_number(rules, db)

    # Key Assemblies by their own part number, not folded: some decorated shapes
    # are Assemblies (e.g. 67401, a decorated 3068b with sub-parts), and folding
    # would wrongly turn the plain 3068b into one. Rebrickable doesn't record
    # how many of each member an Assembly holds, so each counts once.
    for assembly, children in members.items():
        rules.assemblies[assembly] = sorted({rules.shape_of(c) for c in children})
    return rules


def fold_by_part_number(rules: FoldingRules, db: sqlite3.Connection) -> None:
    """Fold decorated shapes that have no relationship row, by their part number.

    The stem is the part number before its pr or pat suffix. In order:
      - a stem that is a shape in the same category is the shape;
      - a torso stem (973c04h02, 973d14) folds into the plain torso;
      - a stem Rebrickable doesn't list becomes an unlisted shape, added
        here, because every version Rebrickable lists is decorated.
    A stem that is a shape in another category is a coincidence (250pr0001 is
    an HO Scale truck, 250 a Duplo brick), so that part number stays as it is.
    """
    categories = {r["part_num"]: r["part_cat_id"] for r in read_table(db, "parts")}
    for part_num in sorted(categories):  # sorted, so the first one found is stable
        match = DECORATION_SUFFIX.match(part_num)
        if part_num in rules.decoration_parent or not match:
            continue
        stem = match.group(1)
        if categories.get(stem) == categories[part_num]:
            base, how = stem, "stem"
        elif TORSO_STEM.fullmatch(stem):
            base, how = PLAIN_TORSO, "torso"
        elif stem not in categories:
            base, how = stem, "unlisted"
            rules.unlisted_shapes.setdefault(stem, part_num)
        else:
            continue
        rules.decoration_parent[part_num] = base
        rules.folded_by[part_num] = how


def find_root(roots: dict[str, str], part_num: str) -> str:
    """Return the representative shape of part_num's group (union-find)."""
    roots.setdefault(part_num, part_num)
    while roots[part_num] != part_num:
        roots[part_num] = roots[roots[part_num]]  # shortcut for later lookups
        part_num = roots[part_num]
    return part_num


def group_designs(rules: FoldingRules) -> dict[str, str]:
    """Group shapes into Designs; return each shape's Design name.

    A Design is named after its alphabetically first part number.
    """
    roots: dict[str, str] = {}
    for a, b in rules.design_links:
        root_a = find_root(roots, rules.shape_of(a))
        root_b = find_root(roots, rules.shape_of(b))
        if root_a != root_b:
            first, second = sorted((root_a, root_b))
            roots[second] = first
    return {shape: find_root(roots, shape) for shape in roots}
