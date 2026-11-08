"""
tests/test_table.py
===================
Tests for the in-memory Table class.
"""
import pytest
from storage.table import Table


def make_users() -> Table:
    t = Table("users", ["id", "name", "age"])
    t.insert((1, "Asha", 24))
    t.insert((2, "Ravi", 30))
    t.insert((3, "Priya", 22))
    return t


def test_insert_returns_row_id():
    t = Table("t", ["x"])
    assert t.insert((10,)) == 0
    assert t.insert((20,)) == 1


def test_get():
    t = make_users()
    assert t.get(0) == (1, "Asha", 24)
    assert t.get(2) == (3, "Priya", 22)
    assert t.get(99) is None


def test_scan_all():
    t = make_users()
    result = t.scan(lambda r: True)
    assert len(result) == 3


def test_scan_filter():
    t = make_users()
    result = t.scan(lambda r: r[2] > 25)
    assert result == [(2, "Ravi", 30)]


def test_scan_no_match():
    t = make_users()
    assert t.scan(lambda r: r[0] == 999) == []


def test_len():
    t = make_users()
    assert len(t) == 3


def test_schema_mismatch():
    t = Table("t", ["a", "b"])
    with pytest.raises(ValueError):
        t.insert((1,))  # too few columns


def test_delete_by_id():
    t = make_users()
    assert t.delete_by_id(1) is True
    assert t.get(1) is None
    assert len(t) == 2


def test_delete_missing_id():
    t = make_users()
    assert t.delete_by_id(99) is False


def test_hash_index_created_on_insert():
    t = Table("t", ["id", "val"])
    t.insert((1, "a"))
    t.create_hash_index("id")
    t.insert((2, "b"))   # should be auto-indexed
    assert t.hash_indexes["id"].lookup(2) == [1]


def test_bptree_index_created_on_insert():
    t = Table("t", ["id", "val"])
    t.insert((10, "x"))
    t.create_bptree_index("id")
    t.insert((20, "y"))
    assert t.bptree_indexes["id"].search(20) == [1]
