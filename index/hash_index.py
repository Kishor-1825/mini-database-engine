"""
index/hash_index.py
===================
A simple hash index mapping key → list[row_id].

Uses Python's built-in dict as the hash table. For extra learning, replace
self._map with a custom open-addressing or chaining implementation.
"""
from __future__ import annotations
from typing import Any, Dict, List


class HashIndex:
    """
    Hash index for O(1) average equality lookup.

    Supports non-unique keys: each key maps to a *list* of row_ids so that
    columns with repeated values (e.g. `age`) work correctly.
    """

    def __init__(self) -> None:
        self._map: Dict[Any, List[int]] = {}

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def insert(self, key: Any, row_id: int) -> None:
        """Add a (key → row_id) mapping."""
        if key not in self._map:
            self._map[key] = []
        self._map[key].append(row_id)

    def delete(self, key: Any, row_id: int) -> bool:
        """Remove a specific (key, row_id) pair. Returns True if found."""
        bucket = self._map.get(key)
        if bucket is None:
            return False
        try:
            bucket.remove(row_id)
        except ValueError:
            return False
        if not bucket:
            del self._map[key]
        return True

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def lookup(self, key: Any) -> List[int]:
        """Return all row_ids for *key*, or [] if not found."""
        return list(self._map.get(key, []))

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        """Number of distinct keys."""
        return len(self._map)

    def __repr__(self) -> str:
        return f"<HashIndex keys={len(self._map)}>"
