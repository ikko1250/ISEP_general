import pandas as pd
import re

CSV_PATH = '/home/ubuntu/cur/isep/texts/main4.3_2025-11-17.v.3.csv'

def is_clean_text(text):
    if not isinstance(text, str) or not text:
        return False
    text = text.strip()
    if text.startswith('○'): return False
    if text.startswith('(目的)'): return True
    if text.startswith('(趣旨)'): return True
    if text.startswith('第1条'): return True
    return False

def analyze_hybrid_years():
    try:
        df = pd.read_csv(CSV_PATH, usecols=['自治体', '制定年', '本文'])
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    muni_data = {} # muni -> list of (year, is_clean)

    for _, row in df.iterrows():
        muni = row['自治体']
        year_str = str(row['制定年'])
        text = row['本文']
        
        match = re.search(r'(\d{4})', year_str)
        if not match: continue
        year = int(match.group(1))
        
        if muni not in muni_data:
            muni_data[muni] = []
        
        muni_data[muni].append((year, is_clean_text(text)))
        
    final_years = {}
    
    for muni, records in muni_data.items():
        clean_years = [r[0] for r in records if r[1]]
        all_years = [r[0] for r in records]
        
        if clean_years:
            final_years[muni] = min(clean_years)
        else:
            final_years[muni] = min(all_years)
            
    from collections import Counter
    c = Counter(final_years.values())
    print("\n--- Distribution of HYBRID years ---")
    for y in sorted(c.keys()):
        if 2010 <= y <= 2025:
            print(f"{y}: {c[y]}")

if __name__ == "__main__":
    analyze_hybrid_years()
