import pandas as pd
import sqlite3
import os

# Paths
CSV_PATH = '/home/ubuntu/cur/isep/analysis_results_sudachi_paragraphs.csv'
DB_PATH = '/home/ubuntu/cur/isep/clause-viewer/clause_data3.db'
OUTPUT_CSV = 'analysis_discrepancies.csv'

def load_csv_data(csv_path):
    print(f"Loading CSV from {csv_path}...")
    df = pd.read_csv(csv_path)
    # Group by municipality and paragraph_num to get unique codes for each paragraph
    # We assume 'matched_codes' contains the code for the paragraph.
    # We'll collect all unique non-null codes for each paragraph.
    
    # Filter out rows where matched_codes is null or empty
    df_codes = df[df['matched_codes'].notna() & (df['matched_codes'] != '')]
    
    # Group and aggregate
    grouped = df_codes.groupby(['municipality', 'paragraph_num'])['matched_codes'].unique()
    
    # Convert numpy arrays to sets for easier comparison
    paragraph_codes = {}
    for (muni, para_num), codes in grouped.items():
        # codes is a numpy array of strings. 
        # It might contain comma-separated values if multiple codes are assigned?
        # Based on inspection, it seems single valued, but let's handle potential commas just in case
        code_set = set()
        for code in codes:
            if ',' in code:
                code_set.update(c.strip() for c in code.split(','))
            else:
                code_set.add(code)
        paragraph_codes[(muni, para_num)] = code_set
        
    print(f"Loaded {len(paragraph_codes)} paragraphs from CSV.")
    return paragraph_codes

def load_db_data(db_path):
    print(f"Loading data from DB {db_path}...")
    conn = sqlite3.connect(db_path)
    
    query = """
    SELECT 
        m.name as municipality,
        p.h5,
        p.dan_number,
        ct.code as coding_type
    FROM paragraphs p
    JOIN municipalities m ON p.municipality_id = m.id
    LEFT JOIN paragraph_codings pc ON p.id = pc.paragraph_id
    LEFT JOIN coding_types ct ON pc.coding_type_id = ct.id
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    # Construct paragraph_num as h5-dan_number
    df['paragraph_num'] = df['h5'].astype(str) + '-' + df['dan_number'].astype(str)
    
    # Group by municipality and paragraph_num
    # Filter out null coding_types
    df_codes = df[df['coding_type'].notna()]
    
    grouped = df_codes.groupby(['municipality', 'paragraph_num'])['coding_type'].unique()
    
    paragraph_codes = {}
    for (muni, para_num), codes in grouped.items():
        code_set = set(codes)
        paragraph_codes[(muni, para_num)] = code_set
        
    print(f"Loaded {len(paragraph_codes)} paragraphs with codes from DB.")
    return paragraph_codes

def compare_results(csv_data, db_data):
    print("Comparing results...")
    
    # Union of all keys
    all_keys = set(csv_data.keys()) | set(db_data.keys())
    
    total_paragraphs = len(all_keys)
    perfect_matches = 0
    discrepancies = []
    
    for key in all_keys:
        muni, para_num = key
        
        csv_codes = csv_data.get(key, set())
        db_codes = db_data.get(key, set())
        
        if csv_codes == db_codes:
            perfect_matches += 1
        else:
            # Record discrepancy
            missing_in_csv = db_codes - csv_codes
            extra_in_csv = csv_codes - db_codes
            
            discrepancies.append({
                'municipality': muni,
                'paragraph_num': para_num,
                'csv_codes': ', '.join(sorted(csv_codes)),
                'db_codes': ', '.join(sorted(db_codes)),
                'missing_in_csv': ', '.join(sorted(missing_in_csv)),
                'extra_in_csv': ', '.join(sorted(extra_in_csv))
            })
            
    accuracy = (perfect_matches / total_paragraphs) * 100 if total_paragraphs > 0 else 0
    
    print(f"Total Paragraphs: {total_paragraphs}")
    print(f"Perfect Matches: {perfect_matches}")
    print(f"Accuracy: {accuracy:.2f}%")
    
    return discrepancies

def analyze_discrepancies(discrepancies):
    if not discrepancies:
        print("No discrepancies found.")
        return
        
    df = pd.DataFrame(discrepancies)
    
    print("\n--- Discrepancy Analysis ---")
    
    # 1. Common missing codes (False Negatives)
    all_missing = []
    for d in discrepancies:
        if d['missing_in_csv']:
            all_missing.extend(d['missing_in_csv'].split(', '))
    
    if all_missing:
        print("\nTop 10 Missing Codes (Present in DB, missing in CSV):")
        print(pd.Series(all_missing).value_counts().head(10))
        
    # 2. Common extra codes (False Positives)
    all_extra = []
    for d in discrepancies:
        if d['extra_in_csv']:
            all_extra.extend(d['extra_in_csv'].split(', '))
            
    if all_extra:
        print("\nTop 10 Extra Codes (Present in CSV, missing in DB):")
        print(pd.Series(all_extra).value_counts().head(10))
        
    # Save to CSV
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"\nDetailed discrepancies saved to {OUTPUT_CSV}")

def main():
    csv_data = load_csv_data(CSV_PATH)
    db_data = load_db_data(DB_PATH)
    
    discrepancies = compare_results(csv_data, db_data)
    analyze_discrepancies(discrepancies)

if __name__ == "__main__":
    main()
