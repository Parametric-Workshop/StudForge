"""The verify operation, start to finish: the edit check.

Checks that a block family file stays correct when a person edits its Params.

Builds the master body, saves it, and reopens the file from disk as a person
would. Then it changes the size the way they would in FreeCAD, one edit after
another, recomputing once each time. Every result must have no feature errors,
be one valid solid, match block_rules.py's volume and box, and be the same solid
as a fresh build at that size.

The edits run at nominal size, then with the profiles/elegoo-cc2-pla.toml print
offsets. The last is a 2 x 4 brick with those
offsets, saved to build/freecad/edit_check-<FreeCAD version>/block.FCStd.

It returns 1 if any edit fails. Runs in FreeCAD.
"""

from pathlib import Path

import FreeCAD as App
import Part

from freecad_generator.families.block import (
    BOX_TOLERANCE,
    VOLUME_TOLERANCE,
    Master,
    build,
    edit,
    open_master,
    problems,
    rule,
)
from freecad_generator.families.block_rules import (
    Size,
    body_height,
    ceiling,
    has_pins,
    has_tubes,
)
from freecad_generator.store.nominal import Nominal, load
from freecad_generator.store.part_files import save
from freecad_generator.store.print_offsets import (
    PROFILES,
    Profile,
    applied,
    load_profile,
    no_offsets,
)

# One folder per FreeCAD version, so a release candidate's file never replaces
# the 1.1.4 one.
VERSION = ".".join(App.Version()[:3])
OUTPUT = Path.cwd() / "build" / "freecad" / f"edit_check-{VERSION}" / "block.FCStd"

# What a person might type, in order: each edit starts from the one before it.
EDITS = [
    Size(Width=2, Length=4, Height=3),  # brick 2 x 4 (3001)
    Size(Width=1, Length=1, Height=3),  # brick 1 x 1 (3005)
    Size(Width=1, Length=2, Height=3),  # brick 1 x 2 (3004): pins come back
    Size(Width=4, Length=1, Height=3),  # brick 1 x 4, the other way round
    Size(Width=1, Length=4, Height=1),  # plate 1 x 4 (3710)
    Size(Width=2, Length=2, Height=3),  # brick 2 x 2 (3003): tubes come back
    Size(Width=3, Length=3, Height=1),  # plate 3 x 3 (11212)
    Size(Width=2, Length=4, Height=15),  # brick 2 x 4, five bricks tall
    Size(Width=2, Length=3, Height=3),  # brick 2 x 3 (3002)
    Size(Width=4, Length=6, Height=3),  # brick 4 x 6 (2356)
    Size(Width=1, Length=1, Height=1),  # plate 1 x 1 (3024)
    Size(Width=2, Length=4, Height=3),  # back to the brick 2 x 4
]
# Then with a filament profile's print offsets, ending on the brick 2 x 4.
WITH_PROFILE = [
    Size(Width=1, Length=4, Height=1),  # pins
    Size(Width=1, Length=1, Height=3),  # neither
    Size(Width=2, Length=4, Height=3),  # tubes
]
PROFILE = PROFILES / "elegoo-cc2-pla.toml"


def difference(first: Part.Shape, second: Part.Shape) -> float:
    """The volume where two solids differ, in cubic millimeters: 0 when they match.

    What's in the first and not the second, plus what's in the second and not the
    first. Unlike comparing volumes, it sees a feature in the wrong place.
    """
    return first.cut(second).Volume + second.cut(first).Volume


def rules_differ(master: Master, nominal: Nominal, size: Size) -> list[str]:
    """Compare the file's Rules in Params with block_rules.py's, one by one.

    Each rule is written twice, as an expression in the file and in Python; this is
    what keeps the two from drifting apart. `nominal` is the sizes it's modeled at.
    """
    expected: dict[str, float] = {
        "HasTubes": has_tubes(size),
        "HasPins": has_pins(size),
        "BodyHeight": body_height(nominal, size),
        "Ceiling": ceiling(nominal, size),
    }
    return [
        f"rule {name} is {rule(master, name)}, expected {value}"
        for name, value in expected.items()
        if abs(rule(master, name) - value) > BOX_TOLERANCE
    ]


def differs_from_fresh(
    master: Master, nominal: Nominal, profile: Profile, size: Size
) -> list[str]:
    """Compare the edited part with one built fresh at the same size and fit.

    The volume and box checks see a wrong rule; this sees a feature an edit left in
    the wrong place, which can keep the volume and the box the same.
    """
    fresh = build(nominal, profile, size)
    differ = difference(master.body.Shape, fresh.body.Shape)
    App.closeDocument(fresh.doc.Name)
    if differ > VOLUME_TOLERANCE:
        return [f"differs from a fresh build by {differ:.3f} mm^3"]
    return []


def run(master: Master, nominal: Nominal, profile: Profile, sizes: list[Size]) -> int:
    """Make each edit in turn and print how it went; return how many failed."""
    failures = 0
    for size in sizes:
        edit(master, size, nominal, profile)
        found = problems(master, applied(nominal, profile), size)
        found += rules_differ(master, applied(nominal, profile), size)
        found += differs_from_fresh(master, nominal, profile, size)
        failures += bool(found)
        status = "FAIL" if found else "ok  "
        print(f"{status} {label(size, profile):44} {'; '.join(found)}", flush=True)
    return failures


def label(size: Size, profile: Profile) -> str:
    """An edit as it's reported, such as "2 x 4 x 3 plates (nominal)"."""
    return f"{size.Width} x {size.Length} x {size.Height} plates ({profile.name})"


def verify() -> int:
    """Run every edit; return 1 if any of them failed."""
    nominal, plain = load(), no_offsets()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    built = build(nominal, plain, EDITS[0])
    save(built.doc, OUTPUT)
    App.closeDocument(built.doc.Name)
    master = open_master(OUTPUT)  # every edit is made to the file as reopened
    failures = run(master, nominal, plain, EDITS)
    failures += run(master, nominal, load_profile(PROFILE), WITH_PROFILE)
    total = len(EDITS) + len(WITH_PROFILE)
    save(master.doc, OUTPUT)
    print(f"{total - failures} of {total} edits ok; saved {OUTPUT}", flush=True)
    return 1 if failures else 0
