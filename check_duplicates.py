import sqlite3
import os
import re

db_path = os.path.join(os.path.dirname(__file__), 'clause-viewer/clause_data3.db')

def check_duplicates():
    if not os.path.exists(db_path):
        print(f"Error: Database file not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get municipalities with multiple years
    sql_multi_years = """
    SELECT m.id, m.name
    FROM municipalities m
    JOIN paragraphs p ON m.id = p.municipality_id
    GROUP BY m.id, m.name
    HAVING COUNT(DISTINCT p.year) > 1
    """
    cursor.execute(sql_multi_years)
    municipalities = cursor.fetchall()

    print(f"Found {len(municipalities)} municipalities with multiple years.")
    print("-" * 60)

    results = []

    for munic_id, munic_name in municipalities:
        # Get years and first paragraph text for each year
        sql_details = """
        SELECT year, text
        FROM paragraphs
        WHERE municipality_id = ? AND category = '条例' AND dan_number = 1
        ORDER BY year
        """
        cursor.execute(sql_details, (munic_id,))
        rows = cursor.fetchall()
        
        # If no '条例' found (maybe only '施行規則'), try without category filter or check '施行規則'
        if not rows:
             sql_details = """
            SELECT year, text
            FROM paragraphs
            WHERE municipality_id = ? AND dan_number = 1
            ORDER BY year
            """
             cursor.execute(sql_details, (munic_id,))
             rows = cursor.fetchall()

        print(f"Municipality: {munic_name}")
        
        munic_info = {'name': munic_name, 'years': []}

        for year, text in rows:
            # Check for patterns
            starts_with_purpose = text.strip().startswith('(目的)') or text.strip().startswith('第1条') or text.strip().startswith('(趣旨)')
            has_date_pattern = re.search(r'令和\d+年|平成\d+年', text)
            has_ordinance_num = re.search(r'条例第\d+号', text)
            
            status = "Unknown"
            if starts_with_purpose and not has_date_pattern:
                status = "Likely Clean (Body)"
            elif has_date_pattern or has_ordinance_num:
                status = "Likely Header/Metadata"
            
            snippet = text[:50].replace('\n', ' ')
            print(f"  Year: {year} | Status: {status} | Text: {snippet}...")
            
            munic_info['years'].append({
                'year': year,
                'status': status,
                'text_snippet': snippet
            })
        
        results.append(munic_info)
        print("-" * 60)

    conn.close()

if __name__ == "__main__":
    check_duplicates()
