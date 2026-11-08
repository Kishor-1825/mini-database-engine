"""
index/bptree.py
===============
B+ Tree index implementation.

Key design choices
------------------
* Leaf nodes store: keys[], values[] (each value is a list[row_id]),
  and a `next` pointer to the right sibling leaf.
* Internal nodes store: keys[] (separator keys), children[] (child nodes).
* `max_keys` is the maximum number of keys allowed in any node before a
  split is triggered.  Use max_keys=3 while debugging so splits happen
  constantly and bugs surface quickly.
* All keys must be comparable with < and ==.

Operations
----------
search(key)                 → list[row_id]
insert(key, row_id)         → None   (triggers splits as needed)
range_search(low, high)     → list[row_id]  (walk leaf chain)
delete(key, row_id)         → bool   (borrow / merge / root-shrink)
validate()                  → None   (raises AssertionError on invariant violation)
visualize()                 → str    (Graphviz DOT source)
"""
from __future__ import annotations
from typing import Any, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

class _Node:
    __slots__ = ("keys", "children", "values", "next", "is_leaf")

    def __init__(self, is_leaf: bool) -> None:
        self.is_leaf: bool = is_leaf
        self.keys: List[Any] = []

        # Internal nodes only
        self.children: List[_Node] = []

        # Leaf nodes only
        self.values: List[List[int]] = []   # parallel to keys; each is a list of row_ids
        self.next: Optional[_Node] = None   # right sibling leaf


# ---------------------------------------------------------------------------
# B+ Tree
# ---------------------------------------------------------------------------

class BPlusTree:
    """
    B+ Tree ordered index.

    Parameters
    ----------
    max_keys : int
        Maximum keys per node before a split.  Minimum useful value is 2.
        Use 3 during development; 64 or higher for production.
    """

    def __init__(self, max_keys: int = 64) -> None:
        if max_keys < 2:
            raise ValueError("max_keys must be >= 2.")
        self.max_keys = max_keys
        self._min_keys = max_keys // 2          # minimum keys in non-root node
        self._root: _Node = _Node(is_leaf=True)
        self._height: int = 1

    # ==================================================================
    # Public API
    # ==================================================================

    def search(self, key: Any) -> List[int]:
        """Return all row_ids stored under *key*, or [] if not found."""
        leaf = self._find_leaf(key)
        idx = self._leaf_key_index(leaf, key)
        if idx is not None:
            return list(leaf.values[idx])
        return []

    def insert(self, key: Any, row_id: int) -> None:
        """Insert (key, row_id). Splits nodes as necessary."""
        result = self._insert(self._root, key, row_id)
        if result is not None:
            # Root split: create a new root
            mid_key, new_child = result
            new_root = _Node(is_leaf=False)
            new_root.keys = [mid_key]
            new_root.children = [self._root, new_child]
            self._root = new_root
            self._height += 1

    def range_search(self, low: Any, high: Any) -> List[int]:
        """Return all row_ids for keys in [low, high] (inclusive)."""
        result: List[int] = []
        leaf = self._find_leaf(low)
        while leaf is not None:
            for i, k in enumerate(leaf.keys):
                if k > high:
                    return result
                if k >= low:
                    result.extend(leaf.values[i])
            leaf = leaf.next
        return result

    def delete(self, key: Any, row_id: int) -> bool:
        """
        Remove (key, row_id).  Performs borrow / merge / root-shrink to
        maintain balance.  Returns True if the pair was found and removed.
        """
        found, _ = self._delete(self._root, key, row_id, parent=None, parent_idx=None)
        # If root is now an internal node with 0 keys and 1 child, shrink
        if (
            not self._root.is_leaf
            and len(self._root.keys) == 0
            and len(self._root.children) == 1
        ):
            self._root = self._root.children[0]
            self._height -= 1
        return found

    # ==================================================================
    # Validation
    # ==================================================================

    def validate(self) -> None:
        """
        Check all B+ Tree invariants.  Raises AssertionError with a
        descriptive message on the first violation found.
        """
        self._validate_node(self._root, min_key=None, max_key=None, depth=0,
                            expected_leaf_depth=self._height - 1)
        # Check leaf chain is sorted and contiguous
        prev_key: Any = None
        node = self._leftmost_leaf()
        while node is not None:
            for k in node.keys:
                assert prev_key is None or k >= prev_key, (
                    f"Leaf chain out of order: {prev_key} then {k}"
                )
                prev_key = k
            node = node.next

    # ==================================================================
    # Visualisation (Graphviz DOT)
    # ==================================================================

    def visualize(self, title: str = "B+ Tree") -> str:
        """Return a Graphviz DOT string for the tree."""
        lines = [
            'digraph BPlusTree {',
            f'  label="{title}";',
            '  node [shape=record fontname="Courier"];',
        ]
        self._dot_node(self._root, lines, [0])
        lines.append('}')
        return '\n'.join(lines)

    def _dot_node(self, node: _Node, lines: List[str], counter: List[int]) -> int:
        my_id = counter[0]
        counter[0] += 1
        label_parts = [f"<k{i}> {k}" for i, k in enumerate(node.keys)]
        label = "|".join(label_parts) if label_parts else "∅"
        style = 'style="filled" fillcolor="#d0e8ff"' if node.is_leaf else ''
        lines.append(f'  n{my_id} [label="{{{label}}}" {style}];')
        if not node.is_leaf:
            for child in node.children:
                child_id = self._dot_node(child, lines, counter)
                lines.append(f'  n{my_id} -> n{child_id};')
        return my_id

    # ==================================================================
    # Internal helpers — search / leaf navigation
    # ==================================================================

    def _find_leaf(self, key: Any) -> _Node:
        """Walk from root to the leaf where *key* belongs."""
        node = self._root
        while not node.is_leaf:
            idx = self._child_index(node, key)
            node = node.children[idx]
        return node

    @staticmethod
    def _child_index(node: _Node, key: Any) -> int:
        """Return the index of the child to follow for *key* in an internal node."""
        for i, k in enumerate(node.keys):
            if key < k:
                return i
        return len(node.keys)

    @staticmethod
    def _leaf_key_index(leaf: _Node, key: Any) -> Optional[int]:
        """Return position of *key* in leaf.keys, or None if absent."""
        for i, k in enumerate(leaf.keys):
            if k == key:
                return i
        return None

    def _leftmost_leaf(self) -> _Node:
        node = self._root
        while not node.is_leaf:
            node = node.children[0]
        return node

    # ==================================================================
    # Internal helpers — insert
    # ==================================================================

    def _insert(
        self, node: _Node, key: Any, row_id: int
    ) -> Optional[Tuple[Any, _Node]]:
        """
        Recursively insert (key, row_id) starting at *node*.
        Returns (promoted_key, new_right_child) if this node split,
        else None.
        """
        if node.is_leaf:
            self._leaf_insert(node, key, row_id)
            if len(node.keys) > self.max_keys:
                return self._split_leaf(node)
            return None
        else:
            idx = self._child_index(node, key)
            result = self._insert(node.children[idx], key, row_id)
            if result is not None:
                mid_key, new_child = result
                self._internal_insert_child(node, idx, mid_key, new_child)
                if len(node.keys) > self.max_keys:
                    return self._split_internal(node)
            return None

    @staticmethod
    def _leaf_insert(leaf: _Node, key: Any, row_id: int) -> None:
        """Insert key/row_id into a leaf in sorted order."""
        for i, k in enumerate(leaf.keys):
            if key == k:
                leaf.values[i].append(row_id)
                return
            if key < k:
                leaf.keys.insert(i, key)
                leaf.values.insert(i, [row_id])
                return
        leaf.keys.append(key)
        leaf.values.append([row_id])

    def _split_leaf(self, leaf: _Node) -> Tuple[Any, _Node]:
        """
        Split a full leaf in half.
        Returns (first_key_of_new_right_leaf, new_right_leaf).
        The first key of the right leaf is *copied* up (not moved).
        """
        mid = len(leaf.keys) // 2
        new_leaf = _Node(is_leaf=True)
        new_leaf.keys = leaf.keys[mid:]
        new_leaf.values = leaf.values[mid:]
        new_leaf.next = leaf.next

        leaf.keys = leaf.keys[:mid]
        leaf.values = leaf.values[:mid]
        leaf.next = new_leaf

        return new_leaf.keys[0], new_leaf

    @staticmethod
    def _internal_insert_child(
        node: _Node, child_idx: int, mid_key: Any, new_child: _Node
    ) -> None:
        """Insert mid_key and new_child into an internal node at the right spot."""
        node.keys.insert(child_idx, mid_key)
        node.children.insert(child_idx + 1, new_child)

    def _split_internal(self, node: _Node) -> Tuple[Any, _Node]:
        """
        Split a full internal node in half.
        The *middle* key is *pushed up* (not copied) — it leaves this node.
        Returns (pushed_up_key, new_right_internal_node).
        """
        mid = len(node.keys) // 2
        mid_key = node.keys[mid]

        new_node = _Node(is_leaf=False)
        new_node.keys = node.keys[mid + 1:]
        new_node.children = node.children[mid + 1:]

        node.keys = node.keys[:mid]
        node.children = node.children[:mid + 1]

        return mid_key, new_node

    # ==================================================================
    # Internal helpers — delete
    # ==================================================================

    def _delete(
        self,
        node: _Node,
        key: Any,
        row_id: int,
        parent: Optional[_Node],
        parent_idx: Optional[int],
    ) -> Tuple[bool, bool]:
        """
        Returns (found: bool, underflow: bool).
        `underflow` is True when this node now has fewer than _min_keys keys
        and the caller (parent) needs to fix it.
        """
        if node.is_leaf:
            found = self._leaf_delete(node, key, row_id)
            underflow = len(node.keys) < self._min_keys and parent is not None
            return found, underflow

        # Navigate to the correct child
        idx = self._child_index(node, key)
        found, child_underflow = self._delete(
            node.children[idx], key, row_id, parent=node, parent_idx=idx
        )

        if child_underflow:
            self._fix_underflow(node, idx)

        underflow = len(node.keys) < self._min_keys and parent is not None
        return found, underflow

    @staticmethod
    def _leaf_delete(leaf: _Node, key: Any, row_id: int) -> bool:
        """Remove (key, row_id) from a leaf. Returns True if found."""
        for i, k in enumerate(leaf.keys):
            if k == key:
                try:
                    leaf.values[i].remove(row_id)
                except ValueError:
                    return False
                if not leaf.values[i]:
                    leaf.keys.pop(i)
                    leaf.values.pop(i)
                return True
        return False

    def _fix_underflow(self, parent: _Node, child_idx: int) -> None:
        """
        Fix underflow in parent.children[child_idx] by trying:
        1. Borrow from left sibling
        2. Borrow from right sibling
        3. Merge with left sibling
        4. Merge with right sibling
        """
        child = parent.children[child_idx]

        # Try borrow from left sibling
        if child_idx > 0:
            left = parent.children[child_idx - 1]
            if len(left.keys) > self._min_keys:
                self._borrow_from_left(parent, child_idx, child, left)
                return

        # Try borrow from right sibling
        if child_idx < len(parent.children) - 1:
            right = parent.children[child_idx + 1]
            if len(right.keys) > self._min_keys:
                self._borrow_from_right(parent, child_idx, child, right)
                return

        # Merge
        if child_idx > 0:
            # Merge child into its left sibling
            left = parent.children[child_idx - 1]
            self._merge(parent, child_idx - 1, left, child)
        else:
            # Merge right sibling into child
            right = parent.children[child_idx + 1]
            self._merge(parent, child_idx, child, right)

    def _borrow_from_left(
        self, parent: _Node, child_idx: int, child: _Node, left: _Node
    ) -> None:
        if child.is_leaf:
            # Move last key/value of left into front of child
            child.keys.insert(0, left.keys.pop())
            child.values.insert(0, left.values.pop())
            parent.keys[child_idx - 1] = child.keys[0]
        else:
            # Rotate through parent separator
            sep = parent.keys[child_idx - 1]
            child.keys.insert(0, sep)
            child.children.insert(0, left.children.pop())
            parent.keys[child_idx - 1] = left.keys.pop()

    def _borrow_from_right(
        self, parent: _Node, child_idx: int, child: _Node, right: _Node
    ) -> None:
        if child.is_leaf:
            child.keys.append(right.keys.pop(0))
            child.values.append(right.values.pop(0))
            parent.keys[child_idx] = right.keys[0]
        else:
            sep = parent.keys[child_idx]
            child.keys.append(sep)
            child.children.append(right.children.pop(0))
            parent.keys[child_idx] = right.keys.pop(0)

    def _merge(
        self, parent: _Node, left_idx: int, left: _Node, right: _Node
    ) -> None:
        """Merge *right* into *left*, removing the separator from *parent*."""
        sep = parent.keys.pop(left_idx)
        parent.children.pop(left_idx + 1)

        if left.is_leaf:
            left.keys.extend(right.keys)
            left.values.extend(right.values)
            left.next = right.next
        else:
            left.keys.append(sep)
            left.keys.extend(right.keys)
            left.children.extend(right.children)

    # ==================================================================
    # Internal helpers — validation
    # ==================================================================

    def _validate_node(
        self,
        node: _Node,
        min_key: Optional[Any],
        max_key: Optional[Any],
        depth: int,
        expected_leaf_depth: int,
    ) -> None:
        # Leaves must all be at the same depth
        if node.is_leaf:
            assert depth == expected_leaf_depth, (
                f"Leaf at depth {depth}, expected {expected_leaf_depth}"
            )
            # Keys sorted
            for i in range(len(node.keys) - 1):
                assert node.keys[i] <= node.keys[i + 1], (
                    f"Leaf keys out of order: {node.keys[i]} > {node.keys[i + 1]}"
                )
            return

        # Internal node: keys sorted
        for i in range(len(node.keys) - 1):
            assert node.keys[i] < node.keys[i + 1], (
                f"Internal keys out of order: {node.keys[i]} >= {node.keys[i + 1]}"
            )

        # Key count bounds (not for root at depth 0)
        if depth > 0:
            assert len(node.keys) >= self._min_keys, (
                f"Internal node underflow at depth {depth}: {len(node.keys)} < {self._min_keys}"
            )
        assert len(node.keys) <= self.max_keys, (
            f"Internal node overflow: {len(node.keys)} > {self.max_keys}"
        )
        assert len(node.children) == len(node.keys) + 1, (
            f"children count mismatch: {len(node.children)} != {len(node.keys)+1}"
        )

        # Recurse
        for i, child in enumerate(node.children):
            lo = node.keys[i - 1] if i > 0 else min_key
            hi = node.keys[i] if i < len(node.keys) else max_key
            self._validate_node(child, lo, hi, depth + 1, expected_leaf_depth)
