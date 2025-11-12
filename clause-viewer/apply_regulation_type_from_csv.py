import csv
import sqlite3
from collections import defaultdict
from datetime import datetime
from pathlib import Path

DB_PATH = Path('clause-viewer/clause_data.db')
CSV_PATH = Path('clause-viewer/mixed_regulation_positive_permission_paragraphs.csv')

# Column names in the CSV
COL_MUNICIPALITY = 'municipality_name'
COL_NEW_VALUE = '変更先'

# Safety first: preview changes without writing.
DRY_RUN = False
CHANGED_BY = 'script:apply_regulation_type_from_csv'
NOTE = 'Update regulation_type per CSV 変更先; preserve original in regulation_type_original'


def ensure_schema(conn: sqlite3.Connection):
    cur = conn.cursor()
    # regulation_type_original column
    cur.execute("PRAGMA table_info('municipalities')")
    cols = {row[1] for row in cur.fetchall()}
    if 'regulation_type_original' not in cols:
        cur.execute("ALTER TABLE municipalities ADD COLUMN regulation_type_original TEXT")

    # Single, simple update log
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS regulation_type_update_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            municipality_id INTEGER,
            municipality_name TEXT,
            old_value TEXT,
            new_value TEXT,
            source TEXT,
            note TEXT,
            changed_by TEXT,
            changed_at TEXT,
            FOREIGN KEY (municipality_id) REFERENCES municipalities(id)
        )
        """
    )
    conn.commit()


def backfill_original(conn: sqlite3.Connection):
    cur = conn.cursor()
    # Only copy when original is NULL
    cur.execute(
        "UPDATE municipalities SET regulation_type_original = regulation_type WHERE regulation_type_original IS NULL"
    )
    return cur.rowcount


def read_mapping_from_csv(csv_path: Path):
    mapping = defaultdict(set)
    with csv_path.open('r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get(COL_MUNICIPALITY) or '').strip()
            new_val = (row.get(COL_NEW_VALUE) or '').strip()
            if not name:
                continue
            if new_val:
                mapping[name].add(new_val)
    # Normalize: pick one value per municipality, warn on conflicts
    final = {}
    conflicts = {}
    for name, values in mapping.items():
        if len(values) > 1:
            conflicts[name] = sorted(values)
        # deterministic pick: sorted first
        final[name] = sorted(values)[0]
    return final, conflicts


def apply_updates(conn: sqlite3.Connection, updates: dict):
    cur = conn.cursor()
    stats = {'updated': 0, 'not_found': 0}
    for name, new_val in updates.items():
        cur.execute(
            "SELECT id, name, regulation_type, regulation_type_original FROM municipalities WHERE name = ?",
            (name,),
        )
        row = cur.fetchone()
        if not row:
            stats['not_found'] += 1
            print(f"[WARN] Municipality not found: {name}")
            continue
        mun_id, mun_name, old_val, orig_val = row
        if not DRY_RUN:
            cur.execute(
                "UPDATE municipalities SET regulation_type = ? WHERE id = ?",
                (new_val, mun_id),
            )
            cur.execute(
                """
                INSERT INTO regulation_type_update_log
                (municipality_id, municipality_name, old_value, new_value, source, note, changed_by, changed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    mun_id,
                    mun_name,
                    old_val,
                    new_val,
                    'CSV:変更先',
                    NOTE,
                    CHANGED_BY,
                    datetime.utcnow().isoformat(timespec='seconds') + 'Z',
                ),
            )
        stats['updated'] += 1
        print(f"[OK] {mun_name} (id={mun_id}) {old_val} -> {new_val} (original={orig_val})")

    if not DRY_RUN:
        conn.commit()
    return stats


def main():
    # Read mapping from CSV
    updates, conflicts = read_mapping_from_csv(CSV_PATH)
    print(f"Loaded updates from CSV: {len(updates)} municipalities with 変更先")
    if conflicts:
        print("[WARN] Conflicting 変更先 values detected:")
        for k, vs in conflicts.items():
            print(f"  - {k}: {vs} -> using '{vs[0]}'")

    conn = sqlite3.connect(DB_PATH)
    try:
        ensure_schema(conn)
        copied = backfill_original(conn)
        print(f"Backfilled regulation_type_original for {copied} rows (NULL only)")
        stats = apply_updates(conn, updates)
        print(f"Dry-run: {DRY_RUN}")
        print(f"Summary: updated={stats['updated']} not_found={stats['not_found']}")
        if DRY_RUN:
            print("No changes written. Set DRY_RUN=False to apply.")
    finally:
        conn.close()


if __name__ == '__main__':
    main()
