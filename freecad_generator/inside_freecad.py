"""The Part generation service's API: the commands FreeCAD is started with.

The generator's code needs FreeCAD's own Python, so it runs inside FreeCAD. The
client (cli.py) starts FreeCAD on this file and hands it one command:

    verify    check that a generated file survives a person's edits

This file reads the command and calls its operation. FreeCAD's exit code is the
operation's: 1 if anything failed.
"""

import argparse
import sys
import traceback
from collections.abc import Callable
from pathlib import Path

# FreeCAD runs this file by its path, so Python doesn't know the repo folder yet.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from freecad_generator.verifying.run_verify import verify


def main() -> int:
    """Run the command FreeCAD was handed; return 1 if it failed."""
    parser = argparse.ArgumentParser(prog="python3 -m freecad_generator")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("verify")
    parser.parse_args(passed_arguments())
    return verify()


def passed_arguments() -> list[str]:
    """The command and its options: what follows --pass on FreeCAD's command line.

    FreeCAD reads its command line itself and refuses options it doesn't know;
    whatever follows --pass it hands on untouched (cli.py puts it there).
    """
    if "--pass" not in sys.argv:
        return []
    return sys.argv[sys.argv.index("--pass") + 1 :]


def exit_with(main: Callable[[], int]) -> None:
    """Run the main function and exit with its code, or 1 if it raised.

    FreeCADCmd exits with 0 even when a script raises, so a failed run would
    otherwise look like a passing one.
    """
    try:
        code = main()
    except Exception:  # anything: print where it failed, and fail the run
        traceback.print_exc()
        code = 1
    sys.stdout.flush()
    sys.exit(code)


# FreeCADCmd runs this file as a module, not as __main__, so it runs as soon as
# the file is loaded.
exit_with(main)
