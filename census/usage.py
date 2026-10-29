"""Usage: how many of each shape the official sets use, set by set.

Only each set's latest inventory version counts, spares are left out, and a
minifig's shapes count once per minifig in the set. Assemblies and decorated
shapes count as the shapes they stand for (see census/folding.py), and each
decorated shape also gets a usage of its own.
"""

import sqlite3
from collections import Counter, defaultdict

from census import read_table
from folding import FoldingRules

# Usage broken down by set: per_set[part_num][set_num] = quantity, for every
# shape and every decorated shape. A decorated shape's quantity also counts
# toward its shape's.
PerSetUsage = dict[str, Counter[str]]
# An inventory line: (part_num, quantity).
Line = tuple[str, int]


def latest_inventory_ids(
    db: sqlite3.Connection,
) -> tuple[dict[str, str], dict[str, str]]:
    """Return the latest inventory id for each set and for each minifig.

    Rebrickable keeps corrected inventories as new versions; only the highest
    version counts. Minifig inventories have set numbers starting "fig-".
    """
    best: dict[str, tuple[str, int]] = {}  # number -> (inventory id, version)
    for r in read_table(db, "inventories"):
        number, version = r["set_num"], int(r["version"])
        if number not in best or version > best[number][1]:
            best[number] = (r["id"], version)
    sets = {n: inv for n, (inv, _) in best.items() if not n.startswith("fig-")}
    figs = {n: inv for n, (inv, _) in best.items() if n.startswith("fig-")}
    return sets, figs


def load_inventory_lines(db: sqlite3.Connection) -> dict[str, list[Line]]:
    """Return every inventory's lines, leaving out spares."""
    lines: defaultdict[str, list[Line]] = defaultdict(list)
    for r in read_table(db, "inventory_parts"):
        if r["is_spare"] == "False":
            lines[r["inventory_id"]].append((r["part_num"], int(r["quantity"])))
    return lines


def load_set_minifigs(
    db: sqlite3.Connection, set_inventories: set[str], fig_inventories: dict[str, str]
) -> dict[str, list[Line]]:
    """Return (minifig inventory id, quantity) pairs for each set inventory."""
    figs: defaultdict[str, list[Line]] = defaultdict(list)
    for r in read_table(db, "inventory_minifigs"):
        if r["inventory_id"] in set_inventories and r["fig_num"] in fig_inventories:
            fig_inv = fig_inventories[r["fig_num"]]
            figs[r["inventory_id"]].append((fig_inv, int(r["quantity"])))
    return figs


def set_lines(
    lines: dict[str, list[Line]], set_figs: dict[str, list[Line]], inv: str
) -> list[Line]:
    """Return a set inventory's lines, plus each minifig's lines times its quantity."""
    result = list(lines[inv])
    for fig_inv, fig_qty in set_figs[inv]:
        result += [(p, q * fig_qty) for p, q in lines[fig_inv]]
    return result


def count_usage(db: sqlite3.Connection, rules: FoldingRules) -> tuple[PerSetUsage, int]:
    """Count each shape's and decorated shape's quantity in each official set.

    Minifig shapes are included. Usage is the sum of the quantities; Reach is
    the number of sets. Also returns how many official sets were counted.
    """
    set_inventories, fig_inventories = latest_inventory_ids(db)
    lines = load_inventory_lines(db)
    set_figs = load_set_minifigs(db, set(set_inventories.values()), fig_inventories)
    per_set: PerSetUsage = defaultdict(Counter)
    for set_num, inv in set_inventories.items():
        for part_num, qty in set_lines(lines, set_figs, inv):
            if part_num in rules.decoration_parent:
                per_set[part_num][set_num] += qty
            for shape in rules.expand(part_num):
                per_set[shape][set_num] += qty
    return per_set, len(set_inventories)
