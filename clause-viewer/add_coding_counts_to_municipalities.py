import argparse
import os
import re
import shutil
import sqlite3
from datetime import datetime


def slugify_code(code: str) -> str:
    # Remove leading asterisks and non-alphanumerics -> underscore
    code = code.lstrip('*')
    slug = re.sub(r"[^A-Za-z0-9]+", "_", code).strip("_")
    return slug


def ensure_columns(conn: sqlite3.Connection, columns):
    cur = conn.cursor()
    cur.execute("PRAGMA table_info('municipalities')")
    existing = {row[1] for row in cur.fetchall()}  # row[1] = name

    for col in columns:
        if col not in existing:
            cur.execute(f"ALTER TABLE municipalities ADD COLUMN {col} INTEGER")
    conn.commit()


def backfill_counts(conn: sqlite3.Connection, mapping):
    cur = conn.cursor()
    # Use one update per coding type to keep it simple and explicit
    for coding_type_id, column in mapping:
        cur.execute(
            f"""
            UPDATE municipalities AS m
            SET {column} = (
                SELECT COUNT(*)
                FROM paragraphs p
                JOIN paragraph_codings pc ON pc.paragraph_id = p.id
                WHERE p.municipality_id = m.id
                  AND pc.coding_type_id = ?
            )
            """,
            (coding_type_id,),
        )
    conn.commit()


def main(db_path: str, backup: bool = True):
    if backup:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = f"{db_path}.bak.{ts}"
        shutil.copy2(db_path, backup_path)
        print(f"Backup created: {backup_path}")

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        # Fetch coding types
        cur.execute("SELECT id, code FROM coding_types ORDER BY id")
        coding_types = cur.fetchall()

        # Build column names: count_<slug>
        mapping = []  # list of (coding_type_id, column_name)
        for ct_id, code in coding_types:
            slug = slugify_code(code)
            column = f"count_{slug}"
            mapping.append((ct_id, column))

        # Ensure columns exist
        ensure_columns(conn, [col for _, col in mapping])

        # Backfill counts from paragraph_codings
        backfill_counts(conn, mapping)

        # Quick sanity check: show counts for a few municipalities
        cur.execute(
            "SELECT name, id FROM municipalities ORDER BY id LIMIT 5"
        )
        sample = cur.fetchall()
        if sample:
            # Build a small projection using first 3 columns
            preview_cols = [mapping[i][1] for i in range(min(3, len(mapping)))]
            cols_sql = ", ".join(preview_cols)
            ids = ",".join(str(s[1]) for s in sample)
            q = f"SELECT name, {cols_sql} FROM municipalities WHERE id IN ({ids}) ORDER BY id"
            cur.execute(q)
            rows = cur.fetchall()
            print("Preview (name, " + ", ".join(preview_cols) + "):")
            for r in rows:
                print(r)

        print("Done: columns added and counts backfilled.")
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Add coding count columns to municipalities and backfill counts.")
    parser.add_argument("db", help="Path to SQLite database (clause_data.db)")
    parser.add_argument("--no-backup", action="store_true", help="Do not create a backup copy of the DB")
    args = parser.parse_args()
    main(args.db, backup=not args.no_backup)

