"""The parts of FreeCAD's Sketcher module that the generator uses (FreeCAD 1.1.4)."""

class Constraint:
    def __init__(self, type: str, *args: int | float) -> None: ...
