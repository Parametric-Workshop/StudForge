"""The block family's nominal values give the sizes they're described by."""

import math
from pathlib import Path

import pytest

from freecad_generator.store.nominal import NOMINAL_TOML, load

N = load()


def test_a_misspelled_name_stops_the_build(tmp_path: Path) -> None:
    """A name that isn't a field is reported, with the field it should have been."""
    text = NOMINAL_TOML.read_text().replace("StudChamfer =", "StudChamfr =")
    misspelled = tmp_path / "nominal.toml"
    misspelled.write_text(text)
    with pytest.raises(
        ValueError, match=r"missing \['StudChamfer'\], unknown \['StudChamfr'\]"
    ):
        load(misspelled)


def test_a_1_x_1_is_7_8_wide() -> None:
    """A pitch less the side clearance on both sides."""
    assert N.Pitch - 2 * N.SideClearance == pytest.approx(7.8)


def test_the_wall_is_1_5() -> None:
    """The wall is what's left between the side clearance and the cavity."""
    assert (N.Pitch - 2 * N.SideClearance - N.CavityWidth) / 2 == pytest.approx(1.5)


def test_a_tube_touches_four_studs() -> None:
    """The tube fills the gap between four studs, to within 0.01."""
    gap = N.Pitch * math.sqrt(2) - N.StudDiameter
    assert N.TubeOuterDiameter == pytest.approx(gap, abs=0.01)


def test_a_pin_touches_two_studs() -> None:
    """The pin fills the gap between two studs."""
    assert N.PinDiameter == pytest.approx(N.Pitch - N.StudDiameter)


def test_a_plate_cavity_clears_the_stud_below() -> None:
    """Under a plate's ceiling, a stud of the part below still fits."""
    assert N.PlateHeight - N.PlateCeiling > N.StudHeight


def test_a_name_in_two_sections_stops_the_build(tmp_path: Path) -> None:
    """A later family's section can't quietly replace a value another uses."""
    text = NOMINAL_TOML.read_text() + "\n[technic]\nPinDiameter = 4.8\n"
    repeated = tmp_path / "nominal.toml"
    repeated.write_text(text)
    with pytest.raises(ValueError, match="PinDiameter is in more than one section"):
        load(repeated)
