# Mini Database Engine

A from-scratch database engine in pure Python that demonstrates how **B+ Tree** and **Hash** indexes work, and why they beat a full table scan by orders of magnitude.

---

## Architecture

```
┌──────────────────────────────────────────┐
│  Query Layer  (parser.py + planner.py)   │
│  INSERT · SELECT · DELETE · EXPLAIN      │
├──────────────────────────────────────────┤
│  Index Layer                             │
│  B+ Tree (ordered)  +  Hash (equality)   │
├──────────────────────────────────────────┤
│  Storage Layer  (table.py)               │
│  Rows in memory, identified by row_id    │
└──────────────────────────────────────────┘
```

---

## Features

| Feature | Details |
|---|---|
| **In-memory table** | Insert / full-scan / delete by ID |
| **Hash index** | O(1) equality lookup; non-unique keys supported |
| **B+ Tree index** | O(log n) point lookup; O(log n + k) range scan via linked leaves |
| **Splits & merges** | Full insert with leaf/internal/root splits; delete with borrow/merge/root-shrink |
| **Query planner** | Auto-picks hash → B+ Tree → full scan based on available indexes |
| **EXPLAIN** | Prints chosen strategy without executing the query |
| **SQL-like REPL** | Interactive command-line interface |
| **Validator** | Tree invariant checker (sorted keys, depth consistency, min/max key bounds) |
| **Benchmarks** | Logs speedup at 100K and 1M rows; saves a chart |

---

## Operation Complexity

| Operation | Full Scan | Hash Index | B+ Tree |
|---|---|---|---|
| Point lookup | O(n) | **O(1) avg** | O(log n) |
| Range query | O(n) | ✗ not supported | **O(log n + k)** |
| Insert | — | O(1) avg | O(log n) |
| Delete | O(n) scan + O(1) | O(1) avg | O(log n) |

---

## B+ Tree Structure

After inserting keys 1–9 with `max_keys=3`:

```
              [ 5 ]
             /     \
        [3]           [7]
       /   \         /   \
 [1,2]→[3,4]→[5,6]→[7,8]→[9]
```
Leaves are linked (`→`) so a range scan simply walks the chain.

**Insert / split example** — inserting key `4` into a full leaf `[1,2,3]`:
```
Before:  [1,2,3]
Split →  [1,2]  →  [3,4]      (3 is copied up to parent)
```

---

## Quick Start

```bash
# 1. Create and activate virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate    # Mac / Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the interactive REPL
python main.py

# 4. Or launch the Interactive Web Visualizer Dashboard (zero external dependencies)
python web_ui.py
# Open http://localhost:5000 in your browser
```

### Example session

```
minidb> CREATE INDEX ON users(id) USING hash
minidb> CREATE INDEX ON users(age) USING bptree
minidb> EXPLAIN SELECT * FROM users WHERE id = 3
  EXPLAIN: Hash index lookup on 'id'
minidb> SELECT * FROM users WHERE id = 3
  id | name | age
  ----------------
  3 | Priya | 22
  (1 row) [Hash index lookup on 'id']
minidb> SELECT * FROM users WHERE age BETWEEN 22 AND 28
  id | name  | age
  -----------------
  3 | Priya  | 22
  1 | Asha   | 24
  4 | Kiran  | 28
  (3 rows) [B+ Tree range scan on 'age' [22, 28]]
minidb> DELETE FROM users WHERE id = 2
  Deleted 1 row(s) where id = 2.
```

---

## Running Tests

```bash
python -m pytest tests/ -v
```

---

## Benchmarks

Run:
```bash
python benchmarks/bench_hash.py
python benchmarks/bench_bptree.py   # also saves benchmarks/results.png
```

### Sample results (Apple M1 equivalent; your numbers will vary)

#### Equality lookups (1,000 queries)

| Rows | Full Scan | Hash Index | B+ Tree | Hash speedup | B+ Tree speedup |
|---:|---:|---:|---:|---:|---:|
| 100,000 | ~0.80s | ~0.001s | ~0.004s | ~800× | ~200× |
| 1,000,000 | ~8.5s | ~0.001s | ~0.005s | ~8500× | ~1700× |

#### Range lookups — span ~1,000 values (1,000 queries)

| Rows | Full Scan | B+ Tree |
|---:|---:|---:|
| 100,000 | ~0.90s | ~0.012s | 
| 1,000,000 | ~9.2s | ~0.014s |

> Actual numbers depend on your hardware. The chart is saved to `benchmarks/results.png`.

---

## Project Structure

```
Mini Database Engine/
├── storage/
│   └── table.py          # Table: insert / scan / delete / index hooks
├── index/
│   ├── hash_index.py     # HashIndex: key → [row_ids]
│   └── bptree.py         # BPlusTree: ordered index with leaf-link chain
├── query/
│   ├── parser.py         # SQL-like command parser → AST dict
│   └── planner.py        # Query planner + executor (Database class)
├── tests/
│   ├── test_table.py
│   ├── test_hash_index.py
│   └── test_bptree.py    # Stress tests + invariant validator
├── benchmarks/
│   ├── bench_hash.py
│   └── bench_bptree.py   # Saves results.png
├── main.py               # Interactive REPL
└── requirements.txt
```

---

## What You'll Learn

- **Balanced trees**: B+ Tree invariants, leaf/internal/root splits, borrow/merge on delete
- **Hashing**: key-to-bucket mapping, collision handling (chaining)
- **Linked lists**: leaf chain enables O(k) range traversal after O(log n) descent
- **Systems thinking**: why page granularity and disk I/O patterns drove B+ Tree design
- **Benchmarking**: measuring and proving index speedup with real data

---

## Extensions (Optional)

| Extension | Difficulty |
|---|---|
| Write your own hash table (open addressing / chaining) instead of Python `dict` | ⭐⭐ |
| Disk persistence with fixed-size pages | ⭐⭐⭐ |
| Buffer pool with LRU eviction | ⭐⭐⭐ |
| Write-ahead log (crash recovery) | ⭐⭐⭐⭐ |
| Multi-column indexes | ⭐⭐⭐ |
