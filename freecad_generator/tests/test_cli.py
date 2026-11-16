"""The launcher starts the FreeCAD it's given the right way."""

from freecad_generator.cli import freecad_command


def test_an_appimage_is_asked_for_its_command_line_freecad() -> None:
    """An AppImage starts FreeCADCmd when given "freecadcmd" first."""
    command = freecad_command("/opt/FreeCAD_26.3-Linux-x86_64.AppImage")
    assert command == ["/opt/FreeCAD_26.3-Linux-x86_64.AppImage", "freecadcmd"]


def test_a_freecadcmd_program_runs_as_it_is() -> None:
    """Such as Windows' C:/Program Files/FreeCAD 1.1/bin/FreeCADCmd.exe."""
    path = "C:/Program Files/FreeCAD 1.1/bin/FreeCADCmd.exe"
    assert freecad_command(path) == [path]
