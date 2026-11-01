"""The real shapes the block family makes, by part number (block_shapes.toml)."""

import tomllib
from dataclasses import fields
from pathlib import Path

from freecad_generator.families.block_rules import Size

BLOCK_SHAPES_TOML = Path(__file__).with_name("block_shapes.toml")


def load_block_shapes(path: Path = BLOCK_SHAPES_TOML) -> dict[str, Size]:
    """Read each shape's settings; stop on a setting that isn't one of Size's."""
    with path.open("rb") as file:
        rows = tomllib.load(file)
    settings = {field.name for field in fields(Size)}
    shapes: dict[str, Size] = {}
    for part_num, row in rows.items():
        unknown = row.keys() - settings
        if unknown:
            raise ValueError(f"{path.name}: {part_num} has unknown {sorted(unknown)}")
        shapes[part_num] = Size(**row)
    return shapes
