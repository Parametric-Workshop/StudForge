# StudForge

StudForge models the shapes of LEGO-compatible building parts in FreeCAD, tuned for FDM printing, and tracks how many real shapes it can print.

## Shapes and the census

**Shape**:
One distinct geometry of building element, independent of color and decoration, such as `3068b`; what StudForge models.
_Avoid_: Part, piece, brick (unless it really is a brick), element

**Part number**:
Rebrickable's identifier for a shape, a decorated shape or an assembly, such as `3068b`, `3068bpr0001` or `4624c01`; what everything is keyed by, never a kind of thing.
_Avoid_: Part, ID, design ID

**Decoration**:
A print, pattern or sticker applied to a shape; it never makes a new shape.
_Avoid_: Variant

**Decorated shape**:
A shape with a decoration applied, sold under its own part number, such as `3068bpr0001` on the shape `3068b`; the condensed census folds it into its shape.
_Avoid_: Decorated part, printed part, variant

**Design**:
A group of shapes that a builder treats as the same thing but that differ in geometry, such as tiles with and without a bottom groove.
_Avoid_: Mold group, family

**Variant**:
One shape within a design, such as the grooved 1 x 1 tile.
_Avoid_: Mold, version, revision

**Assembly**:
A factory-combined group of shapes sold under its own part number, such as a wheel with its tire; not itself a shape.
_Avoid_: Composite part, sub-assembly

**Unlisted shape**:
A shape Rebrickable lists only as decorated shapes, such as wings sold only with printed graphics; the condensed census adds it as the shape those decorated shapes fold into.
_Avoid_: Unlisted part, print-only shape, mold

**Rebrickable Census**:
A dated copy of Rebrickable's data, exactly as downloaded: every part number, set, inventory and relationship, with no rules applied.
_Avoid_: Universe, catalog, all parts

**Condensed census**:
The Rebrickable Census with decorated shapes, variants and assemblies condensed into the shapes they stand for, each labeled a candidate or excluded; the source of every coverage figure.
_Avoid_: Catalog, compressed census, folded census

**Candidate**:
A shape StudForge aims to be able to make; candidates are the denominator for coverage.
_Avoid_: Printable, in scope, target

**Excluded**:
A shape StudForge won't make, always recorded with a reason, such as an unprintable material, merchandise, or an incompatible brick system.
_Avoid_: Out of scope, removed, filtered

**Brick system**:
The system of compatible shapes a shape belongs to, set by its stud grid: standard, Duplo, Quatro, Primo or Modulex. Standard and Duplo shapes can be candidates.
_Avoid_: Scale, line, theme

**Family**:
A group of shapes produced by one parametric generator and differing only in size or selectable features, such as the brick family covering 1 x 1 through 2 x 4 and beyond.
_Avoid_: Category, series, type

**Category**:
Rebrickable's classification of a shape (Bricks, Plates, Tiles Special); used only to describe source data.
_Avoid_: Family

## Sets

**Set**:
A model with a parts list: either an official set or a MOC.
_Avoid_: Build (that means a software build), kit, model, project

**Official set**:
A model designed and sold by LEGO, identified by a number like `10698-1`.
_Avoid_: Retail set, product

**MOC**:
A fan-designed model ("My Own Creation"), identified by a number like `MOC-97509`, including alternate models made from one official set's parts.
_Avoid_: Custom set, fan set

**Inventory**:
The list of part numbers, with colors and quantities, needed for one set.
_Avoid_: Parts list, BOM, kit

**Print kit**:
The published, printable package of files for one set.
_Avoid_: Kit, bundle, release

## Coverage

**Shape modeled**:
The first coverage step for a decorated shape, reached on its own once its shape is modeled, since it then has a printable blank.
_Avoid_: Unlocked, blank ready

**Covered**:
A shape or decorated shape whose StudForge model has passed validation against its reference geometry; an assembly is covered when all its shapes are.
_Avoid_: Done, supported, modeled

**Print-tested**:
A covered shape or decorated shape that has been printed with a given filament profile and confirmed to fit.
_Avoid_: Verified, proven

**Usage**:
The total quantity of a shape or decorated shape across every official set in the condensed census, counting shapes in minifigs and quantities inherited from assemblies but not spares; a decorated shape's usage also counts toward its shape's. The main weight for coverage.
_Avoid_: Popularity, frequency

**Reach**:
The number of distinct official sets in the condensed census that contain a shape.
_Avoid_: Usage, popularity

**Usage share**:
A group's usage as a percentage of the total usage of all candidate shapes, or for decorated shapes, of all decorated shapes on candidate shapes.
_Avoid_: % of pieces, popularity

**Shape share**:
The number of shapes in a group as a percentage of all candidate shapes.
_Avoid_: Part share, % of parts, count share

**Decorated shape share**:
The number of decorated shapes in a group as a percentage of all decorated shapes on candidate shapes.
_Avoid_: Decoration share, % of prints

## Dimensions

**Nominal dimension**:
The ideal size of a feature on a shape, before any adjustment for printing.
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
