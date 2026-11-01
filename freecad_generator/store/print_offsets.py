"""Print offsets: the list of them (print_offsets.toml) and filament profiles.

Each offset is named after the nominal value it adjusts plus "Offset", and is
added to it. A filament profile gives values for some of them; the rest are 0.
"""

import tomllib
from dataclasses import dataclass, fields, replace
from pathlib import Path
from typing import Any

from freecad_generator.store.nominal import Nominal

HERE = Path(__file__).parent
PRINT_OFFSETS_TOML = HERE / "print_offsets.toml"
PROFILES = HERE.parents[1] / "profiles"
SUFFIX = "Offset"
LOOSER = ("larger", "smaller")  # which way an offset loosens its fit


@dataclass(frozen=True)
class PrintOffset:
    """One print offset, as print_offsets.toml lists it."""

    name: str  # such as StudDiameterOffset
    group: str  # its fit group's title, such as "Studs and tubes"
    looser: str  # "larger" or "smaller"
    moves: str  # what it moves, in a few words

    @property
    def nominal(self) -> str:
        """The nominal value it adjusts, such as StudDiameter."""
        return self.name.removesuffix(SUFFIX)


@dataclass(frozen=True)
class Profile:
    """A filament profile: its name, and a value for every print offset."""

    name: str
    offsets: dict[str, float]  # every offset by name, 0 unless the profile sets it


def load_print_offsets(path: Path = PRINT_OFFSETS_TOML) -> list[PrintOffset]:
    """Read the list of print offsets; stop on one that adjusts no nominal value."""
    with path.open("rb") as file:
        groups: dict[str, dict[str, Any]] = tomllib.load(file)
    nominal = {field.name for field in fields(Nominal)}
    offsets: list[PrintOffset] = []
    for group in groups.values():
        title = str(group.pop("title"))
        for name, entry in group.items():
            offset = PrintOffset(name, title, entry["looser"], entry["moves"])
            if not name.endswith(SUFFIX) or offset.nominal not in nominal:
                raise ValueError(f"{path.name}: {name} adjusts no nominal value")
            if offset.looser not in LOOSER:
                raise ValueError(f"{path.name}: {name}'s looser must be {LOOSER}")
            if any(other.name == name for other in offsets):
                raise ValueError(f"{path.name}: {name} is in more than one fit group")
            offsets.append(offset)
    return offsets


def load_profile(path: Path, offsets: list[PrintOffset] | None = None) -> Profile:
    """Read a filament profile; stop on a name that isn't a print offset."""
    with path.open("rb") as file:
        values = tomllib.load(file)
    name = str(values.pop("name"))
    known = {offset.name: 0.0 for offset in offsets or load_print_offsets()}
    unknown = values.keys() - known.keys()
    if unknown:
        raise ValueError(f"{path.name}: unknown print offsets {sorted(unknown)}")
    return Profile(name, known | {key: float(value) for key, value in values.items()})


def no_offsets(offsets: list[PrintOffset] | None = None) -> Profile:
    """The profile that changes nothing: every part at its nominal size."""
    return Profile(
        "nominal", {offset.name: 0.0 for offset in offsets or load_print_offsets()}
    )


def applied(nominal: Nominal, profile: Profile) -> Nominal:
    """The sizes a part is modeled at: each nominal value plus its offset."""
    changes = {
        name.removesuffix(SUFFIX): getattr(nominal, name.removesuffix(SUFFIX)) + value
        for name, value in profile.offsets.items()
    }
    return replace(nominal, **changes)
