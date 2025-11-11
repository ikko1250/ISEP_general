#!/usr/bin/env python3
"""
Interactive viewer for paragraph text from clause_data.db.

- Prompts for paragraph_id repeatedly and prints the paragraph text.
- Append '-c' after the id to also print assigned codings.
  Type 'q', 'quit', or 'exit' to leave.

Usage:
  python view_paragraph_by_id.py [path/to/clause_data.db]

If no DB path is given, it defaults to a file named 'clause_data.db'
in the same directory as this script.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path


def open_db(db_path: Path) -> sqlite3.Connection:
    # Open read-only and keep temp in memory for sandboxed environments
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA temp_store=MEMORY")
    return conn


def main(argv: list[str]) -> int:
    script_dir = Path(__file__).resolve().parent
    default_db = script_dir / "clause_data.db"

    if len(argv) >= 2:
        db_path = Path(argv[1])
    else:
        db_path = default_db

    if not db_path.exists():
        print(f"Error: DB file not found: {db_path}")
        print("Usage: python view_paragraph_by_id.py [path/to/clause_data.db]")
        return 2

    try:
        conn = open_db(db_path)
    except sqlite3.Error as e:
        print(f"Failed to open database: {e}")
        return 1

    print(f"Opened DB: {db_path}")
    print("Type a paragraph_id to show text. Add '-c' to also show codings. Type 'q' to quit.")

    try:
        while True:
            try:
                raw = input("paragraph_id> ").strip()
            except EOFError:
                print()
                break

            if raw.lower() in {"q", "quit", "exit"}:
                break
            if not raw:
                continue

            # Parse input: allow forms like "123" or "123 -c"
            parts = raw.split()
            show_codes = False
            if len(parts) >= 2:
                show_codes = any(p.lower() == '-c' for p in parts[1:])
            try:
                pid = int(parts[0])
            except (ValueError, IndexError):
                print("Please enter a numeric id (optionally followed by -c), or 'q' to quit.")
                continue

            try:
                row = conn.execute(
                    "SELECT p.id, p.text FROM paragraphs p WHERE p.id = ?",
                    (pid,),
                ).fetchone()
            except sqlite3.Error as e:
                print(f"Query failed: {e}")
                continue

            if not row:
                print(f"No paragraph found for id={pid}.")
                continue

            text = row["text"] or ""
            print("\n----- BEGIN TEXT -----")
            print(text)
            print("----- END TEXT -----\n")

            if show_codes:
                try:
                    codes = conn.execute(
                        """
                        SELECT ct.code, ct.description
                        FROM paragraph_codings pc
                        JOIN coding_types ct ON ct.id = pc.coding_type_id
                        WHERE pc.paragraph_id = ?
                        ORDER BY ct.code
                        """,
                        (pid,),
                    ).fetchall()
                except sqlite3.Error as e:
                    print(f"Failed to fetch codings: {e}")
                    continue

                print("----- CODINGS -----")
                if not codes:
                    print("(none)")
                else:
                    for c in codes:
                        code = c[0]
                        desc = c[1]
                        if desc:
                            print(f"- {code}: {desc}")
                        else:
                            print(f"- {code}")
                print("-------------------\n")

    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
