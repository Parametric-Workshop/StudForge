---
status: proposed
---

# Generated files stay editable

Every FreeCAD file the generator writes can be edited in FreeCAD's `Params` without running any Python. How far that goes depends on the shape. A **sized family**, such as the block family, holds its size rules as expressions: setting `Width` to 3 in `3001.FCStd` gives a correct 3 x 4 brick. A **fixed shape**, made by its own generator because no other real shape shares its layout, can't be resized, but its nominal values and print offsets stay in `Params`, so a fit can still be tuned by hand. We chose this over making every shape resizable, because most shapes come in a single size: for those, size rules would be code written twice for an edit nobody makes.

## Considered options

- **Python decides, the file obeys**: the generator makes the size decisions in Python and switches features on or off before saving. Simpler to write, but each file is right only at the size it was generated at, and looks parametric while quietly breaking when a person resizes it.
- **Every shape resizable**: one rule set for everything, at the cost of size rules for shapes that only come in one size, and of shapes whose layout no expression can describe.

## Consequences

In a sized family, each rule is written as a FreeCAD expression in the file and again in plain Python, so some logic that would be one line of Python becomes a longer expression. FreeCAD 1.1.4 has known problems that a Python generator could work around after each edit but a file has to avoid by how it's built, such as a feature coming back from suppression with a stale placement, which the files avoid by attaching every sketch to a plane. So a sized family is tested by reopening a generated file, editing it, and checking every result against its plain-Python rules and against a fresh build. A fixed shape has no size rules to test; it is checked against its reference geometry. This ADR stays proposed until the tests pass on a FreeCAD release the files are meant for.
