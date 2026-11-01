"""The block family's size rules give the sizes of known parts."""

import math

import pytest

from freecad_generator.families.block_rules import (
    Size,
    box,
    ceiling,
    has_pins,
    has_tubes,
    stud_volume,
    volume,
)
from freecad_generator.store.nominal import load

N = load()
BRICK_2_X_4 = Size(Width=2, Length=4, Height=3)
PLATE_2_X_4 = Size(Width=2, Length=4, Height=1)


def test_a_plate_has_the_thin_ceiling_and_a_brick_the_thick_one() -> None:
    """Plates keep room for the stud below; bricks get the stiffer top."""
    assert ceiling(N, PLATE_2_X_4) == N.PlateCeiling
    assert ceiling(N, BRICK_2_X_4) == N.BrickCeiling


def test_a_2_x_4_brick_box() -> None:
    """31.8 long, 15.8 wide, and 9.6 tall plus its 1.7 studs."""
    assert box(N, BRICK_2_X_4) == pytest.approx((31.8, 15.8, 11.3))


def test_a_chamfered_stud_is_a_cylinder_and_a_cone() -> None:
    """Worked the other way: a 1.5 tall cylinder under a 0.2 tall cone frustum."""
    cylinder = math.pi * 2.4**2 * 1.5
    frustum = math.pi * 0.2 / 3 * (2.4**2 + 2.4 * 2.2 + 2.2**2)
    assert stud_volume(N) == pytest.approx(cylinder + frustum)


def test_a_2_x_4_brick_volume() -> None:
    """The shell under a 1.6 ceiling, three 8.0 tall tubes and eight studs."""
    tubes = 3 * math.pi / 4 * (6.51**2 - 4.8**2) * 8.0
    shell = 31.8 * 15.8 * 9.6 - 28.8 * 12.8 * 8.0
    studs = 8 * stud_volume(N)
    assert volume(N, BRICK_2_X_4) == pytest.approx(shell + tubes + studs)


@pytest.mark.parametrize(
    ("width", "length", "tubes", "pins"),
    [
        (1, 1, False, False),
        (1, 4, False, True),
        (4, 1, False, True),
        (2, 2, True, False),
    ],
)
def test_which_parts_have_tubes_or_pins(
    width: int, length: int, tubes: bool, pins: bool
) -> None:
    """A 1 x 1 has neither; 1 x N has pins either way round; 2 x 2 and up has tubes."""
    size = Size(Width=width, Length=length, Height=3)
    assert (has_tubes(size), has_pins(size)) == (tubes, pins)
