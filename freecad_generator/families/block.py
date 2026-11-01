"""Build the block family's master body: bricks and plates. Runs in FreeCAD.

Every size decision is an expression on the file's Params, so a person can open a
generated file, change Width, Length or Height there, and get a correct part (ADR
0003). block_rules.py states the same rules in plain Python, for checking. The
sketches, pads and patterns are made with part_design.py, shared by every family.
"""

from __future__ import annotations  # FreeCAD has no VarSet class to name at run time

from dataclasses import dataclass, fields
from pathlib import Path
from typing import cast

import FreeCAD as App
import Part
import Sketcher

from freecad_generator.families.block_rules import BRICK_HEIGHT, Size, box, volume
from freecad_generator.families.part_design import (
    P,
    circle,
    driven,
    extrude,
    grid_pattern,
    rectangle,
    show_result,
    sketch_on,
)
from freecad_generator.store.nominal import Nominal
from freecad_generator.store.print_offsets import Profile

PROFILE = "Profile"  # the Params property naming the filament profile
VOLUME_TOLERANCE = 0.01  # cubic millimeters, for problems()
BOX_TOLERANCE = 0.001  # millimeters

# The Rules group in Params: every rule and derived size, each written once as an
# expression, so a person sees in Params what a size gets and every feature refers
# to a rule by name. (name, property kind, expression). FreeCAD expressions have
# no `and` or `or` (and silently drop a `!`), so "and" is a product of
# comparisons, each 1 or 0. The modeled sizes (nominal plus print offset) are
# added before these, by add_rules.
RULES = [
    ("BodyHeight", "Length", f"{P}.Height * {P}.PlateHeight"),
    (
        "Ceiling",
        "Length",
        f"{P}.Height < {BRICK_HEIGHT} ? {P}.PlateCeiling : {P}.BrickCeiling",
    ),
    ("CavityHeight", "Length", f"{P}.BodyHeight - {P}.Ceiling"),
    # From a grid line in to the cavity's wall.
    ("Inset", "Length", f"({P}.Pitch - {P}.ModeledCavityWidth) / 2"),
    ("HasTubes", "Bool", f"({P}.Width >= 2) * ({P}.Length >= 2)"),
    # Pins on parts 1 stud wide, either way round; not on a 1 x 1.
    ("HasPins", "Bool", f"({P}.Width == 1) + ({P}.Length == 1) == 1"),
]

# Short names for the rules, as they read in an expression.
BODY_HEIGHT, CAVITY_HEIGHT, INSET = f"{P}.BodyHeight", f"{P}.CavityHeight", f"{P}.Inset"
HAS_TUBES, HAS_PINS = f"{P}.HasTubes", f"{P}.HasPins"


def modeled(name: str) -> str:
    """The size a nominal value is modeled at, with its print offset: a Rules name."""
    return f"{P}.Modeled{name}"


def outside(studs: str) -> str:
    """The outside's length over a number of studs, less the side clearance."""
    return f"{P}.{studs} * {P}.Pitch - 2 * {modeled('SideClearance')}"


def cavity(studs: str) -> str:
    """The cavity's length over a number of studs."""
    return f"{modeled('CavityWidth')} + ({P}.{studs} - 1) * {P}.Pitch"


def add_params(
    doc: App.Document, nominal: Nominal, profile: Profile, size: Size
) -> App.VarSet:
    """Add the Params VarSet: the size, every nominal value and every print offset."""
    params = doc.addObject("App::VarSet", P)
    for field in fields(size):
        params.addProperty("App::PropertyInteger", field.name, "Size")
        setattr(params, field.name, getattr(size, field.name))
    for field in fields(nominal):
        params.addProperty("App::PropertyLength", field.name, "Nominal")
        setattr(params, field.name, getattr(nominal, field.name))
    params.addProperty("App::PropertyString", PROFILE, "Print offsets")
    setattr(params, PROFILE, profile.name)
    for name, value in profile.offsets.items():
        # A distance, unlike a length, can be negative.
        params.addProperty("App::PropertyDistance", name, "Print offsets")
        setattr(params, name, value)
    add_rules(params, profile)
    return params


def add_rules(params: App.VarSet, profile: Profile) -> None:
    """Add the Rules group: the modeled sizes, then RULES, each read-only.

    A modeled size is a nominal value plus its print offset, such as
    ModeledStudDiameter; every expression uses these, never the bare nominal value.
    """
    sized = [
        (
            f"Modeled{name.removesuffix('Offset')}",
            "Length",
            f"{P}.{name.removesuffix('Offset')} + {P}.{name}",
        )
        for name in profile.offsets
    ]
    for name, kind, expression in [*sized, *RULES]:
        params.addProperty(f"App::Property{kind}", name, "Rules")
        params.setExpression(name, expression)
        params.setPropertyStatus(name, "ReadOnly")  # set by its expression only


def add_shell(body: App.Body) -> None:
    """The outside, padded up from the bottom, and the cavity pocketed up into it."""
    sketch = sketch_on(
        body,
        "OutsideSketch",
        "XY_Plane",
        {"x": modeled("SideClearance"), "y": modeled("SideClearance")},
    )
    rectangle(sketch, "Outside", outside("Length"), outside("Width"))
    extrude(body, "Outside", sketch, BODY_HEIGHT)

    sketch = sketch_on(body, "CavitySketch", "XY_Plane", {"x": INSET, "y": INSET})
    rectangle(sketch, "Cavity", cavity("Length"), cavity("Width"))
    extrude(body, "Cavity", sketch, CAVITY_HEIGHT, pocket=True)


def add_tubes(body: App.Body) -> None:
    """Tubes between every four studs, on parts at least 2 x 2: one tube, patterned.

    The tube and its bore are one sketch of two circles, padded up the cavity.
    """
    center = {"x": f"{P}.Pitch", "y": f"{P}.Pitch"}
    sketch = sketch_on(body, "TubeSketch", "XY_Plane", center)
    circle(sketch, "TubeOuterDiameter", modeled("TubeOuterDiameter"))
    circle(sketch, "TubeInnerDiameter", modeled("TubeInnerDiameter"))
    tube = extrude(body, "Tube", sketch, CAVITY_HEIGHT)
    tube.setExpression("Suppressed", f"not({HAS_TUBES})")
    grid_pattern(body, "Tubes", [tube], between=True, has=HAS_TUBES)


def add_pins(body: App.Body) -> None:
    """Pins between every two studs, on parts 1 stud wide: one pin, patterned.

    The first pin sits a pitch along the part's long side and half a pitch in from
    its short side, whichever way round the part is.
    """
    first = {
        axis: f"({P}.{studs} == 1 ? {P}.Pitch / 2 : {P}.Pitch)"
        for axis, studs in (("x", "Length"), ("y", "Width"))
    }
    sketch = sketch_on(body, "PinSketch", "XY_Plane", first)
    circle(sketch, "PinDiameter", modeled("PinDiameter"))
    pin = extrude(body, "Pin", sketch, CAVITY_HEIGHT)
    pin.setExpression("Suppressed", f"not({HAS_PINS})")
    grid_pattern(body, "Pins", [pin], between=True, has=HAS_PINS)


def stud_profile(sketch: App.SketchObject) -> None:
    """Half a stud's section, from its axis out, with the top edge chamfered.

    Five lines: across the bottom, up the side, the 45 degree chamfer, back across
    the top, and down the axis. Revolved about the sketch's vertical axis.
    """
    radius, height, chamfer = 2.4, 1.7, 0.2  # starting shape; Params sets the sizes
    corners = [
        App.Vector(0, 0),
        App.Vector(radius, 0),
        App.Vector(radius, height - chamfer),
        App.Vector(radius - chamfer, height),
        App.Vector(0, height),
    ]
    for i in range(5):
        sketch.addGeometry(Part.LineSegment(corners[i], corners[(i + 1) % 5]))
    for i in range(5):  # each line's end on the next line's start
        sketch.addConstraint(Sketcher.Constraint("Coincident", i, 2, (i + 1) % 5, 1))
    sketch.addConstraint(Sketcher.Constraint("Coincident", 0, 1, -1, 1))
    for line, direction in ((0, "Horizontal"), (1, "Vertical"), (3, "Horizontal")):
        sketch.addConstraint(Sketcher.Constraint(direction, line))
    sketch.addConstraint(Sketcher.Constraint("Vertical", 4))
    driven(
        sketch,
        Sketcher.Constraint("DistanceX", 0, 1, 0, 2, radius),
        "StudRadius",
        f"{modeled('StudDiameter')} / 2",
    )
    driven(
        sketch,
        Sketcher.Constraint("DistanceY", -1, 1, 3, 2, height),
        "StudHeight",
        f"{P}.StudHeight",
    )
    # The chamfer line's two ends: as far across as up, so 45 degrees.
    driven(
        sketch,
        Sketcher.Constraint("DistanceX", 2, 2, 2, 1, chamfer),
        "StudChamferAcross",
        f"{P}.StudChamfer",
    )
    driven(
        sketch,
        Sketcher.Constraint("DistanceY", 2, 1, 2, 2, chamfer),
        "StudChamferUp",
        f"{P}.StudChamfer",
    )


def add_studs(body: App.Body) -> None:
    """A stud on every grid square: one revolved stud, patterned.

    The profile is sketched on the XZ plane, where the sketch's x is the body's x,
    its y the body's z, and the offset's z runs along the plane's normal, the
    body's -y.
    """
    sketch = sketch_on(
        body,
        "StudSketch",
        "XZ_Plane",
        {"x": f"{P}.Pitch / 2", "y": BODY_HEIGHT, "z": f"-{P}.Pitch / 2"},
    )
    stud_profile(sketch)
    stud = body.newObject("PartDesign::Revolution", "Stud")
    stud.Profile = sketch
    stud.ReferenceAxis = (sketch, ["V_Axis"])
    stud.Angle = 360
    grid_pattern(body, "Studs", [stud], between=False)


# Sizes between them switching on every pattern: tubes on a 2 x 6 brick, pins on a
# 1 x 4 brick (see build).
WARM_UP = [Size(Width=2, Length=6, Height=3), Size(Width=1, Length=4, Height=3)]


@dataclass(frozen=True)
class Master:
    """A block family document: its Params and its one body."""

    doc: App.Document
    params: App.VarSet
    body: App.Body


def open_master(path: Path) -> Master:
    """Open a saved block family file, as a person would."""
    doc = App.openDocument(str(path))
    params = cast("App.VarSet", doc.getObject(P))
    body = cast("App.Body", doc.getObject("Body"))
    return Master(doc, params, body)


def build(nominal: Nominal, profile: Profile, size: Size) -> Master:
    """A new document holding the master body, at the given size and fit.

    The body is first recomputed at WARM_UP sizes, so every pattern makes a shape
    once while it's switched on. FreeCAD 26.3 (RC2) passes nothing through a
    pattern that was suppressed before it ever made a shape, emptying the body.
    """
    doc = App.newDocument("block")
    params = add_params(doc, nominal, profile, WARM_UP[0])
    body = doc.addObject("PartDesign::Body", "Body")
    add_shell(body)
    add_tubes(body)
    add_pins(body)
    add_studs(body)
    doc.recompute()
    master = Master(doc, params, body)
    for warm_up in [*WARM_UP[1:], size]:
        edit(master, warm_up, nominal, profile)
    show_result(doc, body)
    return master


def edit(master: Master, size: Size, nominal: Nominal, profile: Profile) -> None:
    """Change Params' size, nominal values and offsets, as a person would; recompute."""
    for values in (size, nominal):
        for field in fields(values):
            setattr(master.params, field.name, getattr(values, field.name))
    setattr(master.params, PROFILE, profile.name)
    for name, value in profile.offsets.items():
        setattr(master.params, name, value)
    master.doc.recompute()


def rule(master: Master, name: str) -> float:
    """A rule's value from the file's Params: a size in mm, or 1 or 0 for yes or no."""
    value = getattr(master.params, name)
    return float(getattr(value, "Value", value))  # sizes come as a Quantity


def problems(master: Master, nominal: Nominal, size: Size) -> list[str]:
    """What's wrong with the master body at this size, if anything.

    `nominal` is the sizes it's modeled at: nominal values plus any print offsets.
    """
    found: list[str] = []
    broken = [o.Name for o in master.doc.Objects if "Invalid" in o.State]
    if broken:
        found.append(f"errors in {', '.join(broken)}")
    shape = master.body.Shape
    if not shape.isValid():
        found.append("not a valid shape")
    if len(shape.Solids) != 1:
        found.append(f"{len(shape.Solids)} solids")
    if abs(shape.Volume - volume(nominal, size)) > VOLUME_TOLERANCE:
        found.append(f"volume {shape.Volume:.3f}, expected {volume(nominal, size):.3f}")
    bounds = shape.optimalBoundingBox()  # BoundBox pads curved faces
    actual = (bounds.XLength, bounds.YLength, bounds.ZLength)
    expected = box(nominal, size)
    if any(abs(a - e) > BOX_TOLERANCE for a, e in zip(actual, expected, strict=True)):
        found.append(f"box {actual}, expected {expected}")
    return found
