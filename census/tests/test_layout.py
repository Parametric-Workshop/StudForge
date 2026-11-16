"""Check that census files only import what the layout allows.

The layout, from census/__init__.py: the client uses only the names that file
offers, and each operation calls only itself and the store.
"""

import ast
from pathlib import Path

import census

CENSUS = Path(__file__).parent.parent
OPERATIONS = ("importing", "condensing", "coverage")


def census_imports(path: Path) -> set[str]:
    """Return the census modules a file imports, such as "census.store.files"."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
            # "from census.store import archive" imports census.store.archive.
            found.update(f"{node.module}.{name.name}" for name in node.names)
        elif isinstance(node, ast.Import):
            found.update(name.name for name in node.names)
    return {name for name in found if name.split(".")[0] == "census"}


def folders_used(folder: str) -> set[str]:
    """Return the census folders and top files that a folder's code imports."""
    return {
        name.split(".")[1]
        for path in (CENSUS / folder).glob("*.py")
        for name in census_imports(path)
        if "." in name
    }


def test_the_client_only_imports_the_api() -> None:
    """Whatever the client needs, it gets from the names census/__init__.py offers."""
    tree = ast.parse((CENSUS / "cli.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules = [name.name for name in node.names]
            assert not [m for m in modules if m.startswith("census.")], modules
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module.split(".")[0] == "census":
                assert node.module == "census", node.module
                assert {name.name for name in node.names} <= set(census.__all__)


def test_the_api_file_only_lists_names() -> None:
    """census/__init__.py holds imports and the list of names, and no code."""
    tree = ast.parse((CENSUS / "__init__.py").read_text(encoding="utf-8"))
    code = [
        node
        for node in tree.body[1:]  # after the docstring
        if not isinstance(node, ast.ImportFrom | ast.Assign)
    ]
    assert not code


def test_each_operation_only_imports_itself_and_the_store() -> None:
    """Operations don't call each other, the API or the client."""
    for operation in OPERATIONS:
        assert folders_used(operation) <= {operation, "store"}, operation


def test_the_store_only_imports_itself() -> None:
    """The store knows nothing of the code that uses it."""
    assert folders_used("store") <= {"store"}
