"""Fail if any file switches off a check without the owner's approval.

Linters can be silenced line by line with comments such as `# noqa` or
`# codespell:ignore`. Each such comment must be listed in
scripts/suppressions-allowlist.txt, which only the owner edits, as:

    path/to/file.py: the full line, stripped of surrounding whitespace

Usage:
  python3 scripts/check_suppressions.py
"""

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ALLOWLIST_PATH = REPO / "scripts" / "suppressions-allowlist.txt"

# Comments that turn off a check for a line, a block or a whole file.
SUPPRESSION = re.compile(
    r"#\s*(noqa|ruff\s*:\s*noqa|type\s*:\s*ignore|fmt\s*:\s*(off|skip)|codespell\s*:\s*ignore)",
    re.IGNORECASE,
)

# This file and the allowlist name the patterns, so they can't be checked by them.
EXEMPT = {"scripts/check_suppressions.py", "scripts/suppressions-allowlist.txt"}


def tracked_files() -> list[str]:
    """Return the repo's files that git tracks or would add (respects ignores)."""
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.splitlines()


def load_allowlist() -> set[str]:
    """Return the approved suppressions as 'path: line' strings."""
    if not ALLOWLIST_PATH.exists():
        return set()
    lines = ALLOWLIST_PATH.read_text(encoding="utf-8").splitlines()
    return {line.strip() for line in lines if line.strip() and not line.startswith("#")}


def find_suppressions(path: str) -> list[tuple[int, str]]:
    """Return (line number, line) for every suppression comment in one file."""
    try:
        text = (REPO / path).read_text(encoding="utf-8")
    except (UnicodeDecodeError, FileNotFoundError):
        return []  # binary or deleted files can't hold comments
    found: list[tuple[int, str]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if SUPPRESSION.search(line):
            found.append((number, line.strip()))
    return found


def main() -> int:
    """Report unapproved suppressions; return 1 if any are found."""
    allowed = load_allowlist()
    problems: list[str] = []
    for path in tracked_files():
        if path in EXEMPT:
            continue
        for number, line in find_suppressions(path):
            if f"{path}: {line}" not in allowed:
                problems.append(f"{path}:{number}: {line}")
    if problems:
        print("Unapproved check suppressions (allowlist only with owner approval):")
        print("\n".join(f"  {p}" for p in problems))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
