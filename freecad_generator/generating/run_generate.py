"""The generate operation, start to finish: a nominal FreeCAD and STEP file per shape.

Each shape in block_shapes.toml is the master body edited to its size, as a person
would, checked against block_rules.py, and saved under its part number in
build/freecad/nominal/, at its nominal size with no print offsets. Every file stays
fully editable: its Params hold the size, the nominal values and the print offsets.

A shape whose file was built from the same inputs (see part_files.build_key) is
left as it is, so only a change to the CAD rebuilds anything. The files are never
fitted to a printer: their print offsets stay 0, for a person to tune by hand.

A shape that fails its check isn't written; the run then returns 1. Runs in FreeCAD.
"""

from pathlib import Path

from freecad_generator.families.block import Master, build, edit, problems
from freecad_generator.families.block_rules import Size
from freecad_generator.families.block_shapes import load_block_shapes
from freecad_generator.store.nominal import load
from freecad_generator.store.part_files import (
    NOMINAL,
    build_key,
    remove,
    up_to_date,
    write,
)
from freecad_generator.store.print_offsets import Profile, applied, no_offsets

GENERATOR = Path(__file__).resolve().parents[1]
# What a nominal file's geometry and checks come from, besides its row.
SOURCES = [
    GENERATOR / name
    for name in (
        "families/block.py",
        "families/block_rules.py",
        "families/part_design.py",
        "store/nominal.toml",
        "store/print_offsets.toml",
    )
]


def generate(rebuild_all: bool) -> int:
    """Build every shape that changed; return 1 if any of them failed its check.

    With rebuild_all, every shape is built again, changed or not.
    """
    nominal, profile, shapes = load(), no_offsets(), load_block_shapes()
    master: Master | None = None  # built only once a shape needs it
    built = failures = 0
    for part_num, size in shapes.items():
        key = build_key(size, SOURCES)
        if not rebuild_all and up_to_date(NOMINAL / f"{part_num}.FCStd", key):
            continue
        if master is None:
            master = build(nominal, profile, size)
        edit(master, size, nominal, profile)
        found = problems(master, applied(nominal, profile), size)
        if found:
            failures += 1
            remove(part_num, NOMINAL)
            print(f"FAIL {part_num:8} {'; '.join(found)}", flush=True)
            continue
        about = describe(part_num, size, profile)
        write(master.doc, master.body, NOMINAL, key, about)
        built += 1
        print(f"ok   {part_num}", flush=True)
    unchanged = len(shapes) - built - failures
    print(f"built {built}, unchanged {unchanged}, failed {failures}, in {NOMINAL}")
    return 1 if failures else 0


def describe(part_num: str, size: Size, profile: Profile) -> list[str]:
    """What a STEP file holds, for its header: the part, its size and its fit."""
    features = "" if size.Studs else ", no studs"
    features += ", groove" if size.Groove else ""
    plates = "plate" if size.Height == 1 else "plates"
    return [
        f"StudForge {part_num}",
        f"block family: {size.Width} x {size.Length} studs, {size.Height} {plates}"
        f" tall{features}",
        f"print offsets: {profile.name}",
    ]
