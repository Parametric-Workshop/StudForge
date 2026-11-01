"""The block family's size rules in plain Python, for checking without FreeCAD.

block.py writes each rule as a FreeCAD expression inside the file; this module
writes the same rule in Python, so a built part's volume and box can be compared
with exact values. The edit check holds the two together.
"""

import math
from dataclasses import dataclass

from freecad_generator.store.nominal import Nominal

BRICK_HEIGHT = 3  # plates: from this height up, a part is a brick
RIBBED_WIDTH = 2  # studs: ribs are on 2 x N bricks


@dataclass(frozen=True)
class Size:
    """One block family shape's settings, as in a file's Params."""

    Width: int  # studs across
    Length: int  # studs along
    Height: int  # plates: 1 for a plate or tile, 3 for a brick
    Ribs: bool = True  # off gives a plain shell, to tell ribs apart from fit offsets
    Studs: bool = True  # off for a tile
    Groove: bool = False  # the groove round a tile's bottom edge


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


def has_ribs(size: Size) -> bool:
    """Ribs on 2 x N bricks, brick height and up, unless switched off."""
    tall = size.Height >= BRICK_HEIGHT
    return size.Ribs and tall and size.Width == RIBBED_WIDTH and size.Length > 1


def ribbed_tubes(size: Size) -> list[int]:
    """Which tubes have ribs, numbered 1 to Length - 1 along the part.

    Every other tube, counting out from the center tube, or from the two middle
    tubes when there's an even number of them.
    """
    center = size.Length / 2
    if size.Length % 2 == 0:  # an odd number of tubes, one in the center
        return [k for k in range(1, size.Length) if (k - center) % 2 == 0]
    return [k for k in range(1, size.Length) if (abs(k - center) - 0.5) % 2 == 0]


def strip_in_circle(width: float, diameter: float) -> float:
    """The area of a strip, centered on a circle, that lies inside the circle."""
    r, x = diameter / 2, width / 2
    return 2 * (x * math.sqrt(r * r - x * x) + r * r * math.asin(x / r))


def rib_volume(n: Nominal) -> float:
    """A ribbed tube's two ribs, less the ends they bury in the tube's wall.

    Each runs from the wall's inside face into the middle of the tube's wall; the
    part inside the tube is already tube.
    """
    narrow = n.TubeOuterDiameter - 2 * n.GripRelief  # the tube above the band
    wall = (n.Pitch - n.CavityWidth) / 2 - n.GripRelief
    both = 2 * n.RibThickness * (n.Pitch - wall)  # wall to tube center, each side
    inside = strip_in_circle(n.RibThickness, narrow)
    return (both - inside) * n.RibDepth


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
    """The outside less a cavity a relief wider per side, plus the walls' grip band.

    With GripRelief 0 the relieved cavity is the gripping one, and the band adds
    nothing.
    """
    band = n.GripBandTop - n.GripBandBottom
    grip = cavity(n, size.Width) * cavity(n, size.Length)
    wide = (cavity(n, size.Width) + 2 * n.GripRelief) * (
        cavity(n, size.Length) + 2 * n.GripRelief
    )
    cavity_height = body_height(n, size) - ceiling(n, size)
    full = outside(n, size.Width) * outside(n, size.Length) * body_height(n, size)
    return full - wide * cavity_height + (wide - grip) * band


def tube_volume(n: Nominal, size: Size) -> float:
    """One tube: a relief narrower outside, its grip ring, less its mouth's cuts.

    The mouth, below the grip band, is a wall TubeMouthWall thick, centered on the
    gripping wall; there's no mouth without a grip band.
    """
    outer, inner = n.TubeOuterDiameter, n.TubeInnerDiameter
    narrow = outer - 2 * n.GripRelief
    band = n.GripBandTop - n.GripBandBottom
    cavity_height = body_height(n, size) - ceiling(n, size)
    tube = ring(narrow, inner) * cavity_height + ring(outer, narrow) * band
    if n.GripRelief > 0:
        middle = (outer + inner) / 2
        cut = ring(narrow, middle + n.TubeMouthWall)
        cut += ring(middle - n.TubeMouthWall, inner)
        tube -= cut * n.GripBandBottom
    return tube


def pin_volume(n: Nominal, size: Size) -> float:
    """One pin: a relief narrower, with its grip ring in the band."""
    narrow = n.PinDiameter - 2 * n.GripRelief
    band = n.GripBandTop - n.GripBandBottom
    cavity_height = body_height(n, size) - ceiling(n, size)
    return ring(narrow, 0) * cavity_height + ring(n.PinDiameter, narrow) * band


def groove_volume(n: Nominal, size: Size) -> float:
    """The groove round the bottom edge: GrooveDepth in, GrooveHeight up, all round."""
    length, width = outside(n, size.Length), outside(n, size.Width)
    inner = (length - 2 * n.GrooveDepth) * (width - 2 * n.GrooveDepth)
    return (length * width - inner) * n.GrooveHeight


def volume(n: Nominal, size: Size) -> float:
    """The part's volume in cubic millimeters: shell, tubes or pins, and studs."""
    between = max(size.Width - 1, 1) * max(size.Length - 1, 1)  # tubes or pins
    underside = 0.0
    if has_tubes(size):
        underside = between * tube_volume(n, size)
    elif has_pins(size):
        underside = between * pin_volume(n, size)
    ribs = len(ribbed_tubes(size)) * rib_volume(n) if has_ribs(size) else 0.0
    studs = size.Width * size.Length * stud_volume(n) if size.Studs else 0.0
    groove = groove_volume(n, size) if size.Groove else 0.0
    return shell_volume(n, size) + underside + ribs + studs - groove


def box(n: Nominal, size: Size) -> tuple[float, float, float]:
    """The part's bounding box: length (x), width (y) and height (z), studs on top."""
    height = body_height(n, size) + (n.StudHeight if size.Studs else 0.0)
    return outside(n, size.Length), outside(n, size.Width), height
