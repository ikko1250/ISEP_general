import sqlite3
from pathlib import Path
from datetime import datetime

# === Settings you can edit ===
DB_PATH = Path('clause-viewer/clause_data.db')

# Map municipality name -> new manual regulation_type.
# Set value to None to clear the manual override (revert to automatic).
OVERRIDES = {
    # Examples:
    # '吉賀町': '許可制優位',
    # '松本市': '届出制優位',
    # '木曽町': None,  # clear manual override
}

# Metadata for logging
CHANGED_BY = 'script:update_regulation_type_overrides'
NOTE = 'Manual override of regulation_type'

# Safety: start with dry-run. Set to False to actually write changes.
DRY_RUN = True


def ensure_schema(conn: sqlite3.Connection):
    cur = conn.cursor()
    # Add manual column if missing
    cur.execute("PRAGMA table_info('municipalities')")
    cols = {row[1] for row in cur.fetchall()}
    if 'regulation_type_manual' not in cols:
        cur.execute("ALTER TABLE municipalities ADD COLUMN regulation_type_manual TEXT")

    # Create change log table if missing
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS municipality_regulation_type_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            municipality_id INTEGER,
            municipality_name TEXT,
            old_auto TEXT,
            old_manual TEXT,
            new_manual TEXT,
            note TEXT,
            changed_by TEXT,
            changed_at TEXT,
            FOREIGN KEY (municipality_id) REFERENCES municipalities(id)
        )
        """
    )
    conn.commit()


def apply_overrides(conn: sqlite3.Connection):
    cur = conn.cursor()
    results = []
    for name, new_manual in OVERRIDES.items():
        cur.execute("SELECT id, name, regulation_type, regulation_type_manual FROM municipalities WHERE name = ?", (name,))
        row = cur.fetchone()
        if not row:
            results.append((name, None, None, None, new_manual, 'NOT_FOUND'))
            continue
        mun_id, mun_name, old_auto, old_manual = row

        # Prepare update
        if not DRY_RUN:
            cur.execute(
                "UPDATE municipalities SET regulation_type_manual = ? WHERE id = ?",
                (new_manual, mun_id),
            )
            cur.execute(
                """
                INSERT INTO municipality_regulation_type_changes
                (municipality_id, municipality_name, old_auto, old_manual, new_manual, note, changed_by, changed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    mun_id,
                    mun_name,
                    old_auto,
                    old_manual,
                    new_manual,
                    NOTE,
                    CHANGED_BY,
                    datetime.utcnow().isoformat(timespec='seconds') + 'Z',
                ),
            )
        results.append((mun_name, mun_id, old_auto, old_manual, new_manual, 'OK'))

    if not DRY_RUN:
        conn.commit()
    return results


def main():
    conn = sqlite3.connect(DB_PATH)
    try:
        ensure_schema(conn)
        results = apply_overrides(conn)
        print(f"Dry-run: {DRY_RUN}")
        for r in results:
            mun_name, mun_id, old_auto, old_manual, new_manual, status = r
            print(
                f"[{status}] {mun_name or 'N/A'} (id={mun_id}) auto='{old_auto}' manual(before)='{old_manual}' -> manual(after)='{new_manual}'"
            )
        if DRY_RUN:
            print("No changes written. Set DRY_RUN=False to apply.")
    finally:
        conn.close()


if __name__ == '__main__':
    main()

