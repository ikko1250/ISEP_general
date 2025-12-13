
import pandas as pd
import re
import sys

CSV_PATH = '/home/ubuntu/cur/isep/texts/main4.3_2025-11-17.v.3.csv'

def analyze_years():
    print(f"Reading {CSV_PATH}...")
    try:
        df = pd.read_csv(CSV_PATH, usecols=['自治体', '制定年'])
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    print(f"Total rows: {len(df)}")
    
    # Check for raw values
    print("\n--- Raw '制定年' values distribution (Top 20) ---")
    print(df['制定年'].value_counts().head(20).sort_index())
    
    # Check specifically for values containing '2021' or 'R3', '令和3' etc
    print("\n--- Rows potentially related to 2021 ---")
    possible_2021 = df[df['制定年'].astype(str).str.contains('2021|令和3|R3', na=False)]
    print(f"Count of rows matching '2021|令和3|R3': {len(possible_2021)}")
    print(possible_2021['制定年'].value_counts())

    # Apply the same logic as the main script
    year_map = {}
    parsed_counts = {}
    
    for _, row in df.iterrows():
        muni_name = row['自治体']
        year_str = str(row['制定年'])
        
        if pd.isna(muni_name) or pd.isna(year_str):
            continue
            
        match = re.search(r'(\d{4})', year_str)
        if match:
            year = int(match.group(1))
            parsed_counts[year] = parsed_counts.get(year, 0) + 1
            
            if muni_name not in year_map or year < year_map[muni_name]:
                year_map[muni_name] = year

    print("\n--- Parsed Year Counts (All rows) ---")
    for y in sorted(parsed_counts.keys()):
        if 2010 <= y <= 2025:
            print(f"{y}: {parsed_counts[y]}")

    print("\n--- Unique Municipality Enactment Years (Final Used Data) ---")
    final_year_counts = {}
    for y in year_map.values():
        final_year_counts[y] = final_year_counts.get(y, 0) + 1
        
    for y in sorted(final_year_counts.keys()):
        if 2010 <= y <= 2025:
            print(f"{y}: {final_year_counts[y]}")

if __name__ == "__main__":
    analyze_years()
