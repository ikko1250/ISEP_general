"""
未分類自治体分析スクリプト
以下の条件を満たす自治体を抽出する:
1. lv1ファイルで「禁止・許可・同意」に分類されていない
2. かつ、lv2ファイルにも登場しない
3. かつ、協議・届出分析結果ファイルにも登場しない

つまり、どの分析にも登場しない「漏れ」の自治体を特定する
"""

import pandas as pd
import sqlite3
import os

# 設定
# 設定
DB_PATH = '/home/ubuntu/cur/isep/clause-viewer/clause_data4.db'
LV1_FILE = './CLAUSE_ZONE_Lv1_classification_result.csv'
LV2_FILE = './CLAUSE_ZONE_Lv2_classification_result.csv'
NOTIFICATION_FILE = './notification_structure_analysis_result.csv'
OUTPUT_DIR = './'
OUTPUT_FILE = os.path.join(OUTPUT_DIR, 'unclassified_municipalities_result.csv')

# lv1のカテゴリで除外対象（禁止・許可・同意に分類されている場合に除外）
LV1_EXCLUDE_CATEGORIES = ['禁止', '許可', '同意']


def get_all_municipalities(db_path: str) -> pd.DataFrame:
    """DBからすべての自治体を取得する"""
    conn = sqlite3.connect(db_path)
    query = """
    SELECT id, name, regulation_type, area_type 
    FROM municipalities
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


def get_lv1_excluded_municipalities(lv1_file: str, exclude_cats: list) -> set:
    """lv1ファイルから禁止・許可・同意に分類されている自治体を取得する"""
    df = pd.read_csv(lv1_file)
    excluded = set()
    
    for _, row in df.iterrows():
        cat = str(row.get('category', ''))
        for exc in exclude_cats:
            if exc in cat:
                excluded.add(row['municipality'])
                break
    
    return excluded


def get_lv2_municipalities(lv2_file: str) -> set:
    """lv2ファイルに登場するすべての自治体を取得する"""
    df = pd.read_csv(lv2_file)
    return set(df['municipality'].tolist())


def get_notification_municipalities(notification_file: str) -> set:
    """協議・届出分析結果ファイルに登場する自治体を取得する"""
    df = pd.read_csv(notification_file)
    return set(df['自治体名'].tolist())


def main():
    print("=== 未分類自治体分析スクリプト ===\n")
    print("条件:")
    print("  1. lv1で「禁止・許可・同意」に分類されていない")
    print("  2. かつ、lv2にも登場しない")
    print("  3. かつ、協議・届出ファイルにも登場しない\n")
    
    # 1. DBからすべての自治体を取得
    all_munis_df = get_all_municipalities(DB_PATH)
    all_munis = set(all_munis_df['name'].tolist())
    print(f"DB内の全自治体数: {len(all_munis)}")
    
    # 2. lv1ファイルで禁止・許可・同意に分類されている自治体
    lv1_excluded = get_lv1_excluded_municipalities(LV1_FILE, LV1_EXCLUDE_CATEGORIES)
    print(f"lv1で禁止・許可・同意に分類: {len(lv1_excluded)}")
    
    # 3. lv2ファイルに登場するすべての自治体
    lv2_all = get_lv2_municipalities(LV2_FILE)
    print(f"lv2に登場する自治体: {len(lv2_all)}")
    
    # 4. 協議・届出ファイルに登場する自治体
    notification_munis = get_notification_municipalities(NOTIFICATION_FILE)
    print(f"協議・届出ファイルに登場する自治体: {len(notification_munis)}")
    
    # 5. 未分類自治体を特定
    # ステップ1: lv1で禁止・許可・同意に分類されていない
    lv1_not_excluded = all_munis - lv1_excluded
    # ステップ2: 上記のうちlv2にも登場しない
    step2 = lv1_not_excluded - lv2_all
    # ステップ3: 上記のうち協議・届出にも登場しない
    unclassified = step2 - notification_munis
    
    print(f"\n--- 結果 ---")
    print(f"lv1で禁止・許可・同意に分類されていない: {len(lv1_not_excluded)}")
    print(f"上記のうちlv2にも登場しない: {len(step2)}")
    print(f"上記のうち協議・届出にも登場しない（未分類）: {len(unclassified)}")
    
    if unclassified:
        print(f"\n未分類自治体リスト ({len(unclassified)}件):")
        unclassified_list = sorted(list(unclassified))
        
        # 区域タイプ別に集計
        area_counts = {}
        for muni in unclassified_list:
            muni_info = all_munis_df[all_munis_df['name'] == muni].iloc[0]
            area_type = muni_info['area_type']
            if area_type not in area_counts:
                area_counts[area_type] = []
            area_counts[area_type].append(muni)
            print(f"  {muni} (規制: {muni_info['regulation_type']}, 区域: {area_type})")
        
        # 区域タイプ別サマリー
        print(f"\n--- 区域タイプ別サマリー ---")
        for area_type, munis in sorted(area_counts.items()):
            print(f"  {area_type}: {len(munis)}件")
        
        # 結果をDataFrameにまとめてCSV出力
        result_df = all_munis_df[all_munis_df['name'].isin(unclassified)].copy()
        result_df.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')
        print(f"\n結果をCSVに保存しました: {OUTPUT_FILE}")
        
        # 抑制区域と禁止区域に属する自治体を別CSVに保存
        zone_area_types = ['抑制地区制', '禁止地区制']
        zone_munis_df = result_df[result_df['area_type'].isin(zone_area_types)].copy()
        
        if not zone_munis_df.empty:
            zone_output_file = os.path.join(OUTPUT_DIR, 'unclassified_zone_municipalities.csv')
            zone_munis_df.to_csv(zone_output_file, index=False, encoding='utf-8-sig')
            print(f"\n抑制区域・禁止区域の自治体をCSVに保存しました: {zone_output_file}")
            print(f"  対象件数: {len(zone_munis_df)}件")
            for area_type in zone_area_types:
                count = len(zone_munis_df[zone_munis_df['area_type'] == area_type])
                if count > 0:
                    print(f"    - {area_type}: {count}件")
        else:
            print("\n抑制区域・禁止区域に属する未分類自治体はありません。")
        
        # 区域設定なしの自治体を別CSVに保存
        no_zone_munis_df = result_df[result_df['area_type'] == '区域設定なし'].copy()
        
        if not no_zone_munis_df.empty:
            no_zone_output_file = os.path.join(OUTPUT_DIR, 'unclassified_no_zone_municipalities.csv')
            no_zone_munis_df.to_csv(no_zone_output_file, index=False, encoding='utf-8-sig')
            print(f"\n区域設定なしの自治体をCSVに保存しました: {no_zone_output_file}")
            print(f"  対象件数: {len(no_zone_munis_df)}件")
        else:
            print("\n区域設定なしの未分類自治体はありません。")
    else:
        print("\n未分類自治体はありません。")


if __name__ == "__main__":
    main()

