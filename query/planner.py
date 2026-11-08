"""
query/planner.py
================
Query planner and executor for the mini database engine.

The planner decides which strategy to use for each SELECT:
  1. Hash index lookup      — equality on a hash-indexed column    O(1)
  2. B+ Tree search         — equality on a bptree-indexed column  O(log n)
  3. B+ Tree range search   — BETWEEN on a bptree-indexed column   O(log n + k)
  4. Full table scan        — no suitable index                    O(n)

It also executes CREATE TABLE, CREATE INDEX, INSERT, DELETE, DROP TABLE
commands and returns human-readable result strings.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from storage.table import Table


# ---------------------------------------------------------------------------
# Database (collection of tables)
# ---------------------------------------------------------------------------

class Database:
    """Holds a set of named tables and executes parsed AST commands."""

    def __init__(self) -> None:
        self.tables: Dict[str, Table] = {}

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    def execute(self, ast: Dict[str, Any]) -> str:
        """Execute a parsed AST node. Returns a result string."""
        explain = ast.get("explain", False)
        t = ast["type"]

        if t == "create_table":
            return self._exec_create_table(ast)
        if t == "create_index":
            return self._exec_create_index(ast)
        if t == "insert":
            return self._exec_insert(ast)
        if t == "select":
            if explain:
                return self._explain_select(ast)
            return self._exec_select(ast)
        if t == "delete":
            return self._exec_delete(ast)
        if t == "drop_table":
            return self._exec_drop_table(ast)

        raise ValueError(f"Unknown AST type: '{t}'")

    # ------------------------------------------------------------------
    # DDL
    # ------------------------------------------------------------------

    def _exec_create_table(self, ast: Dict) -> str:
        name = ast["table"]
        if name in self.tables:
            return f"ERROR: Table '{name}' already exists."
        self.tables[name] = Table(name, ast["schema"])
        return f"Table '{name}' created with schema {ast['schema']}."

    def _exec_create_index(self, ast: Dict) -> str:
        tbl = self._get_table(ast["table"])
        col = ast["column"]
        idx_type = ast["index_type"]
        if idx_type == "hash":
            tbl.create_hash_index(col)
            return f"Hash index created on {ast['table']}({col})."
        else:
            tbl.create_bptree_index(col)
            return f"B+ Tree index created on {ast['table']}({col})."

    def _exec_drop_table(self, ast: Dict) -> str:
        name = ast["table"]
        if name not in self.tables:
            return f"ERROR: Table '{name}' does not exist."
        del self.tables[name]
        return f"Table '{name}' dropped."

    # ------------------------------------------------------------------
    # DML — Insert
    # ------------------------------------------------------------------

    def _exec_insert(self, ast: Dict) -> str:
        tbl = self._get_table(ast["table"])
        row_id = tbl.insert(tuple(ast["values"]))
        return f"Inserted row_id={row_id}: {tuple(ast['values'])}."

    # ------------------------------------------------------------------
    # DML — Select
    # ------------------------------------------------------------------

    def _exec_select(self, ast: Dict) -> str:
        tbl = self._get_table(ast["table"])
        rows, strategy = self._run_select(tbl, ast)
        if not rows:
            return f"(0 rows) [{strategy}]"
        header = " | ".join(tbl.schema)
        lines = [f"  {header}", "  " + "-" * len(header)]
        for row in rows:
            lines.append("  " + " | ".join(str(v) for v in row))
        lines.append(f"({len(rows)} row{'s' if len(rows) != 1 else ''}) [{strategy}]")
        return "\n".join(lines)

    def _explain_select(self, ast: Dict) -> str:
        tbl = self._get_table(ast["table"])
        strategy = self._choose_strategy(tbl, ast)
        return f"EXPLAIN: {strategy}"

    def _run_select(
        self, tbl: Table, ast: Dict
    ) -> Tuple[List[Tuple], str]:
        """Execute the SELECT and return (matching rows, strategy name)."""
        op = ast.get("op", "ALL")

        if op == "ALL":
            return list(r for r in tbl.rows if r is not None), "Full table scan"

        col = ast["column"]
        col_pos = tbl.col_index(col)
        strategy = self._choose_strategy(tbl, ast)

        if op == "=" and col in tbl.hash_indexes:
            row_ids = tbl.hash_indexes[col].lookup(ast["value"])
            rows = [tbl.get(rid) for rid in row_ids if tbl.get(rid) is not None]
            return rows, strategy

        if op == "=" and col in tbl.bptree_indexes:
            row_ids = tbl.bptree_indexes[col].search(ast["value"])
            rows = [tbl.get(rid) for rid in row_ids if tbl.get(rid) is not None]
            return rows, strategy

        if op == "BETWEEN" and col in tbl.bptree_indexes:
            row_ids = tbl.bptree_indexes[col].range_search(ast["low"], ast["high"])
            rows = [tbl.get(rid) for rid in row_ids if tbl.get(rid) is not None]
            return rows, strategy

        # Fallback: full table scan
        if op == "=":
            rows = tbl.scan(lambda r: r[col_pos] == ast["value"])
        elif op == "BETWEEN":
            rows = tbl.scan(lambda r: ast["low"] <= r[col_pos] <= ast["high"])
        else:
            rows = list(r for r in tbl.rows if r is not None)
        return rows, strategy

    def _choose_strategy(self, tbl: Table, ast: Dict) -> str:
        op = ast.get("op", "ALL")
        if op == "ALL":
            return "Full table scan (no WHERE clause)"
        col = ast.get("column", "")
        if op == "=" and col in tbl.hash_indexes:
            return f"Hash index lookup on '{col}'"
        if op == "=" and col in tbl.bptree_indexes:
            return f"B+ Tree point lookup on '{col}'"
        if op == "BETWEEN" and col in tbl.bptree_indexes:
            return f"B+ Tree range scan on '{col}' [{ast['low']}, {ast['high']}]"
        return f"Full table scan (no index on '{col}')"

    # ------------------------------------------------------------------
    # DML — Delete
    # ------------------------------------------------------------------

    def _exec_delete(self, ast: Dict) -> str:
        tbl = self._get_table(ast["table"])
        col = ast["column"]
        col_pos = tbl.col_index(col)
        value = ast["value"]

        # Find matching row IDs
        row_ids = []
        if col in tbl.hash_indexes:
            row_ids = tbl.hash_indexes[col].lookup(value)
        elif col in tbl.bptree_indexes:
            row_ids = tbl.bptree_indexes[col].search(value)
        else:
            row_ids = [i for i, r in enumerate(tbl.rows)
                       if r is not None and r[col_pos] == value]

        count = 0
        for rid in row_ids:
            if tbl.delete_by_id(rid):
                # Remove from indexes
                for c, idx in tbl.hash_indexes.items():
                    row = tbl.rows[rid]  # already None
                    # We stored value before deletion; re-derive from rid history
                    idx.delete(value, rid)
                for c, idx in tbl.bptree_indexes.items():
                    idx.delete(value, rid)
                count += 1

        return f"Deleted {count} row(s) where {col} = {value!r}."

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_table(self, name: str) -> Table:
        if name not in self.tables:
            raise KeyError(f"Table '{name}' does not exist.")
        return self.tables[name]

    def list_tables(self) -> str:
        if not self.tables:
            return "No tables."
        lines = ["Tables:"]
        for name, tbl in self.tables.items():
            hash_cols = list(tbl.hash_indexes.keys())
            bpt_cols = list(tbl.bptree_indexes.keys())
            lines.append(
                f"  {name}  schema={tbl.schema}  rows={len(tbl)}"
                f"  hash_idx={hash_cols}  bptree_idx={bpt_cols}"
            )
        return "\n".join(lines)
