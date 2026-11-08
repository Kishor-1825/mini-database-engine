"""
web_ui.py
=========
Web UI and REST API server for the Mini Database Engine.
Zero external dependencies (uses standard library http.server).

Usage:
    python web_ui.py [--port 5000]
"""
import sys
import os
import json
import time
import random
import argparse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from query.parser import parse
from query.planner import Database
from storage.table import Table
from index.bptree import BPlusTree
from index.hash_index import HashIndex

# Global database instance
db = Database()


def init_sample_data(max_keys: int = 3):
    """Initialize database with a sample 'users' table and indexes."""
    global db
    db = Database()
    users = Table("users", ["id", "name", "age"])
    db.tables["users"] = users

    sample_rows = [
        (1, "Asha", 24),
        (2, "Ravi", 30),
        (3, "Priya", 22),
        (4, "Kiran", 28),
        (5, "Meena", 35),
        (6, "Arjun", 19),
        (7, "Deepa", 27),
        (8, "Vikram", 31),
        (9, "Sneha", 25),
        (10, "Dev", 23),
    ]
    for row in sample_rows:
        users.insert(row)

    # Hash index on id, B+ Tree on age (with small max_keys to show tree splits!)
    users.create_hash_index("id")
    users.create_bptree_index("age", max_keys=max_keys)


def serialize_bptree(tree: BPlusTree) -> dict:
    """Serialize a BPlusTree instance into a structured JSON dictionary."""
    node_id_map = {}

    def assign_ids(node):
        if id(node) not in node_id_map:
            node_id_map[id(node)] = len(node_id_map)
        if not node.is_leaf:
            for child in node.children:
                assign_ids(child)

    assign_ids(tree._root)
    nodes = []

    def collect(node, depth=0):
        nid = node_id_map[id(node)]
        info = {
            "id": nid,
            "is_leaf": node.is_leaf,
            "depth": depth,
            "keys": node.keys,
        }
        if node.is_leaf:
            # node.values is list[list[int]] of row_ids
            info["values"] = node.values
            info["next_id"] = node_id_map.get(id(node.next)) if node.next else None
        else:
            info["children"] = [node_id_map[id(c)] for c in node.children]
            for c in node.children:
                collect(c, depth + 1)
        nodes.append(info)

    collect(tree._root, 0)

    # Order nodes by depth then id
    nodes.sort(key=lambda x: (x["depth"], x["id"]))

    return {
        "max_keys": tree.max_keys,
        "height": tree._height,
        "root_id": node_id_map.get(id(tree._root), 0),
        "nodes": nodes,
    }


def serialize_database_state():
    """Return a full snapshot of the database state."""
    tables_data = {}
    for name, tbl in db.tables.items():
        # Rows
        rows_data = []
        for rid, row in enumerate(tbl.rows):
            if row is None:
                rows_data.append({"row_id": rid, "values": None, "deleted": True})
            else:
                rows_data.append({"row_id": rid, "values": list(row), "deleted": False})

        # Hash indexes
        hash_data = {}
        for col, idx in tbl.hash_indexes.items():
            # _map is key -> list[row_id]
            buckets = [
                {"key": k, "row_ids": list(v)}
                for k, v in sorted(idx._map.items(), key=lambda item: str(item[0]))
            ]
            hash_data[col] = {
                "distinct_keys": len(idx),
                "buckets": buckets,
            }

        # B+ Tree indexes
        bpt_data = {}
        for col, idx in tbl.bptree_indexes.items():
            bpt_data[col] = serialize_bptree(idx)

        tables_data[name] = {
            "name": name,
            "schema": tbl.schema,
            "row_count": len(tbl),
            "total_slots": len(tbl.rows),
            "rows": rows_data,
            "hash_indexes": hash_data,
            "bptree_indexes": bpt_data,
        }

    return {"tables": tables_data}


def run_benchmark(n_rows: int = 5000, lookup_count: int = 300, range_span: int = 200):
    """Run an isolated in-memory benchmark comparing Full Scan vs Hash vs B+ Tree."""
    t = Table("bench", ["id", "val", "num"])
    ids = list(range(n_rows))
    random.shuffle(ids)
    for uid in ids:
        t.insert((uid, f"val_{uid}", uid % 1000))

    lookup_keys = random.sample(ids, min(lookup_count, n_rows))
    range_queries = []
    for _ in range(min(lookup_count, n_rows)):
        lo = random.randint(0, max(0, n_rows - range_span))
        range_queries.append((lo, lo + range_span))

    t.create_hash_index("id")
    t.create_bptree_index("id", max_keys=32)

    # 1. Equality - Full Scan
    col_pos = 0
    t0 = time.perf_counter()
    for key in lookup_keys:
        _ = t.scan(lambda r, k=key: r[col_pos] == k)
    eq_scan_sec = time.perf_counter() - t0

    # 2. Equality - Hash Index
    t0 = time.perf_counter()
    for key in lookup_keys:
        rids = t.hash_indexes["id"].lookup(key)
        _ = [t.get(i) for i in rids]
    eq_hash_sec = time.perf_counter() - t0

    # 3. Equality - B+ Tree
    t0 = time.perf_counter()
    for key in lookup_keys:
        rids = t.bptree_indexes["id"].search(key)
        _ = [t.get(i) for i in rids]
    eq_bpt_sec = time.perf_counter() - t0

    # 4. Range - Full Scan
    t0 = time.perf_counter()
    for lo, hi in range_queries:
        _ = t.scan(lambda r, l=lo, h=hi: l <= r[col_pos] <= h)
    rng_scan_sec = time.perf_counter() - t0

    # 5. Range - B+ Tree
    t0 = time.perf_counter()
    for lo, hi in range_queries:
        rids = t.bptree_indexes["id"].range_search(lo, hi)
        _ = [t.get(i) for i in rids]
    rng_bpt_sec = time.perf_counter() - t0

    return {
        "n_rows": n_rows,
        "lookup_count": len(lookup_keys),
        "range_span": range_span,
        "equality": {
            "full_scan_sec": eq_scan_sec,
            "full_scan_ms_per_q": (eq_scan_sec / len(lookup_keys)) * 1000,
            "hash_sec": eq_hash_sec,
            "hash_ms_per_q": (eq_hash_sec / len(lookup_keys)) * 1000,
            "hash_speedup": round(eq_scan_sec / max(eq_hash_sec, 1e-9), 1),
            "bptree_sec": eq_bpt_sec,
            "bptree_ms_per_q": (eq_bpt_sec / len(lookup_keys)) * 1000,
            "bptree_speedup": round(eq_scan_sec / max(eq_bpt_sec, 1e-9), 1),
        },
        "range": {
            "full_scan_sec": rng_scan_sec,
            "full_scan_ms_per_q": (rng_scan_sec / len(range_queries)) * 1000,
            "bptree_sec": rng_bpt_sec,
            "bptree_ms_per_q": (rng_bpt_sec / len(range_queries)) * 1000,
            "bptree_speedup": round(rng_scan_sec / max(rng_bpt_sec, 1e-9), 1),
        },
    }


class DatabaseAPIHandler(BaseHTTPRequestHandler):
    """Handles HTTP requests for static assets and API calls."""

    def _send_json(self, data: dict, status: int = 200):
        body = json.dumps(data, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/state":
            self._send_json(serialize_database_state())
            return

        # Serve static HTML/JS/CSS
        if path in ("", "/", "/index.html"):
            html_file = os.path.join(BASE_DIR, "web", "index.html")
            if os.path.exists(html_file):
                with open(html_file, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return
            else:
                self.send_error(404, "web/index.html not found.")
                return

        self.send_error(404, "Endpoint not found.")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(length) if length > 0 else b"{}"

        try:
            body = json.loads(post_data.decode("utf-8")) if post_data else {}
        except Exception:
            body = {}

        if path == "/api/execute":
            sql = body.get("sql", "").strip()
            if not sql:
                self._send_json({"success": False, "error": "SQL statement is empty."}, 400)
                return

            try:
                t0 = time.perf_counter()
                ast = parse(sql)
                explain = ast.get("explain", False)
                op_type = ast.get("type")

                strategy = None
                result_rows = []
                schema = []

                if op_type == "select":
                    tbl_name = ast["table"]
                    if tbl_name in db.tables:
                        tbl = db.tables[tbl_name]
                        schema = tbl.schema
                        if explain:
                            strategy = db._explain_select(ast)
                            msg = strategy
                        else:
                            rows, strat = db._run_select(tbl, ast)
                            strategy = strat
                            result_rows = [list(r) for r in rows if r is not None]
                            msg = f"{len(result_rows)} row(s) returned via {strategy}"
                    else:
                        raise KeyError(f"Table '{tbl_name}' does not exist.")
                else:
                    msg = db.execute(ast)

                elapsed_ms = (time.perf_counter() - t0) * 1000

                self._send_json({
                    "success": True,
                    "sql": sql,
                    "ast": ast,
                    "type": op_type,
                    "message": msg,
                    "strategy": strategy,
                    "schema": schema,
                    "rows": result_rows,
                    "elapsed_ms": round(elapsed_ms, 3),
                    "state": serialize_database_state(),
                })
            except Exception as e:
                self._send_json({
                    "success": False,
                    "sql": sql,
                    "error": str(e),
                }, 200)
            return

        if path == "/api/reset":
            max_keys = int(body.get("max_keys", 3))
            init_sample_data(max_keys=max_keys)
            self._send_json({
                "success": True,
                "message": f"Database reset with sample 'users' table and B+ tree (max_keys={max_keys}).",
                "state": serialize_database_state(),
            })
            return

        if path == "/api/insert_random":
            tbl_name = body.get("table", "users")
            count = int(body.get("count", 5))
            if tbl_name not in db.tables:
                self._send_json({"success": False, "error": f"Table '{tbl_name}' does not exist."}, 400)
                return

            tbl = db.tables[tbl_name]
            names = ["Alex", "Sam", "Taylor", "Jordan", "Morgan", "Casey", "Riley", "Jamie", "Logan", "Reese"]
            start_id = len(tbl.rows) + 1
            inserted = []
            for i in range(count):
                row_id = start_id + i
                name = random.choice(names)
                age = random.randint(18, 55)
                row = (row_id, name, age)
                tbl.insert(row)
                inserted.append(row)

            self._send_json({
                "success": True,
                "message": f"Inserted {count} random rows into '{tbl_name}'.",
                "inserted": inserted,
                "state": serialize_database_state(),
            })
            return

        if path == "/api/benchmark":
            n_rows = int(body.get("rows", 5000))
            lookups = int(body.get("queries", 300))
            span = int(body.get("range_span", 200))
            # Bound row count for interactive responsiveness
            n_rows = max(500, min(n_rows, 100000))
            lookups = max(50, min(lookups, 2000))
            res = run_benchmark(n_rows, lookups, span)
            self._send_json({"success": True, "benchmark": res})
            return

        self.send_error(404, "Endpoint not found.")


def run_server(port: int = 5000):
    """Start the web server."""
    init_sample_data(max_keys=3)
    server_address = ("", port)
    httpd = ThreadingHTTPServer(server_address, DatabaseAPIHandler)
    url = f"http://localhost:{port}"

    print(f"""
  ╔══════════════════════════════════════════════════════════════╗
  ║            Mini Database Engine - Web Visualizer             ║
  ║                                                              ║
  ║  ✓ B+ Tree Interactive Visualizer (with leaf link chains)   ║
  ║  ✓ Hash Index Bucket Inspector                               ║
  ║  ✓ SQL Console & EXPLAIN Query Planner                       ║
  ║  ✓ Live In-Memory Data Grid                                  ║
  ║  ✓ Live Index Benchmarking Playground                        ║
  ║                                                              ║
  ║  Open in browser: \033[1;32m{url}\033[0m                             ║
  ║  Press Ctrl+C to stop.                                       ║
  ╚══════════════════════════════════════════════════════════════╝
    """)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  Shutting down web server... Goodbye!")
        httpd.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mini Database Engine Web UI")
    parser.add_argument("--port", type=int, default=5000, help="Port to run on (default: 5000)")
    args = parser.parse_args()
    run_server(args.port)

