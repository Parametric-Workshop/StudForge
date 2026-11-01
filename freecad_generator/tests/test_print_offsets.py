"""The list of print offsets, filament profiles, and how offsets apply."""

from pathlib import Path

import pytest

from freecad_generator.store.nominal import load
from freecad_generator.store.print_offsets import (
    PROFILES,
    applied,
    load_print_offsets,
    load_profile,
    no_offsets,
)

N = load()


def test_every_offset_has_a_fit_group_and_a_direction() -> None:
    """Each offset adjusts a nominal value, and says which way loosens its fit."""
    offsets = load_print_offsets()
    assert {offset.group for offset in offsets} == {"Studs and tubes"}
    assert {offset.nominal for offset in offsets} >= {"StudDiameter", "CavityWidth"}


def test_every_profile_reads() -> None:
    """Every profile in profiles/ names only known offsets."""
    for path in sorted(PROFILES.glob("*.toml")):
        assert load_profile(path).name


def test_a_profile_fills_the_rest_with_zero() -> None:
    """The CC2 profile sets four offsets; the others are 0."""
    profile = load_profile(PROFILES / "elegoo-cc2-pla.toml")
    assert profile.offsets["StudDiameterOffset"] == pytest.approx(0.35)
    assert profile.offsets["PinDiameterOffset"] == 0


def test_a_misspelled_offset_stops_the_build(tmp_path: Path) -> None:
    """A name that isn't in print_offsets.toml is reported."""
    path = tmp_path / "typo.toml"
    path.write_text('name = "typo"\nStudDiamterOffset = 0.1\n')
    with pytest.raises(ValueError, match="StudDiamterOffset"):
        load_profile(path)


def test_offsets_add_to_their_nominal_values() -> None:
    """A part is modeled at nominal plus offset; with no offsets, at nominal."""
    profile = load_profile(PROFILES / "elegoo-cc2-pla.toml")
    assert applied(N, profile).StudDiameter == pytest.approx(4.8 + 0.35)
    assert applied(N, profile).CavityWidth == pytest.approx(4.8 - 0.15)
    assert applied(N, no_offsets()) == N
