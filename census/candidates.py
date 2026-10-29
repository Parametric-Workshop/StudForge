"""Which shapes StudForge aims to make: brick systems and exclusion rules.

These are project decisions, not facts from Rebrickable, so they live apart
from the folding in census/condense.py. Changing a rule here changes every
coverage figure, because candidates are the denominator for coverage.
"""

# Brick systems StudForge makes shapes for. Other systems don't connect to
# standard bricks (Modulex uses a 5 mm grid) or barely do (Quatro, Primo).
CANDIDATE_SYSTEMS = {"standard", "duplo"}

# Materials StudForge can print. Rubber and flexible plastic print in TPU.
PRINTABLE_MATERIALS = {"Plastic", "Flexible Plastic", "Rubber"}

# Rebrickable categories excluded whatever their material, and why.
EXCLUDED_CATEGORIES = {
    "Gear Parts": "merchandise",  # keychains, magnets, storage cases
    "HO Scale": "not compatible with standard LEGO",  # 1960s 1:87 model vehicles
    "Stickers": "not 3D printable",  # a cutting-machine add-on could cover them later
}


def brick_system(name: str, category: str) -> str:
    """Return the brick system a shape belongs to, from its category and name.

    Rebrickable files Duplo, Quatro and Primo under one category, and their
    accessories under others, but the system's name appears in the name.
    """
    if category == "Modulex":
        return "modulex"
    words = set(name.replace(",", " ").split())
    for system in ("Quatro", "Primo", "Duplo"):
        if system in words:
            return system.lower()
    if category.startswith("Duplo"):
        return "duplo"
    return "standard"


def exclusion(system: str, category: str, material: str) -> tuple[str, str] | None:
    """Return why StudForge won't make a shape, or None if it's a candidate.

    The answer comes as (reason, detail), e.g. ("not 3D printable", "cloth").
    """
    if system not in CANDIDATE_SYSTEMS:
        return ("not compatible with standard LEGO", system)
    if material not in PRINTABLE_MATERIALS:
        return ("not 3D printable", material.lower())
    if category in EXCLUDED_CATEGORIES:
        return (EXCLUDED_CATEGORIES[category], category)
    return None
