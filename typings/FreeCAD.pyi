"""The parts of FreeCAD's App module that the generator uses (FreeCAD 1.1.4)."""

from typing import Literal, overload

from Part import Shape

class Vector:
    x: float
    y: float
    z: float
    def __init__(self, x: float = 0, y: float = 0, z: float = 0) -> None: ...
    def __add__(self, other: Vector) -> Vector: ...

class DocumentObject:
    Name: str
    State: list[str]
    Visibility: bool
    def setExpression(self, path: str, expression: str | None) -> None: ...
    def isDerivedFrom(self, type: str) -> bool: ...

class VarSet(DocumentObject):
    def setPropertyStatus(self, name: str, status: str) -> None: ...
    def addProperty(
        self, type: str, name: str, group: str = "", doc: str = ""
    ) -> VarSet: ...

class OriginFeature(DocumentObject):
    Role: str

class Origin(DocumentObject):
    OriginFeatures: list[OriginFeature]

class Body(DocumentObject):
    Origin: Origin
    Tip: DocumentObject
    Group: list[DocumentObject]
    Shape: Shape
    @overload
    def newObject(
        self, type: Literal["Sketcher::SketchObject"], name: str
    ) -> SketchObject: ...
    @overload
    def newObject(
        self, type: Literal["PartDesign::Pad", "PartDesign::Pocket"], name: str
    ) -> ProfileFeature: ...
    @overload
    def newObject(
        self, type: Literal["PartDesign::Revolution"], name: str
    ) -> Revolution: ...
    @overload
    def newObject(
        self, type: Literal["PartDesign::LinearPattern"], name: str
    ) -> LinearPattern: ...

class Revolution(ProfileFeature):
    ReferenceAxis: tuple[DocumentObject, list[str]]
    Angle: float

class LinearPattern(DocumentObject):
    Originals: list[DocumentObject]
    Direction: tuple[DocumentObject, list[str]]
    Direction2: tuple[DocumentObject, list[str]]
    Mode: str
    Mode2: str

class SketchObject(DocumentObject):
    AttachmentSupport: list[tuple[DocumentObject, str]]
    MapMode: str
    GeometryCount: int
    def addGeometry(self, geometry: object) -> int: ...
    def addConstraint(self, constraint: object) -> int: ...
    def renameConstraint(self, index: int, name: str) -> None: ...

class ProfileFeature(DocumentObject):
    Profile: SketchObject
    Reversed: bool

class Document(DocumentObject):
    Objects: list[DocumentObject]
    Label: str
    CreatedBy: str
    Company: str
    Comment: str
    Meta: dict[str, str]
    def getObject(self, name: str) -> DocumentObject | None: ...
    @overload
    def addObject(self, type: Literal["App::VarSet"], name: str) -> VarSet: ...
    @overload
    def addObject(self, type: Literal["PartDesign::Body"], name: str) -> Body: ...
    def recompute(self) -> int: ...
    def saveAs(self, path: str) -> None: ...

def newDocument(name: str) -> Document: ...
def Version() -> list[str]: ...  # major, minor, patch, then build details
def openDocument(path: str) -> Document: ...
def closeDocument(name: str) -> None: ...
