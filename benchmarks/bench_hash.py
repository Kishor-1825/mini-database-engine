"""
benchmarks/bench_hash.py
========================
Benchmark: full scan vs hash index for equality lookups.
Sizes: 100K and 1M rows.
"""
import time
import random
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from storage.table import Table


LOOKUP_COUNT = 1_000


def benchmark(n_rows: int):
    print(f"\n{'='*60}")
    print(f"  Dataset size: {n_rows:,} rows | {LOOKUP_COUNT:,} lookups each")
    print(f"{'='*60}")

    # Build table
    t = Table("bench", ["id", "name", "age"])
    ids = list(range(n_rows))
    random.shuffle(ids)
    for i, uid in enumerate(ids):
        t.insert((uid, f"user_{uid}", 20 + (uid % 50)))

    # Sample lookup keys (guaranteed to exist)
    lookup_keys = random.sample(ids, LOOKUP_COUNT)

    # --- Full scan ---
    col_pos = 0
    start = time.perf_counter()
    for key in lookup_keys:
        _ = t.scan(lambda r, k=key: r[col_pos] == k)
    scan_time = time.perf_counter() - start

    # --- Hash index ---
    t.create_hash_index("id")
    start = time.perf_counter()
    for key in lookup_keys:
        row_ids = t.hash_indexes["id"].lookup(key)
        _ = [t.get(rid) for rid in row_ids]
    hash_time = time.perf_counter() - start

    speedup = scan_time / hash_time if hash_time > 0 else float("inf")

    print(f"  Full scan:   {scan_time:.4f}s  ({scan_time/LOOKUP_COUNT*1000:.4f} ms/lookup)")
    print(f"  Hash index:  {hash_time:.4f}s  ({hash_time/LOOKUP_COUNT*1000:.4f} ms/lookup)")
    print(f"  Speedup:     {speedup:.1f}x")

    return scan_time, hash_time


if __name__ == "__main__":
    results = {}
    for n in [100_000, 1_000_000]:
        results[n] = benchmark(n)

    print("\n\n  SUMMARY TABLE")
    print(f"  {'Rows':>12} | {'Full Scan (s)':>14} | {'Hash (s)':>10} | {'Speedup':>8}")
    print("  " + "-" * 55)
    for n, (s, h) in results.items():
        print(f"  {n:>12,} | {s:>14.4f} | {h:>10.4f} | {s/h:>7.1f}x")
