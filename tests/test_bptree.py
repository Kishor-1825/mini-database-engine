"""
tests/test_bptree.py
====================
Comprehensive tests for the B+ Tree: insert, search, range_search,
delete, and stress tests with the invariant validator.
"""
import random
import pytest
from index.bptree import BPlusTree


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fresh(max_keys: int = 3) -> BPlusTree:
    return BPlusTree(max_keys=max_keys)


def insert_range(tree: BPlusTree, keys) -> None:
    for i, k in enumerate(keys):
        tree.insert(k, i)
        tree.validate()


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------

def test_min_max_keys_guard():
    with pytest.raises(ValueError):
        BPlusTree(max_keys=1)


# ---------------------------------------------------------------------------
# Search on empty tree
# ---------------------------------------------------------------------------

def test_search_empty():
    t = fresh()
    assert t.search(5) == []


# ---------------------------------------------------------------------------
# Insert in order
# ---------------------------------------------------------------------------

def test_insert_in_order():
    t = fresh(max_keys=3)
    for i in range(1, 21):
        t.insert(i, i)
        t.validate()
    for i in range(1, 21):
        assert i in t.search(i)


# ---------------------------------------------------------------------------
# Insert in reverse order
# ---------------------------------------------------------------------------

def test_insert_reverse_order():
    t = fresh(max_keys=3)
    for i in range(20, 0, -1):
        t.insert(i, i)
        t.validate()
    for i in range(1, 21):
        assert i in t.search(i)


# ---------------------------------------------------------------------------
# Insert random order
# ---------------------------------------------------------------------------

def test_insert_random_1000():
    t = BPlusTree(max_keys=5)
    keys = list(range(1000))
    random.shuffle(keys)
    for i, k in enumerate(keys):
        t.insert(k, i)
        # Only validate every 100 inserts to keep test fast
        if i % 100 == 0:
            t.validate()
    t.validate()
    for k in keys:
        assert len(t.search(k)) >= 1


# ---------------------------------------------------------------------------
# Non-unique keys
# ---------------------------------------------------------------------------

def test_non_unique_keys():
    t = fresh(max_keys=4)
    for i in range(5):
        t.insert(42, i)
    result = t.search(42)
    assert sorted(result) == list(range(5))
    t.validate()


# ---------------------------------------------------------------------------
# Range search
# ---------------------------------------------------------------------------

def test_range_search_basic():
    t = BPlusTree(max_keys=4)
    for i in range(1, 51):
        t.insert(i, i)
    result = sorted(t.range_search(10, 20))
    expected = list(range(10, 21))
    assert result == expected


def test_range_search_empty_range():
    t = BPlusTree(max_keys=4)
    for i in range(1, 10):
        t.insert(i, i)
    assert t.range_search(50, 100) == []


def test_range_search_matches_linear_scan():
    """range_search result must equal a linear scan over the same keys."""
    t = BPlusTree(max_keys=5)
    all_keys = list(range(200))
    random.shuffle(all_keys)
    for i, k in enumerate(all_keys):
        t.insert(k, i)

    low, high = 50, 100
    bpt_result = sorted(t.range_search(low, high))

    linear = sorted(
        i for i, k in enumerate(all_keys) if low <= k <= high
    )
    assert bpt_result == linear


def test_range_search_single_element():
    t = BPlusTree(max_keys=4)
    t.insert(7, 99)
    assert t.range_search(7, 7) == [99]


# ---------------------------------------------------------------------------
# Delete — basic
# ---------------------------------------------------------------------------

def test_delete_existing_key():
    t = fresh(max_keys=4)
    t.insert(10, 0)
    t.insert(20, 1)
    assert t.delete(10, 0) is True
    assert t.search(10) == []
    t.validate()


def test_delete_missing_key_returns_false():
    t = fresh(max_keys=4)
    t.insert(5, 0)
    assert t.delete(999, 0) is False


def test_delete_one_of_many_row_ids():
    t = fresh(max_keys=4)
    t.insert(5, 0)
    t.insert(5, 1)
    t.delete(5, 0)
    result = t.search(5)
    assert 0 not in result
    assert 1 in result
    t.validate()


# ---------------------------------------------------------------------------
# Delete — stress (triggers borrow / merge)
# ---------------------------------------------------------------------------

def test_delete_stress():
    t = BPlusTree(max_keys=4)
    keys = list(range(100))
    for k in keys:
        t.insert(k, k)
    t.validate()

    random.shuffle(keys)
    for k in keys:
        t.delete(k, k)
        t.validate()

    # Tree should be empty now
    for k in range(100):
        assert t.search(k) == []


# ---------------------------------------------------------------------------
# Height grows with inserts
# ---------------------------------------------------------------------------

def test_tree_height_grows():
    t = BPlusTree(max_keys=3)
    initial_height = t._height
    for i in range(50):
        t.insert(i, i)
    assert t._height > initial_height


# ---------------------------------------------------------------------------
# Visualize returns non-empty DOT
# ---------------------------------------------------------------------------

def test_visualize_produces_dot():
    t = BPlusTree(max_keys=4)
    for i in range(1, 10):
        t.insert(i, i)
    dot = t.visualize()
    assert "digraph" in dot
    assert "BPlusTree" in dot
