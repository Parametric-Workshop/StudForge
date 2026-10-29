"""Build the condensed census from the Rebrickable Census.

Reads the census tables in build/census.sqlite (built by census/census.py, or
rebuilt first if it's missing or out of date) and writes the condensed census
into the same database. Condensing doesn't re-read the CSVs, so rule changes
are quick to try.

The steps, each with its rules in its own module:
  1. census/folding.py: which part numbers are one shape.
  2. census/usage.py: how many of each shape the official sets use.
  3. census/candidates.py: each shape's brick system, and whether it's a
     candidate or excluded. Every shape is kept, so the viewer can show what
     is left out and why.
  4. This file: each shape's and decorated shape's details (photo, LDraw IDs,
     years), then the tables.

Terms follow GLOSSARY.md.

Usage:
  python3 census/condense.py
"""

import sqlite3
import sys
from collections import Counter, defaultdict

import condensed_census
from candidates import brick_system, exclusion
from census import (
    DB_PATH,
    REPO,
    bring_census_up_to_date,
    now_text,
    read_table,
    sha256,
)
from condensed_census import (
    Assembly,
    CondensedCensus,
    DecoratedShape,
    Shape,
    ShapeSet,
    count_part_numbers,
)
from folding import (
    MAX_ASSEMBLY_DEPTH,
    FoldingRules,
    group_designs,
    load_folding_rules,
)
from usage import PerSetUsage, count_usage

CENSUS_DIR = REPO / "census"

# The files whose rules shape the condensed census. Their checksums are saved
# with it, so census_viewer.py can tell when it needs condensing again.
RULE_FILES = [
    "condense.py",
    "condensed_census.py",
    "folding.py",
    "usage.py",
    "candidates.py",
]

# Where Rebrickable keeps an element's photo; inventory photo URLs follow it.
ELEMENT_PHOTO = "https://cdn.rebrickable.com/media/parts/elements/{}.jpg"

# A set's name and release year.
SetInfo = tuple[str, int]


# --- Building the records --------------------------------------------------------


def load_sets(db: sqlite3.Connection) -> dict[str, SetInfo]:
    """Return each set's (name, release year)."""
    return {r["set_num"]: (r["name"], int(r["year"])) for r in read_table(db, "sets")}


def load_images(
    db: sqlite3.Connection, rules: FoldingRules
) -> tuple[dict[str, str], dict[str, str]]:
    """Return one photo URL per shape, and one per decorated shape.

    A shape's own photo from an inventory line wins; failing that, a photo of
    one of its decorated shapes; failing that, the photo of its highest-numbered
    element. A decorated shape has no fallback to its shape: a plain photo
    would hide what the decoration looks like.

    Shapes that only reach sets inside an assembly (2550, the monkey body in
    2550c01) have no inventory line of their own, so they need the elements.
    Newer, higher-numbered elements are far more likely to have a photo: in
    the 2026-10-23 snapshot, 60% of 7-digit element photos appear in
    Rebrickable's inventories, against 28% of 6-digit ones.
    """
    listed: dict[str, str] = {}  # each part number's first photo in an inventory
    for r in read_table(db, "inventory_parts"):
        if r["img_url"]:
            listed.setdefault(r["part_num"], r["img_url"])
    elements: dict[str, str] = {}
    for r in read_table(db, "elements"):
        part_num, element = r["part_num"], r["element_id"]
        current = elements.get(part_num)
        if current is None or (len(element), element) > (len(current), current):
            elements[part_num] = element
    element_photos = {p: ELEMENT_PHOTO.format(e) for p, e in elements.items()}

    own: dict[str, str] = {}
    borrowed: dict[str, str] = {}  # a decorated shape's photo, for its shape
    for part_num, url in listed.items():
        shape = rules.shape_of(part_num)
        target = own if shape == part_num else borrowed
        target.setdefault(shape, url)
    shapes = element_photos | borrowed | own  # later sources override earlier ones
    decorated = {
        p: listed.get(p) or element_photos.get(p, "") for p in rules.decoration_parent
    }
    return shapes, decorated


def load_ldraw_ids(db: sqlite3.Connection) -> dict[str, list[str]]:
    """Return the LDraw file names Rebrickable maps to each part number."""
    ldraw: defaultdict[str, list[str]] = defaultdict(list)
    for r in read_table(db, "part_mappings"):
        if r["ext_system"] == "LD":
            ldraw[r["part_num"]].append(r["ext_id"])
    return ldraw


def usage_in_sets(
    part_num: str, per_set: PerSetUsage, sets: dict[str, SetInfo]
) -> tuple[int, int, int | None, int | None]:
    """Return a part number's usage, reach, and first and last year in a set.

    The years are None for a part number no official set uses.
    """
    set_counts = per_set.get(part_num, Counter())
    years = [sets[s][1] for s in set_counts if s in sets]
    first_year, last_year = (min(years), max(years)) if years else (None, None)
    return sum(set_counts.values()), len(set_counts), first_year, last_year


def make_shapes_and_assemblies(
    db: sqlite3.Connection,
    rules: FoldingRules,
    per_set: PerSetUsage,
    sets: dict[str, SetInfo],
    images: dict[str, str],
) -> tuple[list[Shape], list[Assembly]]:
    """Return a Shape or an Assembly for each undecorated part number."""
    categories = {r["id"]: r["name"] for r in read_table(db, "part_categories")}
    designs = group_designs(rules)
    ldraw = load_ldraw_ids(db)
    shapes: list[Shape] = []
    assemblies: list[Assembly] = []
    for r in read_table(db, "parts"):
        part_num, name = r["part_num"], r["name"]
        shape = rules.decoration_parent.get(part_num, "")
        unlisted = rules.unlisted_shapes.get(shape) == part_num
        if unlisted:
            # Rebrickable doesn't list this shape, so its first decorated
            # shape's details stand in for it.
            part_num = shape
        elif part_num in rules.decoration_parent:
            continue
        category = categories.get(r["part_cat_id"], "")
        image = images.get(part_num, "")
        if part_num in rules.assemblies:
            # Assemblies carry no Usage of their own (ADR 0001).
            members = rules.assemblies[part_num]
            assemblies.append(Assembly(part_num, name, category, image, members))
            continue
        system = brick_system(name, category)
        reason = exclusion(system, category, r["part_material"])
        excluded, excluded_detail = reason if reason else (None, None)
        usage, reach, first_year, last_year = usage_in_sets(part_num, per_set, sets)
        shapes.append(
            Shape(
                part_num=part_num,
                name=name,
                category=category,
                design=designs.get(part_num, part_num),
                usage=usage,
                reach=reach,
                first_year=first_year,
                last_year=last_year,
                ldraw_ids=" ".join(ldraw[part_num]),
                brick_system=system,
                excluded=excluded,
                excluded_detail=excluded_detail,
                image=image,
                unlisted=unlisted,
            )
        )
    return shapes, assemblies


def make_decorated_shapes(
    db: sqlite3.Connection,
    rules: FoldingRules,
    per_set: PerSetUsage,
    sets: dict[str, SetInfo],
    images: dict[str, str],
) -> list[DecoratedShape]:
    """Return every decorated shape, with its own usage and photo."""
    names = {r["part_num"]: r["name"] for r in read_table(db, "parts")}
    decorated: list[DecoratedShape] = []
    for part_num in rules.decoration_parent:
        usage, reach, first_year, last_year = usage_in_sets(part_num, per_set, sets)
        decorated.append(
            DecoratedShape(
                part_num=part_num,
                name=names.get(part_num, ""),
                folds_into=rules.shape_of(part_num),
                folded_by=rules.folded_by[part_num],
                usage=usage,
                reach=reach,
                first_year=first_year,
                last_year=last_year,
                image=images.get(part_num, ""),
            )
        )
    return decorated


def make_shape_sets(shapes: list[Shape], per_set: PerSetUsage) -> list[ShapeSet]:
    """Return each shape's quantity in each official set."""
    return [
        ShapeSet(shape.part_num, set_num, quantity)
        for shape in shapes
        for set_num, quantity in per_set.get(shape.part_num, Counter()).items()
    ]


# --- Condensing ------------------------------------------------------------------


def condense(db: sqlite3.Connection) -> tuple[int, int, int, int]:
    """Replace the condensed census tables, built from the census tables.

    Returns the number of shapes, candidate shapes, assemblies and official sets.
    """
    rules = load_folding_rules(db)
    per_set, official_sets = count_usage(db, rules)
    for part_num in sorted(rules.depth_limited):
        print(
            f"warning: assembly {part_num} nests more than {MAX_ASSEMBLY_DEPTH} levels "
            "deep (a loop in the data?); its usage was counted as a plain shape",
            file=sys.stderr,
        )
    sets = load_sets(db)
    shape_images, decorated_images = load_images(db, rules)
    shapes, assemblies = make_shapes_and_assemblies(
        db, rules, per_set, sets, shape_images
    )
    decorated = make_decorated_shapes(db, rules, per_set, sets, decorated_images)

    census = CondensedCensus(shapes, decorated, assemblies)
    # Every part number Rebrickable lists must become a shape, a decorated
    # shape or an assembly. Checked before writing, so a failure leaves the
    # previous condensed census in place.
    part_numbers = db.execute("SELECT COUNT(*) FROM parts").fetchone()[0]
    accounted = count_part_numbers(census).total
    if accounted != part_numbers:
        raise SystemExit(
            f"Rebrickable lists {part_numbers:,} part numbers, but the condensed "
            f"census accounts for {accounted:,}"
        )
    condensed_census.write(db, census, make_shape_sets(shapes, per_set))
    db.executemany(
        "INSERT OR REPLACE INTO meta VALUES (?,?)",
        [
            ("sets", str(official_sets)),
            ("part_numbers", str(part_numbers)),
            ("condensed_at", now_text()),
        ]
        + [(f"{name} sha256", checksum) for name, checksum in rule_checksums()],
    )
    db.commit()  # without this, sqlite discards everything on close

    candidates = sum(1 for shape in shapes if shape.excluded is None)
    return len(shapes), candidates, len(assemblies), official_sets


def rule_checksums() -> list[tuple[str, str]]:
    """Return (file name, SHA-256) for each file in RULE_FILES."""
    return [(name, sha256(CENSUS_DIR / name)) for name in RULE_FILES]


def changed_rule_files(meta: dict[str, str]) -> list[str]:
    """Return the rule files that changed since the census was last condensed.

    meta is the census's meta table. A census that was never condensed has
    no checksums, so every rule file counts as changed.
    """
    return [
        name
        for name, checksum in rule_checksums()
        if meta.get(f"{name} sha256") != checksum
    ]


def condense_census() -> None:
    """Build the condensed census and print what it holds."""
    db = sqlite3.connect(DB_PATH)
    shapes, candidates, assemblies, official_sets = condense(db)
    snapshot_date = db.execute(
        "SELECT value FROM meta WHERE key = 'snapshot_date'"
    ).fetchone()[0]
    db.close()
    print(
        f"Condensed census {snapshot_date}: {shapes:,} shapes ({candidates:,} "
        f"candidates) and {assemblies:,} assemblies, from {official_sets:,} "
        "official sets"
    )
    print(f"  database: {DB_PATH.relative_to(REPO)}")


def main() -> None:
    """Bring the census up to date, then condense it."""
    bring_census_up_to_date()
    condense_census()


if __name__ == "__main__":
    main()
