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

def analyze_clean_years():
    try:
        df = pd.read_csv(CSV_PATH, usecols=['自治体', '制定年', '本文'])
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    print(f"Total rows: {len(df)}")
    
    clean_counts = 0
    clean_years_map = {} # muni -> list of clean years
    
    for _, row in df.iterrows():
        muni = row['自治体']
        year_str = str(row['制定年'])
        text = row['本文']
        
        match = re.search(r'(\d{4})', year_str)
        if not match: continue
        year = int(match.group(1))
        
        if is_clean_text(text):
            clean_counts += 1
            if muni not in clean_years_map:
                clean_years_map[muni] = []
            clean_years_map[muni].append(year)
            
    print(f"Clean rows found: {clean_counts}")
    print(f"Municipalities with clean text: {len(clean_years_map)}")
    
    # Check 2021 specifically
    years_flat = []
    for ys in clean_years_map.values():
        years_flat.extend(ys)
        
    from collections import Counter
    c = Counter(years_flat)
    print("\n--- Distribution of CLEAN years ---")
    for y in sorted(c.keys()):
        if 2010 <= y <= 2025:
            print(f"{y}: {c[y]}")

    # Check comparison with previous specific drop analysis
    # If we use MIN(clean_year), what do we get?
    final_years = {}
    for muni, ys in clean_years_map.items():
        if ys:
            final_years[muni] = min(ys)
            
    c_final = Counter(final_years.values())
    print("\n--- Distribution of MIN CLEAN years ---")
    for y in sorted(c_final.keys()):
        if 2010 <= y <= 2025:
            print(f"{y}: {c_final[y]}")

if __name__ == "__main__":
    analyze_clean_years()
