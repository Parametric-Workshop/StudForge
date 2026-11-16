"""Check that census/store/census_db.py is the only census file that holds SQL."""

import ast
import re
from pathlib import Path

CENSUS = Path(__file__).parent.parent
API = CENSUS / "store" / "census_db.py"
SQL = re.compile(
    r"\b(SELECT\s|INSERT\s+(OR\s+\w+\s+)?INTO\s|CREATE\s+(TABLE|INDEX)\s"
    r"|DROP\s+TABLE\s|DELETE\s+FROM\s|UPDATE\s+\w+\s+SET\s)"
)


def text_in_code(source: str) -> list[str]:
    """Return every piece of text in a file's code, f-strings included."""
    return [
        node.value
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]


def test_only_the_api_file_holds_sql_or_knows_sqlite() -> None:
    """No other census file holds a query, or imports sqlite3."""
    for path in sorted(CENSUS.rglob("*.py")):
        if path == API or "tests" in path.parts:
            continue
        source = path.read_text(encoding="utf-8")
        assert "sqlite3" not in source, f"{path.relative_to(CENSUS)} uses sqlite3"
        queries = [text for text in text_in_code(source) if SQL.search(text)]
        assert not queries, f"{path.relative_to(CENSUS)} holds SQL: {queries[0]!r}"


def test_the_check_would_notice_a_query() -> None:
    """The pattern matches the kinds of statement the census uses."""
    for query in (
        'SELECT COUNT(*) FROM "parts"',
        "INSERT OR REPLACE INTO meta VALUES (?,?)",
        "CREATE TABLE coverage (part_num TEXT)",
        "DROP TABLE IF EXISTS coverage",
    ):
        assert SQL.search(query)
    assert not SQL.search("Select a shape to see where it is used.")
