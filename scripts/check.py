"""Run every repo check and report which ones failed.

The pre-commit hook and CI both run this script, so it is the single
definition of "passing". It is plain Python so it works the same on Windows,
macOS and Linux.

Usage:
  uv run scripts/check.py
"""

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# A failing check can print thousands of lines (codespell on a large generated
# file, say). Show this many of them and count the rest, so the summary stays
# readable.
MAX_OUTPUT_LINES = 20

# (description, command). Every check runs, even after one fails, so a single
# run shows everything that needs fixing.
CHECKS = [
    ("ruff check (lint)", ["ruff", "check", "."]),
    ("ruff format --check (formatting)", ["ruff", "format", "--check", "."]),
    ("basedpyright (type checking, strict)", ["basedpyright"]),
    ("codespell (spelling, American English)", ["codespell"]),
    ("pytest (tests)", ["pytest", "-q"]),
    (
        "suppressions (no unapproved rule overrides)",
        [sys.executable, "scripts/check_suppressions.py"],
    ),
]


def main() -> int:
    """Run each check in turn; return 1 if any of them failed."""
    failed: list[str] = []
    for description, command in CHECKS:
        print(f"== {description}", flush=True)
        result = subprocess.run(
            command,
            cwd=REPO,
            check=False,
            capture_output=True,
            text=True,
            errors="replace",
        )
        lines = (result.stdout + result.stderr).splitlines()
        if lines:
            print("\n".join(lines[:MAX_OUTPUT_LINES]))
        if len(lines) > MAX_OUTPUT_LINES:
            print(f"... and {len(lines) - MAX_OUTPUT_LINES:,} more lines")
        if result.returncode != 0:
            failed.append(description)

    if failed:
        print("\nFailed checks:")
        print("\n".join(f"  {name}" for name in failed))
        return 1
    print("\nAll checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
