import pandas as pd
import sqlite3
import re
import os

DISCREPANCIES_PATH = 'analysis_discrepancies.csv'
DB_PATH = 'clause-viewer/clause_data3.db'
RULES_PATH = 'khcoder_coding_rules_PV_v4.txt'

def load_rules():
    rules = {}
    current_code = None
    if not os.path.exists(RULES_PATH):
        return {}
    with open(RULES_PATH, 'r', encoding='utf-8-sig') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if line.startswith('*'):
                current_code = line
                rules[current_code] = ''
            elif current_code:
                rules[current_code] += ' ' + line
    return {k: v.strip() for k, v in rules.items()}

def get_text(cursor, municipality, h5, dan):
    cursor.execute("""
        SELECT p.text 
        FROM paragraphs p 
        JOIN municipalities m ON p.municipality_id = m.id 
        WHERE m.name = ? AND p.h5 = ? AND p.dan_number = ?
    """, (municipality, h5, dan))
    res = cursor.fetchone()
    return res[0] if res else "[Text not found]"

def main():
    print("Loading discrepancies...")
    df = pd.read_csv(DISCREPANCIES_PATH)
    
    # Flatten missing codes
    missing_list = []
    for idx, row in df.iterrows():
        if pd.isna(row['missing_in_csv']):
            continue
        codes = [c.strip() for c in row['missing_in_csv'].split(',')]
        for c in codes:
            missing_list.append({'code': c, 'municipality': row['municipality'], 'paragraph_num': row['paragraph_num']})
            
    missing_df = pd.DataFrame(missing_list)
    top_missing = missing_df['code'].value_counts().head(5)
    
    print("\n--- Top 5 Missing Codes ---")
    print(top_missing)
    
    rules = load_rules()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    for code in top_missing.index:
        print(f"\n\n==================================================")
        print(f"Analyzing Code: {code}")
        print(f"Count: {top_missing[code]}")
        print(f"Rule: {rules.get(code, 'Rule not found')}")
        print(f"==================================================")
        
        # Get 3 examples
        examples = missing_df[missing_df['code'] == code].head(3)
        
        for _, row in examples.iterrows():
            muni = row['municipality']
            p_num = row['paragraph_num']
            h5, dan = map(int, p_num.split('-'))
            
            text = get_text(cursor, muni, h5, dan)
            
            # Get the full row from original df to show other codes
            orig_row = df[(df['municipality'] == muni) & (df['paragraph_num'] == p_num)].iloc[0]
            
            print(f"\n[Example] {muni} {p_num}")
            print(f"Text: {text}")
            print(f"Expected (DB): {orig_row['db_codes']}")
            print(f"Actual (CSV):  {orig_row['csv_codes']}")
            
    conn.close()

if __name__ == "__main__":
    main()
