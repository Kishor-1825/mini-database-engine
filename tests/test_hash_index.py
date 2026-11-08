"""
tests/test_hash_index.py
========================
Tests for the HashIndex class.
"""
from index.hash_index import HashIndex


def test_insert_and_lookup():
    idx = HashIndex()
    idx.insert(42, 0)
    assert idx.lookup(42) == [0]


def test_missing_key_returns_empty():
    idx = HashIndex()
    assert idx.lookup("nope") == []


def test_non_unique_key():
    idx = HashIndex()
    idx.insert("asha@example.com", 0)
    idx.insert("asha@example.com", 5)
    result = idx.lookup("asha@example.com")
    assert sorted(result) == [0, 5]


def test_multiple_keys():
    idx = HashIndex()
    for i in range(10):
        idx.insert(i, i * 2)
    for i in range(10):
        assert idx.lookup(i) == [i * 2]


def test_delete_specific_row_id():
    idx = HashIndex()
    idx.insert("key", 0)
    idx.insert("key", 1)
    assert idx.delete("key", 0) is True
    assert idx.lookup("key") == [1]


def test_delete_last_row_id_removes_key():
    idx = HashIndex()
    idx.insert("solo", 7)
    idx.delete("solo", 7)
    assert idx.lookup("solo") == []
    assert len(idx) == 0


def test_delete_missing_returns_false():
    idx = HashIndex()
    assert idx.delete("ghost", 0) is False


def test_len():
    idx = HashIndex()
    idx.insert("a", 0)
    idx.insert("b", 1)
    assert len(idx) == 2
