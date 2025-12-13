import pandas as pd
import re

CSV_PATH = '/home/ubuntu/cur/isep/texts/main4.3_2025-11-17.v.3.csv'

def analyze_2021_drop():
    try:
        df = pd.read_csv(CSV_PATH, usecols=['自治体', '制定年'])
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    # 1. 2021年の行を抽出
    rows_2021 = []
    for _, row in df.iterrows():
        year_str = str(row['制定年'])
        match = re.search(r'(\d{4})', year_str)
        if match and int(match.group(1)) == 2021:
            rows_2021.append(row['自治体'])
    
    print(f"2021年のデータ行数: {len(rows_2021)}")
    
    # 2. 全データのマップ作成（最も古い年を保持する現在のロジック）
    min_year_map = {}
    for _, row in df.iterrows():
        muni_name = row['自治体']
        year_str = str(row['制定年'])
        match = re.search(r'(\d{4})', year_str)
        if match:
            year = int(match.group(1))
            if muni_name not in min_year_map or year < min_year_map[muni_name]:
                min_year_map[muni_name] = year

    # 3. 2021年の行に含まれていた自治体が、最終的に何年として扱われたか確認
    count_2021_kept = 0
    reasons = {}
    
    print("\n--- 2021年のデータを持つ自治体の最終採用年 ---")
    for muni in set(rows_2021):
        final_year = min_year_map.get(muni)
        if final_year == 2021:
            count_2021_kept += 1
        else:
            reasons[final_year] = reasons.get(final_year, 0) + 1
            # print(f"{muni}: 2021 -> {final_year}") # 詳細が見たい場合
            
    print(f"最終的に2021年として採用された自治体数: {count_2021_kept}")
    print(f"より古い年が採用された数: {len(set(rows_2021)) - count_2021_kept}")
    
    print("\nより古い年の内訳:")
    for y in sorted(reasons.keys()):
        print(f"{y}年: {reasons[y]}件")

if __name__ == "__main__":
    analyze_2021_drop()
