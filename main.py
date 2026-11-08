"""
main.py
=======
Interactive REPL for the Mini Database Engine.

Usage:
    python main.py

Pre-loaded: a 'users' table with schema [id, name, age].

Commands
--------
  CREATE TABLE <name> (<col1>, <col2>, ...)
  CREATE INDEX ON <table>(<col>) [USING hash|bptree]
  INSERT INTO <table> VALUES (<v1>, <v2>, ...)
  SELECT * FROM <table> [WHERE <col> = <val>]
  SELECT * FROM <table> WHERE <col> BETWEEN <low> AND <high>
  DELETE FROM <table> WHERE <col> = <val>
  EXPLAIN SELECT ...
  DROP TABLE <name>
  TABLES                    -- list all tables and their indexes
  HELP                      -- show this help
  EXIT / QUIT               -- exit the REPL

Example session
---------------
  minidb> INSERT INTO users VALUES (1, 'Asha', 24)
  minidb> INSERT INTO users VALUES (2, 'Ravi', 30)
  minidb> CREATE INDEX ON users(id) USING hash
  minidb> CREATE INDEX ON users(age) USING bptree
  minidb> EXPLAIN SELECT * FROM users WHERE id = 1
  minidb> SELECT * FROM users WHERE id = 1
  minidb> SELECT * FROM users WHERE age BETWEEN 20 AND 25
  minidb> DELETE FROM users WHERE id = 2
"""
import sys
import os

# Allow running from the project root
sys.path.insert(0, os.path.dirname(__file__))

from query.parser import parse
from query.planner import Database

BANNER = r"""
  ╔══════════════════════════════════════════════╗
  ║      Mini Database Engine  v1.0              ║
  ║  B+ Tree • Hash Index • Query Planner        ║
  ║  Type HELP for commands, EXIT to quit.       ║
  ╚══════════════════════════════════════════════╝
"""

HELP_TEXT = """
Commands:
  CREATE TABLE <name> (<col1>, <col2>, ...)
  CREATE INDEX ON <table>(<col>) [USING hash|bptree]
  INSERT INTO <table> VALUES (<v1>, <v2>, ...)
  SELECT * FROM <table> [WHERE <col> = <val>]
  SELECT * FROM <table> WHERE <col> BETWEEN <low> AND <high>
  EXPLAIN SELECT ...          -- show query plan without executing
  DELETE FROM <table> WHERE <col> = <val>
  DROP TABLE <name>
  TABLES                      -- list all tables
  HELP                        -- show this message
  EXIT / QUIT                 -- exit
"""


def preload(db: Database) -> None:
    """Create a sample 'users' table with a few rows."""
    db.execute(parse("CREATE TABLE users (id, name, age)"))
    sample = [
        "INSERT INTO users VALUES (1, 'Asha', 24)",
        "INSERT INTO users VALUES (2, 'Ravi', 30)",
        "INSERT INTO users VALUES (3, 'Priya', 22)",
        "INSERT INTO users VALUES (4, 'Kiran', 28)",
        "INSERT INTO users VALUES (5, 'Meena', 35)",
    ]
    for cmd in sample:
        db.execute(parse(cmd))
    print("  Pre-loaded: table 'users' (id, name, age) with 5 rows.")
    print("  Tip: try  CREATE INDEX ON users(id) USING hash")
    print("            SELECT * FROM users WHERE id = 3")
    print("            SELECT * FROM users WHERE age BETWEEN 22 AND 30")


def repl(db: Database) -> None:
    print(BANNER)
    preload(db)
    print()

    while True:
        try:
            line = input("  minidb> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Bye!")
            break

        if not line:
            continue

        upper = line.upper()

        if upper in ("EXIT", "QUIT", "\\Q"):
            print("  Bye!")
            break

        if upper == "HELP":
            print(HELP_TEXT)
            continue

        if upper == "TABLES":
            print("  " + db.list_tables().replace("\n", "\n  "))
            continue

        try:
            ast = parse(line)
            result = db.execute(ast)
            # Indent result lines for readability
            for ln in result.splitlines():
                print("  " + ln)
        except (SyntaxError, KeyError, ValueError) as exc:
            print(f"  ERROR: {exc}")

        print()


if __name__ == "__main__":
    repl(Database())
