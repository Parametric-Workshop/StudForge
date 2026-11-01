"""The parts of FreeCAD's Part module that the generator uses (FreeCAD 1.1.4)."""

from FreeCAD import Vector

class LineSegment:
    def __init__(self, start: Vector, end: Vector) -> None: ...

class Circle:
    def __init__(self, center: Vector, normal: Vector, radius: float) -> None: ...

class BoundBox:
    XLength: float
    YLength: float
    ZLength: float

class Shape:
    Volume: float
    Solids: list[Shape]
    def cut(self, other: Shape) -> Shape: ...
    def isValid(self) -> bool: ...
    def optimalBoundingBox(self) -> BoundBox: ...
