"""Tests for census/candidates.py: brick systems and exclusion rules."""

import pytest

import candidates


@pytest.mark.parametrize(
    ("name", "category", "system"),
    [
        ("Brick 2 x 4", "Bricks", "standard"),
        ("Duplo Brick 2 x 2", "Duplo, Quatro and Primo", "duplo"),
        ("Playmat, Duplo, Farm", "Non-System Parts", "duplo"),
        ("Primo Brick 1 x 1", "Duplo, Quatro and Primo", "primo"),
        ("Brick 1 x 2", "Modulex", "modulex"),
    ],
)
def test_brick_system(name: str, category: str, system: str) -> None:
    """The brick system comes from the category or a system name in the name."""
    assert candidates.brick_system(name, category) == system


@pytest.mark.parametrize(
    ("system", "category", "material", "reason"),
    [
        ("standard", "Bricks", "Plastic", None),
        ("standard", "Wheels and Tyres", "Rubber", None),
        ("duplo", "Duplo, Quatro and Primo", "Plastic", None),
        (
            "modulex",
            "Modulex",
            "Plastic",
            ("not compatible with standard LEGO", "modulex"),
        ),
        ("standard", "Minifig Accessories", "Cloth", ("not 3D printable", "cloth")),
        ("standard", "Stickers", "Plastic", ("not 3D printable", "Stickers")),
    ],
)
def test_exclusion(
    system: str, category: str, material: str, reason: tuple[str, str] | None
) -> None:
    """Shapes are excluded by brick system, then material, then category."""
    assert candidates.exclusion(system, category, material) == reason
