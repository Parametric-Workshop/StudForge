"""What changed between one condensed census and the next.

The condense operation (census/api.py) compares the condensed census it is about to
replace with the new one, and adds the result to build/census_changes.log. A change
comes from a new Rebrickable snapshot, or from an edit to the folding, family or
exclusion rules; either way, the log says what it did to the shapes StudForge models.

Nothing here reads or writes a file: compare() takes two condensed censuses and
returns sections of text, and report() lays them out.
"""

from dataclasses import dataclass

from census.store.census_db import Assembly, CondensedCensus, DecoratedShape, Shape

# The shape fields whose change is worth a line each, besides the name. Usage,
# reach and years move with every snapshot, so those are counted, not listed.
SHAPE_FIELDS = ["category", "design", "brick_system"]


@dataclass
class Section:
    """One kind of change, and a line for each thing it happened to."""

    title: str
    lines: list[str]


def compare(
    old: CondensedCensus, new: CondensedCensus, tracked: set[str]
) -> list[Section]:
    """Return what changed from old to new, as sections with at least one line.

    tracked is the part numbers recorded in coverage/coverage.csv. Changes that
    touch one of them come first, since those are the ones to act on.
    """
    old_shapes = {s.part_num: s for s in old.shapes}
    new_shapes = {s.part_num: s for s in new.shapes}
    old_decorated = {d.part_num: d for d in old.decorated}
    new_decorated = {d.part_num: d for d in new.decorated}
    old_assemblies = {a.part_num: a for a in old.assemblies}
    new_assemblies = {a.part_num: a for a in new.assemblies}
    both = sorted(old_shapes.keys() & new_shapes.keys())

    sections = [
        Section(
            "Shapes added", named(new_shapes, new_shapes.keys() - old_shapes.keys())
        ),
        Section(
            "Shapes removed", named(old_shapes, old_shapes.keys() - new_shapes.keys())
        ),
        Section(
            "Shapes that became candidates",
            [
                f"{p}  {new_shapes[p].name}  (was excluded: {old_shapes[p].excluded})"
                for p in both
                if old_shapes[p].excluded and not new_shapes[p].excluded
            ],
        ),
        Section(
            "Shapes that are no longer candidates",
            [
                f"{p}  {new_shapes[p].name}  (now excluded: {new_shapes[p].excluded})"
                for p in both
                if not old_shapes[p].excluded and new_shapes[p].excluded
            ],
        ),
        Section(
            "Shapes whose category, design or brick system changed",
            [
                f"{p}  {field}: {getattr(old_shapes[p], field)} -> "
                f"{getattr(new_shapes[p], field)}"
                for p in both
                for field in SHAPE_FIELDS
                if getattr(old_shapes[p], field) != getattr(new_shapes[p], field)
            ],
        ),
        Section(
            "Shapes renamed",
            [
                f"{p}  {old_shapes[p].name} -> {new_shapes[p].name}"
                for p in both
                if old_shapes[p].name != new_shapes[p].name
            ],
        ),
        Section(
            "Decorated shapes added",
            named(new_decorated, new_decorated.keys() - old_decorated.keys()),
        ),
        Section(
            "Decorated shapes removed",
            named(old_decorated, old_decorated.keys() - new_decorated.keys()),
        ),
        Section(
            "Decorated shapes that now fold into a different shape",
            [
                f"{p}  {old_decorated[p].folds_into} -> {new_decorated[p].folds_into}"
                for p in sorted(old_decorated.keys() & new_decorated.keys())
                if old_decorated[p].folds_into != new_decorated[p].folds_into
            ],
        ),
        Section(
            "Assemblies added",
            named(new_assemblies, new_assemblies.keys() - old_assemblies.keys()),
        ),
        Section(
            "Assemblies removed",
            named(old_assemblies, old_assemblies.keys() - new_assemblies.keys()),
        ),
        Section(
            "Assemblies whose shapes changed",
            [
                f"{p}  {' '.join(old_assemblies[p].members)} -> "
                f"{' '.join(new_assemblies[p].members)}"
                for p in sorted(old_assemblies.keys() & new_assemblies.keys())
                if old_assemblies[p].members != new_assemblies[p].members
            ],
        ),
    ]
    sections = [s for s in sections if s.lines]
    affected = [
        f"{line}   [{section.title.lower()}]"
        for section in sections
        for line in section.lines
        if line.split()[0] in tracked
    ]
    if affected:
        sections.insert(0, Section("Tracked in coverage.csv and affected", affected))

    usage_changed = sum(1 for p in both if old_shapes[p].usage != new_shapes[p].usage)
    if usage_changed:
        old_total = sum(s.usage for s in old.shapes)
        new_total = sum(s.usage for s in new.shapes)
        sections.append(
            Section(
                "Usage",
                [
                    f"{usage_changed:,} shapes changed usage; "
                    f"total {old_total:,} -> {new_total:,}"
                ],
            )
        )
    return sections


def named(
    records: dict[str, Shape] | dict[str, DecoratedShape] | dict[str, Assembly],
    part_nums: set[str],
) -> list[str]:
    """Return a "part number  name" line for each of these part numbers, in order."""
    return [f"{p}  {records[p].name}" for p in sorted(part_nums)]


def summary(sections: list[Section]) -> str:
    """Return the changes in one line: "3 shapes added; 1 assemblies removed"."""
    counted = [f"{len(s.lines):,} {s.title.lower()}" for s in sections]
    return "; ".join(counted) if counted else "no changes"


def report(heading: str, sections: list[Section] | None) -> list[str]:
    """Return the log entry for one condense: a heading, then every section.

    sections is None when there was no condensed census to compare with.
    """
    lines = [f"== {heading}"]
    if sections is None:
        return [*lines, "First condensed census: nothing to compare with.", ""]
    if not sections:
        return [*lines, "No changes.", ""]
    for section in sections:
        lines += ["", f"{section.title} ({len(section.lines):,})"]
        lines += [f"  {line}" for line in section.lines]
    return [*lines, ""]
