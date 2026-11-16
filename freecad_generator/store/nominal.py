"""Nominal dimensions of the block family, read from nominal.toml.

The values and the reasons for them live in nominal.toml. This module lists their
names, so the generator and type checker know them, and reads the file.
"""

import tomllib
from dataclasses import dataclass, fields
from pathlib import Path

NOMINAL_TOML = Path(__file__).with_name("nominal.toml")


@dataclass(frozen=True)
class Nominal:
    """The ideal size of each block family feature, before any print offset, in mm."""

    Pitch: float
    SideClearance: float
    PlateHeight: float
    StudDiameter: float
    StudHeight: float
    StudChamfer: float
    CavityWidth: float
    PlateCeiling: float
    BrickCeiling: float
    TubeOuterDiameter: float
    TubeInnerDiameter: float
    PinDiameter: float
    GripBandBottom: float
    GripBandTop: float
    GripRelief: float
    TubeMouthWall: float
    RibThickness: float
    RibDepth: float
    GrooveDepth: float
    GrooveHeight: float


def load(path: Path = NOMINAL_TOML) -> Nominal:
    """Read the nominal values; stop if one is missing, repeated or unknown.

    Sections only group the values, so a name in two sections would otherwise
    quietly replace the first.
    """
    with path.open("rb") as file:
        sections = tomllib.load(file)
    values: dict[str, float] = {}
    for entries in sections.values():
        for name, value in entries.items():
            if name in values:
                raise ValueError(f"{path.name}: {name} is in more than one section")
            values[name] = float(value)
    names = {field.name for field in fields(Nominal)}
    missing, unknown = names - values.keys(), values.keys() - names
    if missing or unknown:
        raise ValueError(
            f"{path.name}: missing {sorted(missing)}, unknown {sorted(unknown)}"
        )
    return Nominal(**values)
