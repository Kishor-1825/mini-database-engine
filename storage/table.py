"""
storage/table.py
================
In-memory table with optional index support.
"""
from __future__ import annotations
from typing import Any, Callable, Dict, List, Optional, Tuple


class Table:
    """
    An in-memory relational table.

    Parameters
    ----------
    name : str
        Table name.
    schema : list[str]
        Column names in order, e.g. ["id", "name", "age"].
    """

    def __init__(self, name: str, schema: List[str]) -> None:
        self.name = name
        self.schema = schema
        self.rows: List[Tuple] = []
        # column name → HashIndex
        self.hash_indexes: Dict[str, Any] = {}
        # column name → BPlusTree
        self.bptree_indexes: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Core DML
    # ------------------------------------------------------------------

    def insert(self, row: Tuple) -> int:
        """Append a row and update all indexes. Returns the row_id."""
        if len(row) != len(self.schema):
            raise ValueError(
                f"Schema expects {len(self.schema)} columns, got {len(row)}."
            )
        row_id = len(self.rows)
        self.rows.append(row)

        # Update all existing indexes
        for col, idx in self.hash_indexes.items():
            col_pos = self.schema.index(col)
            idx.insert(row[col_pos], row_id)

        for col, idx in self.bptree_indexes.items():
            col_pos = self.schema.index(col)
            idx.insert(row[col_pos], row_id)

        return row_id

    def get(self, row_id: int) -> Optional[Tuple]:
        """Return a row by its ID, or None if out of range."""
        if 0 <= row_id < len(self.rows):
            return self.rows[row_id]
        return None

    def scan(self, predicate: Callable[[Tuple], bool]) -> List[Tuple]:
        """Full table scan. Returns all rows where predicate is True."""
        return [row for row in self.rows if row is not None and predicate(row)]

    def delete_by_id(self, row_id: int) -> bool:
        """Mark a row as deleted (set to None). Returns True if found."""
        if 0 <= row_id < len(self.rows) and self.rows[row_id] is not None:
            self.rows[row_id] = None
            return True
        return False

    # ------------------------------------------------------------------
    # Index management
    # ------------------------------------------------------------------

    def col_index(self, column: str) -> int:
        """Return the integer position of a column name in the schema."""
        try:
            return self.schema.index(column)
        except ValueError:
            raise ValueError(f"Column '{column}' not in schema {self.schema}.")

    def create_hash_index(self, column: str) -> None:
        """Build a hash index on *column* from all existing rows."""
        from index.hash_index import HashIndex

        col_pos = self.col_index(column)
        idx = HashIndex()
        for row_id, row in enumerate(self.rows):
            if row is not None:
                idx.insert(row[col_pos], row_id)
        self.hash_indexes[column] = idx

    def create_bptree_index(self, column: str, max_keys: int = 64) -> None:
        """Build a B+ Tree index on *column* from all existing rows."""
        from index.bptree import BPlusTree

        col_pos = self.col_index(column)
        idx = BPlusTree(max_keys=max_keys)
        for row_id, row in enumerate(self.rows):
            if row is not None:
                idx.insert(row[col_pos], row_id)
        self.bptree_indexes[column] = idx

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        return sum(1 for r in self.rows if r is not None)

    def __repr__(self) -> str:
        return f"<Table '{self.name}' cols={self.schema} rows={len(self)}>"
