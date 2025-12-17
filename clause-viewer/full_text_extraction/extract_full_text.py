import sqlite3
import os
import sys
import csv
from pathlib import Path

# Add path for versioning module
sys.path.append('/home/ubuntu/cur/isep')
from versioning.filename import make_dated_versioned_path

# Configuration
DB_PATH = '/home/ubuntu/cur/isep/clause-viewer/clause_data4.db'
OUTPUT_DIR = '/home/ubuntu/cur/isep/clause-viewer/full_text_extraction/output'
CLASSIFICATION_CSV_PATH = '/home/ubuntu/cur/isep/unified_classification_result.csv'

def get_target_municipalities():
    target_categories = [
        "5. その他/分類不能"
    ]
    municipalities = []
    
    try:
        with open(CLASSIFICATION_CSV_PATH, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader, None) # Skip header
            
            # Find indices
            if header:
                try:
                    name_idx = header.index('自治体名')
                    class_idx = header.index('分類')
                except ValueError:
                    # Fallback to hardcoded indices if header doesn't match expected names exactly
                    name_idx = 0
                    class_idx = 1
            else:
                 return []

            for row in reader:
                if len(row) > name_idx:
                    name = row[name_idx]
                    # All municipalities in the CSV are targets
                    municipalities.append(name)
                        
    except FileNotFoundError:
        print(f"Error: Classification file not found at {CLASSIFICATION_CSV_PATH}")
        return []
    except Exception as e:
        print(f"Error reading classification file: {e}")
        return []
        
    return municipalities

TARGET_MUNICIPALITIES = get_target_municipalities()

def main():
    # Ensure base output directory exists
    base_output_dir = Path(OUTPUT_DIR)
    
    # Create versioned folder: extraction_YYYY-MM-DD.v.N
    output_dir = make_dated_versioned_path(base_output_dir, "extraction_", "")
    os.makedirs(output_dir, exist_ok=True)
    print(f"Output contents to: {output_dir}")

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
            
            # Use the common versioned output directory
            muni_output_dir = output_dir

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
