"""
query/parser.py
===============
Minimal SQL-like command parser for the mini database engine.

Supported syntax
----------------
CREATE TABLE <name> (<col1>, <col2>, ...)
CREATE INDEX ON <table>(<col>) [USING hash|bptree]
INSERT INTO <table> VALUES (<v1>, <v2>, ...)
SELECT * FROM <table> [WHERE <col> = <val>]
SELECT * FROM <table> WHERE <col> BETWEEN <low> AND <high>
DELETE FROM <table> WHERE <col> = <val>
EXPLAIN SELECT ...
DROP TABLE <name>

Returns a dict AST with a `type` key and command-specific fields.
"""
from __future__ import annotations

import re
from typing import Any, Dict


# ---------------------------------------------------------------------------
# Public
# ---------------------------------------------------------------------------

def parse(command: str) -> Dict[str, Any]:
    """
    Parse a command string and return an AST dict.
    Raises SyntaxError with a helpful message on parse failure.
    """
    cmd = command.strip()
    if not cmd:
        raise SyntaxError("Empty command.")

    upper = cmd.upper()

    if upper.startswith("EXPLAIN"):
        inner = cmd[len("EXPLAIN"):].strip()
        node = parse(inner)
        node["explain"] = True
        return node

    if upper.startswith("CREATE TABLE"):
        return _parse_create_table(cmd)

    if upper.startswith("CREATE INDEX"):
        return _parse_create_index(cmd)

    if upper.startswith("INSERT"):
        return _parse_insert(cmd)

    if upper.startswith("SELECT"):
        return _parse_select(cmd)

    if upper.startswith("DELETE"):
        return _parse_delete(cmd)

    if upper.startswith("DROP TABLE"):
        return _parse_drop_table(cmd)

    raise SyntaxError(f"Unknown command: '{cmd}'")


# ---------------------------------------------------------------------------
# Type coercion helper
# ---------------------------------------------------------------------------

def _coerce(value: str) -> Any:
    """Try to cast a string token to int, float, or strip quotes for str."""
    v = value.strip().strip("'\"")
    try:
        return int(v)
    except ValueError:
        pass
    try:
        return float(v)
    except ValueError:
        pass
    return v


# ---------------------------------------------------------------------------
# Individual parsers
# ---------------------------------------------------------------------------

_CREATE_TABLE_RE = re.compile(
    r'CREATE\s+TABLE\s+(\w+)\s*\(([^)]+)\)',
    re.IGNORECASE,
)


def _parse_create_table(cmd: str) -> Dict[str, Any]:
    m = _CREATE_TABLE_RE.match(cmd)
    if not m:
        raise SyntaxError(
            "Expected: CREATE TABLE <name> (<col1>, <col2>, ...)\n"
            f"Got: {cmd}"
        )
    name = m.group(1)
    cols = [c.strip() for c in m.group(2).split(",")]
    return {"type": "create_table", "table": name, "schema": cols}


_CREATE_INDEX_RE = re.compile(
    r'CREATE\s+INDEX\s+ON\s+(\w+)\s*\((\w+)\)(?:\s+USING\s+(\w+))?',
    re.IGNORECASE,
)


def _parse_create_index(cmd: str) -> Dict[str, Any]:
    m = _CREATE_INDEX_RE.match(cmd)
    if not m:
        raise SyntaxError(
            "Expected: CREATE INDEX ON <table>(<col>) [USING hash|bptree]\n"
            f"Got: {cmd}"
        )
    index_type = (m.group(3) or "bptree").lower()
    if index_type not in ("hash", "bptree"):
        raise SyntaxError(f"Unknown index type '{index_type}'. Use 'hash' or 'bptree'.")
    return {
        "type": "create_index",
        "table": m.group(1),
        "column": m.group(2),
        "index_type": index_type,
    }


_INSERT_RE = re.compile(
    r'INSERT\s+INTO\s+(\w+)\s+VALUES\s*\((.+)\)',
    re.IGNORECASE,
)


def _parse_insert(cmd: str) -> Dict[str, Any]:
    m = _INSERT_RE.match(cmd)
    if not m:
        raise SyntaxError(
            "Expected: INSERT INTO <table> VALUES (<v1>, <v2>, ...)\n"
            f"Got: {cmd}"
        )
    values = [_coerce(v) for v in m.group(2).split(",")]
    return {"type": "insert", "table": m.group(1), "values": values}


_SELECT_EQ_RE = re.compile(
    r'SELECT\s+\*\s+FROM\s+(\w+)\s+WHERE\s+(\w+)\s*=\s*(.+)',
    re.IGNORECASE,
)
_SELECT_BETWEEN_RE = re.compile(
    r'SELECT\s+\*\s+FROM\s+(\w+)\s+WHERE\s+(\w+)\s+BETWEEN\s+(.+?)\s+AND\s+(.+)',
    re.IGNORECASE,
)
_SELECT_ALL_RE = re.compile(
    r'SELECT\s+\*\s+FROM\s+(\w+)',
    re.IGNORECASE,
)


def _parse_select(cmd: str) -> Dict[str, Any]:
    # Try BETWEEN first (more specific)
    m = _SELECT_BETWEEN_RE.match(cmd)
    if m:
        return {
            "type": "select",
            "table": m.group(1),
            "column": m.group(2),
            "op": "BETWEEN",
            "low": _coerce(m.group(3)),
            "high": _coerce(m.group(4)),
        }
    m = _SELECT_EQ_RE.match(cmd)
    if m:
        return {
            "type": "select",
            "table": m.group(1),
            "column": m.group(2),
            "op": "=",
            "value": _coerce(m.group(3)),
        }
    m = _SELECT_ALL_RE.match(cmd)
    if m:
        return {"type": "select", "table": m.group(1), "op": "ALL"}
    raise SyntaxError(
        "Expected: SELECT * FROM <table> [WHERE <col> = <val> | WHERE <col> BETWEEN <lo> AND <hi>]\n"
        f"Got: {cmd}"
    )


_DELETE_RE = re.compile(
    r'DELETE\s+FROM\s+(\w+)\s+WHERE\s+(\w+)\s*=\s*(.+)',
    re.IGNORECASE,
)


def _parse_delete(cmd: str) -> Dict[str, Any]:
    m = _DELETE_RE.match(cmd)
    if not m:
        raise SyntaxError(
            "Expected: DELETE FROM <table> WHERE <col> = <val>\n"
            f"Got: {cmd}"
        )
    return {
        "type": "delete",
        "table": m.group(1),
        "column": m.group(2),
        "value": _coerce(m.group(3)),
    }


_DROP_TABLE_RE = re.compile(r'DROP\s+TABLE\s+(\w+)', re.IGNORECASE)


def _parse_drop_table(cmd: str) -> Dict[str, Any]:
    m = _DROP_TABLE_RE.match(cmd)
    if not m:
        raise SyntaxError(f"Expected: DROP TABLE <name>\nGot: {cmd}")
    return {"type": "drop_table", "table": m.group(1)}
