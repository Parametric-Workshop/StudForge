# StudForge

StudForge models LEGO-compatible building parts in FreeCAD, tuned for FDM printing, and tracks how much of the real parts catalog it can print.

## Parts and the catalog

**Part**:
One distinct shape of building element, independent of color and decoration.
_Avoid_: Piece, brick (unless it really is a brick), element

**Decoration**:
A print, pattern or sticker applied to a part; it never makes a new part.
_Avoid_: Printed part, variant

**Design**:
A group of parts that a builder treats as the same thing but that differ in geometry, such as tiles with and without a bottom groove.
_Avoid_: Mold group, family

**Variant**:
One part within a design, such as the grooved 1 x 1 tile.
_Avoid_: Mold, version, revision

**Assembly**:
A factory-combined group of parts sold under its own part number, such as a wheel with its tire; not itself a part.
_Avoid_: Composite part, sub-assembly

**Rebrickable Census**:
A dated snapshot of every plastic part known to Rebrickable, with decorations folded into their base part, together with the parts lists of every official set; the denominator for coverage.
_Avoid_: Universe, catalog, all parts

**Family**:
A group of parts produced by one parametric generator and differing only in size or selectable features, such as the brick family covering 1 x 1 through 2 x 4 and beyond.
_Avoid_: Category, series, type

**Category**:
Rebrickable's classification of a part (Bricks, Plates, Tiles Special); used only to describe source data.
_Avoid_: Family

## Builds

**Build**:
Something the owner intends to make with printed parts, either an official set or a MOC.
_Avoid_: Kit, model, set, project

**Inventory**:
The list of parts, with variants, colors and quantities, needed for one build.
_Avoid_: Parts list, BOM, kit

**Print kit**:
The published, printable package of files for one build.
_Avoid_: Kit, bundle, release

## Coverage

**Covered**:
A part whose StudForge model has passed validation against its reference geometry; an assembly is covered when all its parts are.
_Avoid_: Done, supported, modeled

**Print-tested**:
A covered part that has been printed with a given filament profile and confirmed to fit.
_Avoid_: Verified, proven

**Usage**:
The total quantity of a part across every set in the Rebrickable Census, counting minifig parts and quantities inherited from assemblies but not spares; the main weight for coverage.
_Avoid_: Popularity, frequency

**Reach**:
The number of distinct sets in the Rebrickable Census that contain a part.
_Avoid_: Usage, popularity

## Dimensions

**Nominal dimension**:
The ideal size of a feature on a part, before any adjustment for printing.
_Avoid_: Tolerance, spec

**Print offset**:
A deliberate, feature-specific adjustment to a nominal dimension so the printed feature fits as intended.
_Avoid_: Tolerance, clearance (unless it is literally a gap), compensation

**Filament profile**:
A named set of print offsets tuned for one filament.
_Avoid_: Tolerance profile, printer profile

**Slicer compensation**:
A material-level correction applied in the slicer (shrinkage, flow, elephant foot), outside StudForge.
_Avoid_: Tolerance, print offset
