import sqlite3
import os

# Configuration
DB_PATH = '/home/ubuntu/cur/isep/clause-viewer/clause_data4.db'
OUTPUT_DIR = '/home/ubuntu/cur/isep/clause-viewer/full_text_extraction/output'
TARGET_MUNICIPALITIES = [
    '内子町',
    '和歌山市',
    '恵那市',
    '朝日村',
    '長野県筑北村',
    '飯能市'
]

def main():
    # Ensure output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        for muni_name in TARGET_MUNICIPALITIES:
            print(f"Processing {muni_name}...")
            
            # Get municipality_id
            cursor.execute("SELECT id FROM municipalities WHERE name = ?", (muni_name,))
            row = cursor.fetchone()
            
            if not row:
                print(f"  Warning: Municipality '{muni_name}' not found in database.")
                continue
            
            muni_id = row[0]
            
            # Create municipality specific folder
            muni_output_dir = os.path.join(OUTPUT_DIR, muni_name)
            os.makedirs(muni_output_dir, exist_ok=True)

            # Extract '条例' (Ordinance)
            extract_and_save(cursor, muni_id, '条例', muni_name, muni_output_dir)

            # Extract '施行規則' (Enforcement Regulation)
            extract_and_save(cursor, muni_id, '施行規則', muni_name, muni_output_dir)
            
    finally:
        conn.close()
        print("Done.")

def extract_and_save(cursor, muni_id, category, muni_name, output_dir):
    cursor.execute("""
        SELECT text 
        FROM paragraphs 
        WHERE municipality_id = ? AND category = ? 
        ORDER BY dan_number
    """, (muni_id, category))
    
    rows = cursor.fetchall()
    
    if not rows:
        print(f"  No text found for {category} in {muni_name}")
        return

    filename = f"{muni_name}_{category}.txt"
    filepath = os.path.join(output_dir, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        for row in rows:
            text = row[0]
            if text:
                f.write(text + "\n")
    
    print(f"  Saved {category} to {filepath} ({len(rows)} paragraphs)")

if __name__ == '__main__':
    main()
