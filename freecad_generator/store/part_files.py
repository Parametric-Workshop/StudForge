"""The part library's files: saving them. Runs in FreeCAD."""

from __future__ import annotations  # FreeCAD has no Document class to name at run time

import zipfile
from pathlib import Path

import FreeCAD as App


def save(doc: App.Document, path: Path) -> None:
    """Save the document, replacing any older file there without a backup.

    FreeCAD keeps the file it saves over as a .FCBak. A generated file is always
    rebuilt from scratch, so its backup would only take space.
    """
    path.unlink(missing_ok=True)
    doc.saveAs(str(path))
    add_gui_document(doc, path)


def add_gui_document(doc: App.Document, path: Path) -> None:
    """Add to a saved file what the GUI shows: the objects whose Visibility is on.

    FreeCAD without its window saves no GuiDocument.xml, and the GUI then opens
    every object hidden, whatever its Visibility says. This writes the part of
    GuiDocument.xml that says which objects are shown (show_result picks them),
    and the empty camera entry the GUI reads after it.
    """
    shown = [obj.Name for obj in doc.Objects if obj.Visibility]
    entries = "".join(
        f'        <ViewProvider name="{name}">\n'
        '            <Properties Count="1">\n'
        '                <Property name="Visibility" type="App::PropertyBool">\n'
        '                    <Bool value="true"/>\n'
        "                </Property>\n"
        "            </Properties>\n"
        "        </ViewProvider>\n"
        for name in shown
    )
    xml = (
        "<?xml version='1.0' encoding='utf-8'?>\n"
        '<Document SchemaVersion="1">\n'
        f'    <ViewProviderData Count="{len(shown)}">\n{entries}'
        "    </ViewProviderData>\n"
        '    <Camera settings=""/>\n'  # FreeCAD reads one; empty keeps its view
        "</Document>\n"
    )
    with zipfile.ZipFile(path, "a", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("GuiDocument.xml", xml)
