#!/usr/bin/env python3
import sqlite3
from collections import defaultdict
from pathlib import Path


DB_PATH = Path(__file__).with_name("clause_data.db")


def fetchall(db, q, params=()):
    cur = db.cursor()
    cur.execute(q, params)
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def main():
    con = sqlite3.connect(str(DB_PATH))
    # Overall year distribution
    overall = fetchall(
        con,
        """
        SELECT year, COUNT(*) AS cnt
        FROM paragraphs
        WHERE year IS NOT NULL AND TRIM(year) <> ''
        GROUP BY year
        ORDER BY cnt DESC, year
        """,
    )

    print("=== Overall year distribution (top 20) ===")
    for row in overall[:20]:
        print(f"{row['year']}: {row['cnt']}")
    if overall:
        total = sum(r["cnt"] for r in overall)
        top = overall[0]
        print(
            f"Top year share: {top['year']} -> {top['cnt']} / {total} = {top['cnt']/total:.1%}"
        )

    # Per-municipality dominance: share of most frequent year within each municipality
    per_muni = fetchall(
        con,
        """
        SELECT m.name AS municipality, p.year AS year, COUNT(*) AS cnt
        FROM paragraphs p
        JOIN municipalities m ON m.id = p.municipality_id
        WHERE p.year IS NOT NULL AND TRIM(p.year) <> ''
        GROUP BY m.name, p.year
        ORDER BY m.name, cnt DESC
        """,
    )

    # Aggregate to find dominant year per municipality
    muni_totals = defaultdict(int)
    muni_year_counts = defaultdict(list)
    for r in per_muni:
        muni_totals[r["municipality"]] += r["cnt"]
        muni_year_counts[r["municipality"]].append((r["year"], r["cnt"]))

    dominance = []
    for muni, items in muni_year_counts.items():
        items.sort(key=lambda x: x[1], reverse=True)
        top_year, top_cnt = items[0]
        total = muni_totals[muni]
        dominance.append(
            {
                "municipality": muni,
                "year": top_year,
                "top_cnt": top_cnt,
                "total": total,
                "share": top_cnt / total if total else 0.0,
                "distinct_years": len(items),
            }
        )

    dominance.sort(key=lambda x: (x["share"], x["top_cnt"]), reverse=True)
    print("\n=== Municipalities with strongest single-year dominance (top 20) ===")
    for d in dominance[:20]:
        print(
            f"{d['municipality']}: {d['year']} {d['top_cnt']}/{d['total']} ({d['share']:.1%}), years={d['distinct_years']}"
        )

    # Specifically show えりも町
    for d in dominance:
        if d["municipality"] == "えりも町":
            print(
                f"\n[えりも町] top year: {d['year']} {d['top_cnt']}/{d['total']} ({d['share']:.1%}), distinct years={d['distinct_years']}"
            )
            break


if __name__ == "__main__":
    main()

