"""The generator's client: reads the command line, finds FreeCAD and starts it.

The generator's code needs FreeCAD's own Python, so it runs inside FreeCAD. This
client runs in ordinary Python: it finds FreeCAD and starts it, without its
window, on inside_freecad.py, handing on the command with FreeCAD's --pass.

Run it from the repo folder:

    python3 -m freecad_generator generate          (only the shapes that changed)
    python3 -m freecad_generator generate --all    (every shape again)
    python3 -m freecad_generator verify
    python3 -m freecad_generator verify --freecad PATH   (another FreeCAD)

FreeCAD is found, in order: --freecad (an AppImage, or a FreeCADCmd program),
the Flatpak org.freecad.FreeCAD, FreeCADCmd on the PATH, then the usual install
folders on Windows and macOS. Only the Flatpak and AppImage have been tried.
The run's exit code is the command's.
"""

import argparse
import glob
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
COMMANDS = ("generate", "verify")
FLATPAK = "org.freecad.FreeCAD"
# Where FreeCAD's installers put FreeCADCmd, newest version last when sorted.
INSTALLS = (
    "C:/Program Files/FreeCAD*/bin/FreeCADCmd.exe",
    "/Applications/FreeCAD*.app/Contents/Resources/bin/FreeCADCmd",
)


def freecad_command(given: str | None) -> list[str]:
    """The command that starts FreeCAD without its window."""
    if given:
        path = Path(given).expanduser()
        if path.suffix == ".AppImage":  # an AppImage starts FreeCADCmd when asked
            return [str(path), "freecadcmd"]
        return [str(path)]
    if shutil.which("flatpak") and has_flatpak():
        return ["flatpak", "run", "--command=FreeCADCmd", FLATPAK]
    for name in ("FreeCADCmd", "freecadcmd"):
        found = shutil.which(name)
        if found:
            return [found]
    for pattern in INSTALLS:
        installed = sorted(glob.glob(pattern))
        if installed:
            return [installed[-1]]
    raise SystemExit(
        "FreeCAD not found: install it, or name its FreeCADCmd with --freecad"
    )


def has_flatpak() -> bool:
    """Whether FreeCAD's Flatpak is installed."""
    result = subprocess.run(
        ["flatpak", "info", FLATPAK], capture_output=True, check=False
    )
    return result.returncode == 0


def main() -> int:
    """Start FreeCAD on the chosen command; return the command's exit code."""
    parser = argparse.ArgumentParser(
        prog="python3 -m freecad_generator",
        description="Run a generator command in FreeCAD; options after its name "
        "are the command's.",
    )
    parser.add_argument("command", choices=COMMANDS)
    parser.add_argument("--freecad", help="FreeCADCmd, or an AppImage, to run it with")
    args, options = parser.parse_known_args()
    command = [*freecad_command(args.freecad), str(HERE / "inside_freecad.py")]
    # FreeCAD hands on whatever follows --pass to the file it runs.
    command += ["--pass", args.command, *options]
    return subprocess.run(command, cwd=REPO, check=False).returncode
