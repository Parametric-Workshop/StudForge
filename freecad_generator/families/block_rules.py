"""The block family's size rules in plain Python, for checking without FreeCAD.

block.py writes each rule as a FreeCAD expression inside the file; this module
writes the same rule in Python, so a built part's volume and box can be compared
with exact values. The edit check holds the two together.
"""

import math
from dataclasses import dataclass

from freecad_generator.store.nominal import Nominal

BRICK_HEIGHT = 3  # plates: from this height up, a part is a brick


@dataclass(frozen=True)
class Size:
    """One block family shape's settings, as in a file's Params."""

    Width: int  # studs across
    Length: int  # studs along
    Height: int  # plates: 1 for a plate, 3 for a brick


def body_height(n: Nominal, size: Size) -> float:
    """The body's height without studs."""
    return size.Height * n.PlateHeight


def ceiling(n: Nominal, size: Size) -> float:
    """The ceiling's thickness over the cavity."""
    return n.PlateCeiling if size.Height < BRICK_HEIGHT else n.BrickCeiling


def outside(n: Nominal, studs: int) -> float:
    """The outside's length over a number of studs, less the side clearance."""
    return studs * n.Pitch - 2 * n.SideClearance


def cavity(n: Nominal, studs: int) -> float:
    """The cavity's length over a number of studs."""
    return n.CavityWidth + (studs - 1) * n.Pitch


def has_tubes(size: Size) -> bool:
    """Tubes between every four studs, on parts at least 2 x 2."""
    return size.Width > 1 and size.Length > 1


def has_pins(size: Size) -> bool:
    """Pins between every two studs, on parts 1 stud wide, either way round."""
    return (size.Width == 1) != (size.Length == 1)


def stud_volume(n: Nominal) -> float:
    """One stud: a cylinder less the ring its 45 degree chamfer takes off the top.

    The ring is a right triangle, StudChamfer on each side, swept round the axis
    at its centroid, a third of the way in from the stud's side (Pappus).
    """
    radius, chamfer = n.StudDiameter / 2, n.StudChamfer
    cylinder = math.pi * radius**2 * n.StudHeight
    ring = 2 * math.pi * (radius - chamfer / 3) * chamfer**2 / 2
    return cylinder - ring


def ring(outer: float, inner: float) -> float:
    """The area between two circles, given their diameters."""
    return math.pi / 4 * (outer**2 - inner**2)


def shell_volume(n: Nominal, size: Size) -> float:
    """The outside less the cavity under the ceiling."""
    full = outside(n, size.Width) * outside(n, size.Length) * body_height(n, size)
    cavity_height = body_height(n, size) - ceiling(n, size)
    return full - cavity(n, size.Width) * cavity(n, size.Length) * cavity_height


def tube_volume(n: Nominal, size: Size) -> float:
    """One tube, with its bore, up the cavity."""
    cavity_height = body_height(n, size) - ceiling(n, size)
    return ring(n.TubeOuterDiameter, n.TubeInnerDiameter) * cavity_height


def pin_volume(n: Nominal, size: Size) -> float:
    """One pin, up the cavity."""
    cavity_height = body_height(n, size) - ceiling(n, size)
    return ring(n.PinDiameter, 0) * cavity_height


def volume(n: Nominal, size: Size) -> float:
    """The part's volume in cubic millimeters: shell, tubes or pins, and studs."""
    between = max(size.Width - 1, 1) * max(size.Length - 1, 1)  # tubes or pins
    underside = 0.0
    if has_tubes(size):
        underside = between * tube_volume(n, size)
    elif has_pins(size):
        underside = between * pin_volume(n, size)
    studs = size.Width * size.Length * stud_volume(n)
    return shell_volume(n, size) + underside + studs


def box(n: Nominal, size: Size) -> tuple[float, float, float]:
    """The part's bounding box: length (x), width (y) and height (z), studs on top."""
    height = body_height(n, size) + n.StudHeight
    return outside(n, size.Length), outside(n, size.Width), height
