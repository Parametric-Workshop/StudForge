"""Part Design building blocks shared by every family's generator. Runs in FreeCAD.

Each feature is a sketch plus a Part Design feature (Pad, Pocket, Revolution),
its sizes named sketch constraints driven by expressions on the file's Params.
Each sketch is attached to a body plane and moved by its AttachmentOffset, never
its Placement: FreeCAD 1.1.4 puts back a stale Placement when a suppressed feature
comes back.
"""

from __future__ import annotations  # FreeCAD has no Sketch class to name at run time

import FreeCAD as App
import Part
import Sketcher

P = "Params"  # the VarSet holding every size and nominal value


def plane(body: App.Body, role: str) -> App.OriginFeature:
    """One of the body's origin planes or axes, such as XY_Plane."""
    return next(f for f in body.Origin.OriginFeatures if f.Role == role)


def sketch_on(
    body: App.Body, name: str, role: str, offset: dict[str, str]
) -> App.SketchObject:
    """A sketch attached to a body plane, moved by AttachmentOffset expressions."""
    sketch = body.newObject("Sketcher::SketchObject", name)
    sketch.AttachmentSupport = [(plane(body, role), "")]
    sketch.MapMode = "FlatFace"
    for axis, expression in offset.items():
        sketch.setExpression(f".AttachmentOffset.Base.{axis}", expression)
    return sketch


def driven(
    sketch: App.SketchObject,
    constraint: Sketcher.Constraint,
    name: str,
    expression: str,
) -> None:
    """Add a constraint, name it, and drive it from Params."""
    index = sketch.addConstraint(constraint)
    sketch.renameConstraint(index, name)
    sketch.setExpression(f"Constraints.{name}", expression)


def rectangle(sketch: App.SketchObject, name: str, length: str, width: str) -> None:
    """A rectangle with its lower left corner on the sketch's origin.

    Its sides are named constraints, such as OutsideLength and OutsideWidth.
    """
    first = sketch.GeometryCount
    # A starting shape; the constraints size it.
    corners = [App.Vector(x, y) for x, y in ((0, 0), (8, 0), (8, 3), (0, 3))]
    for i in range(4):
        sketch.addGeometry(Part.LineSegment(corners[i], corners[(i + 1) % 4]))
    for i in range(4):  # each side's end on the next side's start
        sketch.addConstraint(
            Sketcher.Constraint("Coincident", first + i, 2, first + (i + 1) % 4, 1)
        )
    for i, direction in enumerate(["Horizontal", "Vertical"] * 2):
        sketch.addConstraint(Sketcher.Constraint(direction, first + i))
    sketch.addConstraint(Sketcher.Constraint("Coincident", first, 1, -1, 1))
    driven(
        sketch,
        Sketcher.Constraint("DistanceX", first, 1, first, 2, 8),
        f"{name}Length",
        length,
    )
    driven(
        sketch,
        Sketcher.Constraint("DistanceY", first + 1, 1, first + 1, 2, 3),
        f"{name}Width",
        width,
    )


def circle(sketch: App.SketchObject, name: str, diameter: str) -> None:
    """A circle centered on the sketch's origin, its diameter a named constraint."""
    index = sketch.addGeometry(Part.Circle(App.Vector(0, 0), App.Vector(0, 0, 1), 2))
    sketch.addConstraint(Sketcher.Constraint("Coincident", index, 3, -1, 1))
    driven(sketch, Sketcher.Constraint("Diameter", index, 4), name, diameter)


def extrude(
    body: App.Body,
    name: str,
    sketch: App.SketchObject,
    length: str,
    pocket: bool = False,
) -> App.ProfileFeature:
    """Pad a sketch up from its plane, or with `pocket`, cut it up into the part."""
    feature = body.newObject(
        "PartDesign::Pocket" if pocket else "PartDesign::Pad", name
    )
    feature.Profile = sketch
    feature.Reversed = pocket  # a pocket would otherwise cut down, away from the part
    feature.setExpression("Length", length)
    return feature


def grid_pattern(
    body: App.Body,
    name: str,
    features: list[App.DocumentObject],
    between: bool,
    has: str | None = None,
) -> None:
    """Repeat features a pitch apart, along the length and across the width.

    One copy on every stud, or with `between`, one between each pair of neighboring
    studs: Length - 1 along, Width - 1 across, and at least one each way, as a 1 x N
    part's pins need. A suppressed pattern still works out its counts, so they never
    drop below 1.
    """
    pattern = body.newObject("PartDesign::LinearPattern", name)
    pattern.Originals = features
    body.Tip = pattern  # a new pattern doesn't become the tip by itself
    pattern.Direction = (plane(body, "X_Axis"), [""])
    pattern.Direction2 = (plane(body, "Y_Axis"), [""])
    pattern.Mode = pattern.Mode2 = "Extent"  # each direction set by its overall length
    fewer = 1 if between else 0
    for direction, studs in (("", "Length"), ("2", "Width")):
        count = f"max(1; {P}.{studs} - {fewer})"
        pattern.setExpression(f"Occurrences{direction}", count)
        pattern.setExpression(f"Length{direction}", f"({count} - 1) * {P}.Pitch")
    if has is not None:
        pattern.setExpression("Suppressed", f"not({has})")


def show_result(doc: App.Document, body: App.Body) -> None:
    """Show the body's result only, as the GUI would leave it.

    A file saved without the GUI keeps each object's own Visibility, so the earlier
    features, the sketches and the origin planes would all open shown.
    """
    for obj in body.Group:
        obj.Visibility = obj == body.Tip
    body.Visibility = True
    for obj in doc.Objects:
        if obj.isDerivedFrom("App::Origin") or obj.isDerivedFrom("App::DatumElement"):
            obj.Visibility = False
