"""
benchmarks/bench_bptree.py
==========================
Benchmark: full scan vs hash vs B+ Tree for equality and range lookups.
Sizes: 100K and 1M rows.
Saves a bar chart to benchmarks/results.png (requires matplotlib).
"""
import time
import random
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from storage.table import Table

LOOKUP_COUNT = 1_000
RANGE_SIZE   = 1_000   # each range query spans ~1,000 values


def build_table(n_rows: int) -> Table:
    t = Table("bench", ["id", "name", "age"])
    ids = list(range(n_rows))
    random.shuffle(ids)
    for uid in ids:
        t.insert((uid, f"user_{uid}", 20 + (uid % 50)))
    return t


def bench_equality(t: Table, lookup_keys):
    col_pos = 0

    # Full scan
    start = time.perf_counter()
    for key in lookup_keys:
        _ = t.scan(lambda r, k=key: r[col_pos] == k)
    scan_eq = time.perf_counter() - start

    # Hash index
    start = time.perf_counter()
    for key in lookup_keys:
        ids = t.hash_indexes["id"].lookup(key)
        _ = [t.get(i) for i in ids]
    hash_eq = time.perf_counter() - start

    # B+ Tree point lookup
    start = time.perf_counter()
    for key in lookup_keys:
        ids = t.bptree_indexes["id"].search(key)
        _ = [t.get(i) for i in ids]
    bpt_eq = time.perf_counter() - start

    return scan_eq, hash_eq, bpt_eq


def bench_range(t: Table, range_queries):
    col_pos = 0

    # Full scan
    start = time.perf_counter()
    for lo, hi in range_queries:
        _ = t.scan(lambda r, l=lo, h=hi: l <= r[col_pos] <= h)
    scan_rng = time.perf_counter() - start

    # B+ Tree range
    start = time.perf_counter()
    for lo, hi in range_queries:
        ids = t.bptree_indexes["id"].range_search(lo, hi)
        _ = [t.get(i) for i in ids]
    bpt_rng = time.perf_counter() - start

    return scan_rng, bpt_rng


def run(n_rows: int):
    print(f"\n{'='*65}")
    print(f"  {n_rows:,} rows | {LOOKUP_COUNT:,} queries each")
    print(f"{'='*65}")

    t = build_table(n_rows)
    all_ids = list(range(n_rows))
    lookup_keys = random.sample(all_ids, LOOKUP_COUNT)
    range_queries = [(random.randint(0, n_rows - RANGE_SIZE),) * 2 for _ in range(LOOKUP_COUNT)]
    range_queries = [(lo, lo + RANGE_SIZE) for lo, _ in range_queries]

    # Build indexes (after table population)
    t.create_hash_index("id")
    t.create_bptree_index("id", max_keys=64)

    se, he, be = bench_equality(t, lookup_keys)
    sr, br = bench_range(t, range_queries)

    print(f"\n  Equality lookups:")
    print(f"    Full scan : {se:.4f}s   ({se/LOOKUP_COUNT*1e3:.4f} ms/q)")
    print(f"    Hash idx  : {he:.4f}s   ({he/LOOKUP_COUNT*1e3:.4f} ms/q)   {se/he:.1f}x speedup")
    print(f"    B+ Tree   : {be:.4f}s   ({be/LOOKUP_COUNT*1e3:.4f} ms/q)   {se/be:.1f}x speedup")

    print(f"\n  Range lookups (span ~{RANGE_SIZE} values):")
    print(f"    Full scan : {sr:.4f}s   ({sr/LOOKUP_COUNT*1e3:.4f} ms/q)")
    print(f"    B+ Tree   : {br:.4f}s   ({br/LOOKUP_COUNT*1e3:.4f} ms/q)   {sr/br:.1f}x speedup")

    return {"n": n_rows, "se": se, "he": he, "be": be, "sr": sr, "br": br}


def plot_results(all_results):
    try:
        import matplotlib.pyplot as plt
        import matplotlib
        matplotlib.use("Agg")
    except ImportError:
        print("matplotlib not installed — skipping chart.")
        return

    labels = [f"{r['n']//1000}K" for r in all_results]
    x = range(len(labels))
    width = 0.15

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle("Mini Database Engine Benchmark", fontsize=14, fontweight="bold")

    # Equality
    ax = axes[0]
    ax.set_title("Equality Lookups (1,000 queries)")
    ax.bar([i - width for i in x], [r["se"] for r in all_results], width, label="Full Scan", color="#e74c3c")
    ax.bar([i          for i in x], [r["he"] for r in all_results], width, label="Hash Index", color="#2ecc71")
    ax.bar([i + width  for i in x], [r["be"] for r in all_results], width, label="B+ Tree", color="#3498db")
    ax.set_xticks(list(x)); ax.set_xticklabels(labels)
    ax.set_ylabel("Time (seconds)")
    ax.legend(); ax.set_yscale("log")

    # Range
    ax = axes[1]
    ax.set_title(f"Range Lookups span ~{RANGE_SIZE} (1,000 queries)")
    ax.bar([i - width/2 for i in x], [r["sr"] for r in all_results], width, label="Full Scan", color="#e74c3c")
    ax.bar([i + width/2 for i in x], [r["br"] for r in all_results], width, label="B+ Tree", color="#3498db")
    ax.set_xticks(list(x)); ax.set_xticklabels(labels)
    ax.set_ylabel("Time (seconds)")
    ax.legend(); ax.set_yscale("log")

    out = os.path.join(os.path.dirname(__file__), "results.png")
    plt.tight_layout()
    plt.savefig(out, dpi=150)
    print(f"\n  Chart saved to {out}")


if __name__ == "__main__":
    all_results = []
    for n in [100_000, 1_000_000]:
        all_results.append(run(n))
    plot_results(all_results)
