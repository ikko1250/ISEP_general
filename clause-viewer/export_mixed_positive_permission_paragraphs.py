import csv
import sqlite3
from pathlib import Path

DB_PATH = Path('clause-viewer/clause_data.db')
OUT_CSV = Path('clause-viewer/stakeholder_confirmation_paragraphs.csv')


def main():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    # Get coding_type_id for *CLAUSE_STAKEHOLDER_CONFIRMATION
    cur.execute(
        "SELECT id FROM coding_types WHERE code = '*CLAUSE_STAKEHOLDER_CONFIRMATION'"
    )
    row = cur.fetchone()
    if not row:
        raise SystemExit('Coding type *CLAUSE_STAKEHOLDER_CONFIRMATION not found')
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
        WHERE pc.coding_type_id = ?
        -- AND m.regulation_type = '混合型'  -- フィルターを外すためコメントアウト（全自治体を対象）
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
