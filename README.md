# StudForge

Parametric, print-tuned building bricks in FreeCAD.

StudForge is an open library of parametric building bricks, modeled in FreeCAD and tuned for FDM printing. Bricks are built from adjustable shape families, with separate tolerance settings for studs, tubes, and walls, so you can dial in clutch for your printer and filament.

## Goals

The goal is to go from real instructions to printed parts:

- Parametric brick, plate, and tile families, with more on the way
- Per-feature print tolerances and per-filament profiles
- Validation against LDraw reference geometry
- Import of LDraw models (`.ldr`) as FreeCAD assemblies
- Per-color export for slicers like Orca
- Community print reports, so you know what works before you print it

It's also a real-world test bed for FreeCAD's assembly workbench, and a FreeCAD workbench version (StudForge Bench) is planned.

## Status

StudForge is part of the [Parametric Workshop](https://www.youtube.com/@parametricworkshop) channel. It's early, so expect rough edges.

## Census

StudForge tracks which real shapes it can print, weighted by how often each shape appears in official sets. A shape is one distinct geometry, whatever its color or decoration. The counts come from a local database built in two steps: the Rebrickable Census, a copy of Rebrickable's free CSV downloads, and the condensed census, which folds decorated shapes, variants and assemblies into the shapes they stand for and labels each shape a candidate or excluded.

1. Download Rebrickable's latest snapshot and build the census from it:

   ```sh
   python3 census/census.py --download
   ```

   Rebrickable allows this at most once a day, so a second download within 24 hours is refused. The CSVs are kept in `downloads/rebrickable/<date>/`, which you shouldn't delete: older snapshots can't be downloaded again. After a download, it prints what changed since the previous snapshot and saves those counts and every new, removed and renamed part number to `changes.txt` in the same folder. If you already have the CSVs from [rebrickable.com/downloads](https://rebrickable.com/downloads/), give their folder instead: `python3 census/census.py path/to/rebrickable_csvs`.

   Either way, building takes a few seconds. It copies every CSV into `build/census.sqlite` (local only) and records the snapshot's date and file checksums in `census/census-manifest.json`.
2. Build the condensed census:

   ```sh
   python3 census/condense.py
   ```

   This adds the condensed tables to the same database. You rarely need to run it yourself: the next step runs it again whenever a rule has changed (folding in `census/folding.py`, usage in `census/usage.py`, candidates in `census/candidates.py`, the tables in `census/condensed_census.py`, or `census/condense.py` itself).
3. Build the census viewer:

   ```sh
   python3 census/census_viewer.py
   ```

   This is the one command to rerun after changing anything, and on a fresh clone it's the only one you need. It builds the census if it's missing or out of date (from the CSVs in `downloads/rebrickable/` if they're there, otherwise by downloading the latest snapshot), and condenses it again if a rule changed. It prints a summary of the condensed census and of StudForge's coverage, and writes `build/census_viewer.html`, a single page you can open in any browser. The page loads its JavaScript libraries from jsDelivr, so opening it needs internet. The viewer starts from every Rebrickable part number and lets you drill down through candidates and exclusions, brick systems, category groups, categories and families to individual shapes. Under each shape are its decorated shapes and the assemblies it's in. Every level shows shape share, usage share and coverage, and how many decorated shapes it holds and how many of those are covered. Hover over a dotted-underlined term to see its definition from [GLOSSARY.md](GLOSSARY.md).

Coverage is tracked in `coverage/coverage.csv`, one row per part number (a shape or a decorated shape) with a status: `planned`, `modeled`, `validated` or `print-tested`. Category groups and families are kept in `census/groups.toml` and `census/families.toml`. Each set StudForge aims to print has its inventory in `coverage/sets/official/` or `coverage/sets/moc/`. See [GLOSSARY.md](GLOSSARY.md) for what the terms mean.

The viewer page uses [D3](https://d3js.org) (ISC), [d3-flextree](https://github.com/klortho/d3-flextree) (WTFPL) and [d3-org-chart](https://github.com/bumbeishvili/org-chart) (MIT), loaded at pinned versions from jsDelivr; see `census/viewer_template.html`.

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, the repo checks, and coding guidelines.

## Data sources

Part, set and inventory data is sourced from [Rebrickable](https://rebrickable.com/downloads/), used under their terms with thanks.

---

*LEGO® is a trademark of the LEGO Group, which does not sponsor, authorize, or endorse this project.*
