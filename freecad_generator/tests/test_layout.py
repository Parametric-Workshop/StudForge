"""Check that generator files only import what the layout allows.

The layout, from freecad_generator/__init__.py: the client imports nothing of the
generator (it starts FreeCAD), the API calls the operations, each operation uses
only itself, the families and the store, and the store uses only itself.
"""

import ast
from pathlib import Path

GENERATOR = Path(__file__).parent.parent
OPERATIONS = ("generating", "verifying")


def folders_used(*paths: Path) -> set[str]:
    """Return the generator folders and top files that some files import."""
    found: set[str] = set()
    for path in paths:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.module:
                parts = node.module.split(".")
                if parts[0] == GENERATOR.name:
                    found.add(parts[1] if len(parts) > 1 else node.names[0].name)
    return found


def in_folder(folder: str) -> list[Path]:
    """Return a folder's Python files."""
    return sorted((GENERATOR / folder).glob("*.py"))


def test_the_client_imports_nothing_of_the_generator() -> None:
    """The client runs in ordinary Python, where FreeCAD's modules don't exist."""
    assert not folders_used(GENERATOR / "cli.py")


def test_the_api_only_calls_the_operations() -> None:
    """The file FreeCAD is started on hands each command to its operation."""
    assert folders_used(GENERATOR / "inside_freecad.py") == set(OPERATIONS)


def test_each_operation_only_imports_itself_the_families_and_the_store() -> None:
    """Operations don't call each other, the API or the client."""
    for operation in OPERATIONS:
        allowed = {operation, "families", "store"}
        assert folders_used(*in_folder(operation)) <= allowed, operation


def test_the_families_only_import_themselves_and_the_store() -> None:
    """A family's model knows nothing of the operations that use it."""
    assert folders_used(*in_folder("families")) <= {"families", "store"}


def test_the_store_only_imports_itself() -> None:
    """The store knows nothing of the code that uses it."""
    assert folders_used(*in_folder("store")) <= {"store"}
