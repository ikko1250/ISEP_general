#!/usr/bin/env python3
"""
Export paragraphs that have a specific coding type to CSV.

Examples:
  python export_paragraphs_by_code.py clause_data.db --code "*CLAUSE_ENVIRONMENT" -o env_paragraphs.csv
  python export_paragraphs_by_code.py clause_data.db --code-id 8 -o env_paragraphs.csv

Columns exported (default):
  paragraph_id, municipality, year, category, dan_number, text, code, code_description
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description="Export paragraphs filtered by coding type to CSV")
    ap.add_argument("db", type=Path, help="Path to SQLite database (e.g., clause_data.db)")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--code", help="Coding type code string (e.g., *CLAUSE_ENVIRONMENT)")
    g.add_argument("--code-id", type=int, help="Coding type id (numeric)")
    ap.add_argument("-o", "--output", type=Path, default=Path("filtered_paragraphs.csv"), help="Output CSV path")
    ap.add_argument("--bom", action="store_true", help="Write UTF-8 BOM for Excel compatibility")
    args = ap.parse_args()

    if not args.db.exists():
        raise SystemExit(f"DB not found: {args.db}")

    # Open DB read-only to avoid any journaling writes in restricted envs
    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    # Use in-memory temp store to avoid writing to /tmp in sandboxed envs
    conn.execute("PRAGMA temp_store=MEMORY")

    # Resolve code id if code string provided
    code_id = args.code_id
    code_str = None
    if args.code is not None:
        row = conn.execute("SELECT id, code, description FROM coding_types WHERE code = ?", (args.code,)).fetchone()
        if not row:
            raise SystemExit(f"No such code in coding_types: {args.code}")
        code_id = int(row["id"])
        code_str = row["code"]
    else:
        row = conn.execute("SELECT id, code, description FROM coding_types WHERE id = ?", (code_id,)).fetchone()
        if not row:
            raise SystemExit(f"No such code id in coding_types: {code_id}")
        code_str = row["code"]

    sql = """
    SELECT 
        p.id AS paragraph_id,
        m.name AS municipality,
        p.year,
        p.category,
        p.dan_number,
        p.text,
        ct.code AS code,
        ct.description AS code_description
    FROM paragraph_codings pc
    JOIN paragraphs p ON p.id = pc.paragraph_id
    LEFT JOIN municipalities m ON m.id = p.municipality_id
    JOIN coding_types ct ON ct.id = pc.coding_type_id
    WHERE pc.coding_type_id = ?
    ORDER BY municipality, p.id
    """

    rows = conn.execute(sql, (code_id,)).fetchall()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "paragraph_id",
        "municipality",
        "year",
        "category",
        "dan_number",
        "text",
        "code",
        "code_description",
    ]

    # Excel-friendly BOM if requested
    encoding = "utf-8-sig" if args.bom else "utf-8"
    with args.output.open("w", newline="", encoding=encoding) as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r[k] for k in fieldnames})

    print(f"Exported {len(rows)} rows for code {code_str} (id={code_id}) -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
