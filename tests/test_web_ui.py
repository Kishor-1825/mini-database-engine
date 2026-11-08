"""
tests/test_web_ui.py
====================
Unit tests for web_ui state serialization and benchmarking functions.
"""
from storage.table import Table
from index.bptree import BPlusTree
import web_ui


def test_serialize_bptree():
    tree = BPlusTree(max_keys=3)
    for i in [10, 20, 5, 15, 25, 30]:
        tree.insert(i, i)
    data = web_ui.serialize_bptree(tree)
    assert data["max_keys"] == 3
    assert data["height"] >= 2
    assert len(data["nodes"]) >= 3
    # Check that leaves have is_leaf=True
    leaves = [n for n in data["nodes"] if n["is_leaf"]]
    assert len(leaves) >= 2


def test_serialize_database_state():
    web_ui.init_sample_data(max_keys=3)
    state = web_ui.serialize_database_state()
    assert "users" in state["tables"]
    users = state["tables"]["users"]
    assert users["row_count"] == 10
    assert "id" in users["hash_indexes"]
    assert "age" in users["bptree_indexes"]


def test_run_benchmark():
    res = web_ui.run_benchmark(n_rows=500, lookup_count=50, range_span=50)
    assert "equality" in res
    assert "range" in res
    assert res["equality"]["hash_speedup"] >= 1.0
    assert res["range"]["bptree_speedup"] >= 1.0

