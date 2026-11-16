"""The block family's size rules give the sizes of known parts."""

import math
from dataclasses import replace

import pytest

from freecad_generator.families.block_rules import (
    Size,
    box,
    ceiling,
    has_pins,
    has_ribs,
    has_tubes,
    ribbed_tubes,
    stud_volume,
    tube_volume,
    volume,
)
from freecad_generator.store.nominal import load

N = load()
BRICK_2_X_4 = Size(Width=2, Length=4, Height=3)
PLATE_2_X_4 = Size(Width=2, Length=4, Height=1)


def test_a_plate_has_the_thin_ceiling_and_a_brick_the_thick_one() -> None:
    """Plates and tiles keep room for the stud below; bricks get the stiffer top."""
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


def test_a_plain_2_x_4_brick_volume() -> None:
    """No grip band or ribs: the shell under a 1.6 ceiling, 8.0 tubes, eight studs."""
    plain = replace(N, GripRelief=0.0)
    tubes = 3 * math.pi / 4 * (6.51**2 - 4.8**2) * 8.0
    shell = 31.8 * 15.8 * 9.6 - 28.8 * 12.8 * 8.0
    studs = 8 * stud_volume(plain)
    brick = replace(BRICK_2_X_4, Ribs=False)
    assert volume(plain, brick) == pytest.approx(shell + tubes + studs)


@pytest.mark.parametrize(
    ("length", "ribbed"),
    [
        (2, [1]),  # 2 x 2: its one tube
        (3, [1, 2]),  # 2 x 3: both middle tubes
        (4, [2]),  # 2 x 4: the center tube, as on a real one
        (5, [2, 3]),  # 2 x 5: both middle tubes
        (6, [1, 3, 5]),  # 2 x 6: the center and every other out
        (8, [2, 4, 6]),  # 2 x 8: as LDraw's 3007
    ],
)
def test_which_tubes_have_ribs(length: int, ribbed: list[int]) -> None:
    """Every other tube, counting out from the center or the two middle tubes."""
    assert ribbed_tubes(Size(Width=2, Length=length, Height=3)) == ribbed


def test_only_2_x_n_bricks_have_ribs() -> None:
    """Not plates, not 1 x N or 4 x N bricks, and not when switched off."""
    assert has_ribs(BRICK_2_X_4)
    assert not has_ribs(PLATE_2_X_4)
    assert not has_ribs(Size(Width=1, Length=4, Height=3))
    assert not has_ribs(Size(Width=4, Length=6, Height=3))
    assert not has_ribs(replace(BRICK_2_X_4, Ribs=False))


def test_a_tube_with_its_grip_band() -> None:
    """6.31 outside up the cavity, 6.51 in the band, a 0.5 wall below it.

    The mouth's wall is centered on the gripping wall, at a 5.655 diameter: from
    5.155 to 6.155 across.
    """
    area = math.pi / 4

    def ring(outer: float, inner: float) -> float:
        return area * (outer**2 - inner**2)

    relieved = ring(6.31, 4.8) * 8.0
    band = ring(6.51, 6.31) * 0.8
    mouth_cuts = (ring(6.31, 6.155) + ring(5.155, 4.8)) * 0.4
    assert tube_volume(N, BRICK_2_X_4) == pytest.approx(relieved + band - mouth_cuts)


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


def test_a_tile_has_no_studs_and_a_groove() -> None:
    """Tile 2 x 2: 3.2 tall, and its groove is a 0.4 x 0.4 frame round the bottom."""
    tile = Size(Width=2, Length=2, Height=1, Studs=False, Groove=True)
    plate = Size(Width=2, Length=2, Height=1)
    groove = (15.8 * 15.8 - 15.0 * 15.0) * 0.4
    studs = 4 * stud_volume(N)
    assert box(N, tile) == pytest.approx((15.8, 15.8, 3.2))
    assert volume(N, plate) - volume(N, tile) == pytest.approx(studs + groove)
