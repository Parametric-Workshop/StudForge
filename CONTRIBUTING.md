# Contributing to StudForge

Thanks for helping. StudForge is meant to be readable by Python hobbyists, so clear code matters as much as working code.

## Setup

You need [uv](https://docs.astral.sh/uv/) and git. FreeCAD 1.1.x is only needed for the part generators.

```sh
uv sync                      # installs the pinned check tools into .venv
uv run pre-commit install    # runs the checks before every commit
```

## Checks

Run everything with:

```sh
uv run scripts/check.py
```

The same script runs before each commit and in CI on every push and pull request. Changes to `main` go through a pull request, and the check must pass before merging.

| Check | What it enforces |
|---|---|
| Ruff lint | Style, likely bugs, docstrings on every module and function, type hints on every function signature, and limits on function complexity, length and arguments |
| Ruff format | One consistent code layout. Run `uv run ruff format .` to fix it |
| basedpyright (strict) | Type hints are consistent, and containers say what they hold |
| codespell | Spelling, in American English (`color`, `modeling`, `center`) |
| Suppression audit | No check is switched off with a `noqa`, `type: ignore` or similar comment |

If a check fails, fix the code rather than silencing the check. If you think a rule is wrong for a specific line, say so in your pull request. Approved exceptions are listed in `scripts/suppressions-allowlist.txt`.

## Writing readable code

Tools can't check these, so reviewers will:

- **Use the project's vocabulary.** Terms like part, design, family, build and print offset have specific meanings, defined in [GLOSSARY.md](GLOSSARY.md). Use them, and avoid the synonyms listed there.
- **Spell names out.** Write `part_num` and `set_inventories`, not `pn` and `si`. Short names are fine for short loops (`for r in rows`).
- **Give each function one job**, and name it after that job: `load_sets`, `count_usage`, `write_census`.
- **Comment the why, not the what.** The code already says what it does. Comments explain decisions, data quirks and anything surprising.
- **Name your numbers.** A bare `5` or `0.1` in the code should be a named constant with a comment saying where it comes from.
- **Prefer a plain loop over a clever one-liner.** A nested comprehension that takes a minute to read should be a loop.
- **Start each script with a docstring** saying what it does, what it reads and writes, and how to run it.

Generator scripts run inside FreeCAD's bundled Python (3.13 for FreeCAD 1.1.4), so they may only use the standard library and FreeCAD's own modules.

## Decisions

Significant decisions that would surprise a newcomer are recorded in [docs/adr/](docs/adr/). If your change reverses one, say so in the pull request.

## Naming and licensing

- Code is licensed under LGPL-2.1, matching FreeCAD.
- Say "LEGO-compatible" only as a description. Don't put "LEGO" in project, file, package or part names.
- [openBrick](https://github.com/cwesson/openBrick) is licensed CC BY-NC-SA 4.0, which is incompatible with LGPL-2.1. Use it as a reference for dimensions and tuning values only. Never copy, translate or adapt its code.
- Part and set data is sourced from [Rebrickable](https://rebrickable.com/downloads/). Credit it wherever that data is used.
- Don't commit personal names, email addresses or local file paths. Commit with your GitHub no-reply email address.
