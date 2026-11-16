"""Build the block family's master body: bricks, plates and tiles. Runs in FreeCAD.

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

from freecad_generator.families.block_rules import (
    BRICK_HEIGHT,
    RIBBED_WIDTH,
    Size,
    box,
    volume,
)
from freecad_generator.families.part_design import (
    P,
    circle,
    driven,
    extrude,
    grid_pattern,
    rectangle,
    row_pattern,
    show_result,
    sketch_on,
)
from freecad_generator.store.nominal import Nominal
from freecad_generator.store.print_offsets import Profile

PROFILE = "Profile"  # the Params property naming the filament profile
VOLUME_TOLERANCE = 0.01  # cubic millimeters, for problems()
BOX_TOLERANCE = 0.001  # millimeters

RELIEF = f"{P}.ModeledGripRelief"  # per side, off the studs outside the grip band

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
    ("BandHeight", "Length", f"{P}.GripBandTop - {P}.GripBandBottom"),
    # The tube and pin outside the grip band, a relief narrower on each side.
    ("TubeRelievedDiameter", "Length", f"{P}.ModeledTubeOuterDiameter - 2 * {RELIEF}"),
    ("PinRelievedDiameter", "Length", f"{P}.ModeledPinDiameter - 2 * {RELIEF}"),
    ("HasTubes", "Bool", f"({P}.Width >= 2) * ({P}.Length >= 2)"),
    # Pins on parts 1 stud wide, either way round; not on a 1 x 1.
    ("HasPins", "Bool", f"({P}.Width == 1) + ({P}.Length == 1) == 1"),
    # A GripRelief of 0 gives plain walls, tubes and pins.
    ("HasGripBand", "Bool", f"{P}.ModeledGripRelief > 0"),
    (
        "HasRibs",
        "Bool",
        f"{P}.Ribs * ({P}.Height >= {BRICK_HEIGHT}) * ({P}.Width == {RIBBED_WIDTH})"
        f" * ({P}.Length >= 2)",
    ),
    # Which tubes have ribs: every other one, counting out from the center tube (or
    # from the two middle tubes, when there's an even number). Tube k sits k
    # pitches along (k = 1 to Length - 1). Two series, each a tube every two
    # pitches: the right-hand one starts at the center (or the right middle) tube;
    # the left-hand one ends two tubes left of the center (or at the left middle).
    ("RibsRightFirst", "Integer", f"floor(({P}.Length + 1) / 2)"),
    (
        "RibsRightCount",
        "Integer",
        f"floor(({P}.Length - 1 - {P}.RibsRightFirst) / 2) + 1",
    ),
    (
        "RibsLeftLast",
        "Integer",
        f"floor({P}.Length / 2) - (mod({P}.Length; 2) == 0 ? 2 : 0)",
    ),
    ("RibsLeftFirst", "Integer", f"2 - mod({P}.RibsLeftLast; 2)"),
    ("RibsLeftCount", "Integer", f"({P}.RibsLeftLast - {P}.RibsLeftFirst) / 2 + 1"),
    ("HasLeftRibs", "Bool", f"{P}.HasRibs * ({P}.RibsLeftLast >= 1)"),
    # From the wall's inside face above the band to the middle of the tube's wall.
    (
        "RibLength",
        "Length",
        f"{P}.Pitch - ({P}.TubeRelievedDiameter + {P}.ModeledTubeInnerDiameter) / 4"
        f" - ({P}.Inset - {RELIEF})",
    ),
]

# Short names for the rules, as they read in an expression.
BODY_HEIGHT, CAVITY_HEIGHT = f"{P}.BodyHeight", f"{P}.CavityHeight"
INSET, BAND_HEIGHT = f"{P}.Inset", f"{P}.BandHeight"
HAS_TUBES, HAS_PINS = f"{P}.HasTubes", f"{P}.HasPins"
HAS_GRIP_BAND, HAS_RIBS = f"{P}.HasGripBand", f"{P}.HasRibs"


def modeled(name: str) -> str:
    """The size a nominal value is modeled at, with its print offset: a Rules name."""
    return f"{P}.Modeled{name}"


def outside(studs: str) -> str:
    """The outside's length over a number of studs, less the side clearance."""
    return f"{P}.{studs} * {P}.Pitch - 2 * {modeled('SideClearance')}"


def cavity(studs: str) -> str:
    """The cavity's length over a number of studs, at its gripping size."""
    return f"{modeled('CavityWidth')} + ({P}.{studs} - 1) * {P}.Pitch"


def relieved(size: str) -> str:
    """A cavity size widened by the relief on both sides."""
    return f"({size} + 2 * {RELIEF})"


def add_params(
    doc: App.Document, nominal: Nominal, profile: Profile, size: Size
) -> App.VarSet:
    """Add the Params VarSet: the size, every nominal value and every print offset."""
    params = doc.addObject("App::VarSet", P)
    for field in fields(size):
        kind = "Bool" if field.type is bool else "Integer"
        params.addProperty(f"App::Property{kind}", field.name, "Size")
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
    """The outside, the cavity pocketed up into it, and the walls' grip band.

    The cavity is cut a relief wider on each side, then the band adds the walls'
    inside faces back to the gripping size, from GripBandBottom to GripBandTop.
    """
    sketch = sketch_on(
        body,
        "OutsideSketch",
        "XY_Plane",
        {"x": modeled("SideClearance"), "y": modeled("SideClearance")},
    )
    rectangle(sketch, "Outside", outside("Length"), outside("Width"))
    extrude(body, "Outside", sketch, BODY_HEIGHT)

    corner = f"{INSET} - {RELIEF}"
    sketch = sketch_on(body, "CavitySketch", "XY_Plane", {"x": corner, "y": corner})
    rectangle(sketch, "Cavity", relieved(cavity("Length")), relieved(cavity("Width")))
    extrude(body, "Cavity", sketch, CAVITY_HEIGHT, pocket=True)

    sketch = sketch_on(
        body,
        "WallGripSketch",
        "XY_Plane",
        {"x": corner, "y": corner, "z": f"{P}.GripBandBottom"},
    )
    rectangle(sketch, "Relieved", relieved(cavity("Length")), relieved(cavity("Width")))
    rectangle(sketch, "Grip", cavity("Length"), cavity("Width"), corner=RELIEF)
    grip = extrude(body, "WallGrip", sketch, BAND_HEIGHT)  # the frame between the two
    grip.setExpression("Suppressed", f"not({HAS_GRIP_BAND})")


def add_groove(body: App.Body) -> None:
    """The groove round a tile's bottom edge, which lets a tile be pried off.

    A frame pocketed up from the bottom: the outside less GrooveDepth per side,
    GrooveHeight tall. Switched on by Groove in Params.
    """
    sketch = sketch_on(
        body,
        "GrooveSketch",
        "XY_Plane",
        {"x": modeled("SideClearance"), "y": modeled("SideClearance")},
    )
    rectangle(sketch, "Outside", outside("Length"), outside("Width"))
    inner = {
        studs: f"{outside(studs)} - 2 * {P}.GrooveDepth"
        for studs in ("Length", "Width")
    }
    rectangle(
        sketch, "Inside", inner["Length"], inner["Width"], corner=f"{P}.GrooveDepth"
    )
    groove = extrude(body, "Groove", sketch, f"{P}.GrooveHeight", pocket=True)
    groove.setExpression("Suppressed", f"not({P}.Groove)")


def add_tubes(body: App.Body) -> None:
    """Tubes between every four studs, on parts at least 2 x 2: one tube, patterned.

    Three features make one tube, all patterned together:
      Tube       the tube and its bore, a relief narrower outside, up the cavity
      TubeGrip   the ring back out to the gripping size, in the grip band
      TubeMouth  below the band, cut to one printed line, TubeMouthWall thick,
                 centered on the gripping wall, so the first layers don't flare it
    """
    center = {"x": f"{P}.Pitch", "y": f"{P}.Pitch"}
    outer, inner = modeled("TubeOuterDiameter"), modeled("TubeInnerDiameter")
    narrow = f"{P}.TubeRelievedDiameter"
    grips = f"{HAS_TUBES} * {HAS_GRIP_BAND}"

    sketch = sketch_on(body, "TubeSketch", "XY_Plane", center)
    circle(sketch, "TubeRelievedDiameter", narrow)
    circle(sketch, "TubeInnerDiameter", inner)
    tube = extrude(body, "Tube", sketch, CAVITY_HEIGHT)
    tube.setExpression("Suppressed", f"not({HAS_TUBES})")

    band = {**center, "z": f"{P}.GripBandBottom"}
    sketch = sketch_on(body, "TubeGripSketch", "XY_Plane", band)
    circle(sketch, "TubeOuterDiameter", outer)
    circle(sketch, "TubeRelievedDiameter", narrow)
    grip = extrude(body, "TubeGrip", sketch, BAND_HEIGHT)
    grip.setExpression("Suppressed", f"not({grips})")

    wall_middle = f"({outer} + {inner}) / 2"  # a diameter
    sketch = sketch_on(body, "TubeMouthSketch", "XY_Plane", center)
    circle(sketch, "TubeRelievedDiameter", narrow)  # the outer ring cut away...
    circle(sketch, "MouthOuterDiameter", f"{wall_middle} + {P}.TubeMouthWall")
    circle(sketch, "MouthInnerDiameter", f"{wall_middle} - {P}.TubeMouthWall")
    circle(sketch, "TubeInnerDiameter", inner)  # ...and the inner ring
    mouth = extrude(body, "TubeMouth", sketch, f"{P}.GripBandBottom", pocket=True)
    mouth.setExpression("Suppressed", f"not({grips})")

    grid_pattern(body, "Tubes", [tube, grip, mouth], between=True, has=HAS_TUBES)


def add_pins(body: App.Body) -> None:
    """Pins between every two studs, on parts 1 stud wide: one pin, patterned.

    The pin is a relief narrower, with a ring back out to the gripping size in the
    grip band. The first pin sits a pitch along the part's long side and half a
    pitch in from its short side, whichever way round the part is.
    """
    first = {
        axis: f"({P}.{studs} == 1 ? {P}.Pitch / 2 : {P}.Pitch)"
        for axis, studs in (("x", "Length"), ("y", "Width"))
    }
    diameter = modeled("PinDiameter")
    narrow = f"{P}.PinRelievedDiameter"

    sketch = sketch_on(body, "PinSketch", "XY_Plane", first)
    circle(sketch, "PinRelievedDiameter", narrow)
    pin = extrude(body, "Pin", sketch, CAVITY_HEIGHT)
    pin.setExpression("Suppressed", f"not({HAS_PINS})")

    sketch = sketch_on(
        body, "PinGripSketch", "XY_Plane", {**first, "z": f"{P}.GripBandBottom"}
    )
    circle(sketch, "PinDiameter", diameter)
    circle(sketch, "PinRelievedDiameter", narrow)
    grip = extrude(body, "PinGrip", sketch, BAND_HEIGHT)
    grip.setExpression("Suppressed", f"not({HAS_PINS} * {HAS_GRIP_BAND})")

    grid_pattern(body, "Pins", [pin, grip], between=True, has=HAS_PINS)


def add_ribs(body: App.Body) -> None:
    """Ribs hanging from the ceiling of a 2 x N brick, from the long walls to tubes.

    Each ribbed tube gets a front and a back rib, from the wall's inside face into
    the middle of the tube's wall, so it joins the tube without reaching the bore.
    Both series of ribbed tubes (see RibsRightFirst in RULES) are patterned two
    pitches apart.
    """
    wall = f"({INSET} - {RELIEF})"  # the wall's inside face above the band
    top = f"{CAVITY_HEIGHT} - {P}.RibDepth"
    for side, has in (("Right", HAS_RIBS), ("Left", f"{P}.HasLeftRibs")):
        first, count = f"{P}.Ribs{side}First", f"{P}.Ribs{side}Count"
        x = f"{first} * {P}.Pitch - {P}.RibThickness / 2"
        ribs: list[App.DocumentObject] = []
        back = f"2 * {P}.Pitch - {wall} - {P}.RibLength"  # mirrors the front rib
        for end, y in (("Front", wall), ("Back", back)):
            name = f"Rib{side}{end}"
            sketch = sketch_on(
                body, f"{name}Sketch", "XY_Plane", {"x": x, "y": y, "z": top}
            )
            rectangle(sketch, "Rib", f"{P}.RibThickness", f"{P}.RibLength")
            rib = extrude(body, name, sketch, f"{P}.RibDepth")
            rib.setExpression("Suppressed", f"not({has})")
            ribs.append(rib)
        row_pattern(body, f"Ribs{side}", ribs, count, has)


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
    """A stud on every grid square, unless Studs is off: one revolved stud, patterned.

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
    stud.setExpression("Suppressed", f"not({P}.Studs)")  # off for a tile
    grid_pattern(body, "Studs", [stud], between=False, has=f"{P}.Studs")


# Sizes between them switching on every pattern: tubes and both rib series on a
# 2 x 6 brick, pins on a 1 x 4 brick (see build).
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
    add_groove(body)
    add_tubes(body)
    add_pins(body)
    add_ribs(body)
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
