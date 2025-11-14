#!/usr/bin/env python3
import argparse
import sqlite3
from pathlib import Path


def find_years(db_path: Path, municipality_name: str):
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        cur = con.cursor()
        cur.execute(
            """
            SELECT p.year, COUNT(*) as cnt
            FROM paragraphs p
            JOIN municipalities m ON p.municipality_id = m.id
            WHERE m.name = ? AND p.year IS NOT NULL AND TRIM(p.year) != ''
            GROUP BY p.year
            ORDER BY p.year
            """,
            (municipality_name,),
        )
        rows = cur.fetchall()
        return rows
    finally:
        con.close()


def main():
    parser = argparse.ArgumentParser(
        description="Show distinct 'year' values for a municipality in the SQLite DB."
    )
    parser.add_argument(
        "db",
        nargs="?",
        default="clause-viewer/clause_data.db",
        help="Path to SQLite DB (default: clause-viewer/clause_data.db)",
    )
    parser.add_argument(
        "-m",
        "--municipality",
        default="えりも町",
        help="Municipality name to search (default: えりも町)",
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        raise SystemExit(f"DB not found: {db_path}")

    rows = find_years(db_path, args.municipality)

    if not rows:
        print(f"No year values found for municipality: {args.municipality}")
        return

    print(f"Municipality: {args.municipality}")
    print("Years (distinct) with paragraph counts:")
    for r in rows:
        print(f"  - {r['year']}: {r['cnt']}")

    if len(rows) == 1:
        print(f"\n=> Treated adoption year: {rows[0]['year']}")
    else:
        # Heuristic: most frequent year as representative
        most = max(rows, key=lambda x: x["cnt"]) if rows else None
        if most:
            print(
                f"\n=> Likely representative year (most frequent): {most['year']} (count={most['cnt']})"
            )


if __name__ == "__main__":
    main()

