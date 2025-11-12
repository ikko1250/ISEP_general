import csv
import sqlite3
from pathlib import Path

DB_PATH = Path('clause-viewer/clause_data.db')
OUT_CSV = Path('clause-viewer/mixed_regulation_positive_permission_paragraphs.csv')


def main():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    # Get coding_type_id for *CLAUSE_POSITIVE_PERMISSION_CONSENT
    cur.execute(
        "SELECT id FROM coding_types WHERE code = '*CLAUSE_POSITIVE_PERMISSION_CONSENT'"
    )
    row = cur.fetchone()
    if not row:
        raise SystemExit('Coding type *CLAUSE_POSITIVE_PERMISSION_CONSENT not found')
    coding_id = row[0]

    # Query paragraphs for mixed-type municipalities with the coding present
    query = (
        """
        SELECT 
            m.id AS municipality_id,
            m.name AS municipality_name,
            p.id AS paragraph_id,
            p.year,
            p.category,
            p.dan_number,
            p.text
        FROM paragraphs p
        JOIN municipalities m ON m.id = p.municipality_id
        JOIN paragraph_codings pc ON pc.paragraph_id = p.id
        WHERE m.regulation_type = '混合型'
          AND pc.coding_type_id = ?
        ORDER BY m.id, p.id
        """
    )

    cur.execute(query, (coding_id,))
    rows = cur.fetchall()

    # Write CSV
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow([
            'municipality_id',
            'municipality_name',
            'paragraph_id',
            'year',
            'category',
            'dan_number',
            'text',
        ])
        for r in rows:
            w.writerow(r)

    print(f'Exported {len(rows)} rows to {OUT_CSV}')


if __name__ == '__main__':
    main()

