#!/usr/bin/env python3
"""
Inspect the schema of an SQLite database: tables, columns, keys, indexes, and FKs.

Usage:
  python inspect_sqlite_schema.py clause_data.db [--no-counts]
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path


def qident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def print_header(title: str) -> None:
    print(f"\n=== {title} ===")


def fetchone_val(conn: sqlite3.Connection, sql: str) -> int | str | None:
    cur = conn.execute(sql)
    row = cur.fetchone()
    if not row:
        return None
    val = row[0]
    return val


def list_schema_objects(conn: sqlite3.Connection, types: tuple[str, ...]) -> list[dict]:
    cur = conn.execute(
        "SELECT name, type, sql FROM sqlite_master WHERE type IN (%s) ORDER BY type, name"
        % ",".join(["?"] * len(types)),
        types,
    )
    rows = [dict(name=r[0], type=r[1], sql=r[2]) for r in cur.fetchall()]
    return rows


def describe_table(conn: sqlite3.Connection, name: str, with_counts: bool) -> None:
    print_header(f"Table: {name}")
    # Columns
    cols = conn.execute(f"PRAGMA table_info({qident(name)})").fetchall()
    if cols:
        print("Columns:")
        print("  - name (type) [pk, notnull, default]")
        for cid, col_name, col_type, notnull, dflt_value, pk in cols:
            flags = []
            if pk:
                flags.append("pk")
            if notnull:
                flags.append("notnull")
            default = f" default={dflt_value}" if dflt_value is not None else ""
            flag_str = (", ".join(flags)) if flags else "-"
            print(f"  - {col_name} ({col_type or 'TEXT'}) [{flag_str}{default}]")
    else:
        print("(no column info)")

    # Foreign keys
    fks = conn.execute(f"PRAGMA foreign_key_list({qident(name)})").fetchall()
    if fks:
        print("Foreign Keys:")
        for (_id, _seq, ref_table, from_col, to_col, on_update, on_delete, match) in fks:
            print(
                f"  - {from_col} -> {ref_table}({to_col}) "
                f"[on_update={on_update}, on_delete={on_delete}, match={match}]"
            )

    # Indexes
    idx = conn.execute(f"PRAGMA index_list({qident(name)})").fetchall()
    if idx:
        print("Indexes:")
        for (_seq, idx_name, unique, origin, partial) in idx:
            cols_info = conn.execute(f"PRAGMA index_info({qident(idx_name)})").fetchall()
            cols_list = ", ".join([r[2] for r in cols_info]) if cols_info else "(expr)"
            print(
                f"  - {idx_name} on ({cols_list}) "
                f"[unique={'yes' if unique else 'no'}, origin={origin}, partial={'yes' if partial else 'no'}]"
            )

    # Row count (optional; skip for views or if disabled)
    if with_counts:
        try:
            cnt = conn.execute(f"SELECT COUNT(*) FROM {qident(name)}").fetchone()[0]
            print(f"Rows: {cnt}")
        except sqlite3.DatabaseError as e:
            print(f"Rows: (count failed: {e})")


def main() -> int:
    p = argparse.ArgumentParser(description="Inspect SQLite schema")
    p.add_argument("db", type=Path, help="Path to SQLite .db file")
    p.add_argument(
        "--no-counts",
        action="store_true",
        help="Do not run COUNT(*) for each table",
    )
    args = p.parse_args()

    if not args.db.exists():
        print(f"Error: file not found: {args.db}", file=sys.stderr)
        return 2

    conn = sqlite3.connect(str(args.db))
    try:
        conn.row_factory = sqlite3.Row
        # Basic DB pragmas
        print_header("Database Info")
        user_version = fetchone_val(conn, "PRAGMA user_version")
        page_size = fetchone_val(conn, "PRAGMA page_size")
        foreign_keys_on = fetchone_val(conn, "PRAGMA foreign_keys")
        encoding = fetchone_val(conn, "PRAGMA encoding")
        print(f"Path: {args.db}")
        print(f"User version: {user_version}")
        print(f"Page size: {page_size}")
        print(f"Encoding: {encoding}")
        print(f"Foreign keys: {'ON' if foreign_keys_on else 'OFF'}")

        # Objects
        objs = list_schema_objects(conn, ("table", "view", "index", "trigger"))
        tables = [o for o in objs if o["type"] == "table" and not o["name"].startswith("sqlite_")]
        views = [o for o in objs if o["type"] == "view"]
        indexes = [o for o in objs if o["type"] == "index"]
        triggers = [o for o in objs if o["type"] == "trigger"]

        print_header("Summary")
        print(f"Tables: {len(tables)} | Views: {len(views)} | Indexes: {len(indexes)} | Triggers: {len(triggers)}")
        if views:
            print("Views:")
            for v in views:
                print(f"  - {v['name']}")
        if triggers:
            print("Triggers:")
            for t in triggers:
                print(f"  - {t['name']}")

        for t in tables:
            describe_table(conn, t["name"], with_counts=not args.no_counts)

        # Optionally print raw CREATE statements for reference
        print_header("CREATE Statements (tables)")
        for t in tables:
            print(f"-- {t['name']}")
            if t["sql"]:
                print(t["sql"].strip())
            else:
                print("(no SQL stored)")

    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

