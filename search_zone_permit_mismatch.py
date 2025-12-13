#!/usr/bin/env python
"""
目的: 抑制区域または禁止区域の設定があり、かつ許可制が敷かれているが、
抑制区域又は禁止区域と結びついた形での許可制が敷かれていない自治体のリストを作成する。

検索条件:
1. dbのmunicipalities.area_type が '抑制地区制', '禁止地区制', '2層構造(抑制+禁止)' のいずれか
2. dbのmunicipalities.regulation_type が '許可制優位'
3. lv1ファイルのcategoryが '許可', '禁止', '同意' を含まない
4. lv2ファイルのcategoryが '絶対禁止', '条件付き禁止', '許可制' を含まない
"""

import sqlite3
import pandas as pd
from pathlib import Path

# ファイルパス
DB_PATH = Path('/home/ubuntu/cur/isep/clause-viewer/clause_data4.db')
LV1_CSV_PATH = Path('/home/ubuntu/cur/isep/clause-viewer/CLAUSE_ZONE_Lv1_classification_result.csv')
LV2_CSV_PATH = Path('/home/ubuntu/cur/isep/clause-viewer/CLAUSE_ZONE_Lv2_classification_result.csv')
OUTPUT_PATH = Path('/home/ubuntu/cur/isep/zone_permit_mismatch_result.csv')

# カテゴリに含まれれば除外する文字列
LV1_EXCLUDE_KEYWORDS = ['許可', '禁止', '同意']
LV2_EXCLUDE_KEYWORDS = ['絶対禁止', '条件付き禁止', '許可制']


def main():
    # 1. データベースから条件に合う自治体を取得
    conn = sqlite3.connect(DB_PATH)
    
    # 区域設定ありかつ許可制の自治体を取得
    query = """
    SELECT name 
    FROM municipalities 
    WHERE area_type IN ('抑制地区制', '禁止地区制', '2層構造(抑制+禁止)')
      AND regulation_type = '許可制優位'
    """
    db_municipalities = pd.read_sql_query(query, conn)
    conn.close()
    
    target_municipalities = set(db_municipalities['name'].tolist())
    print(f"条件1・2を満たす自治体数: {len(target_municipalities)}")
    
    # 2. Lv1 CSVを読み込み、除外対象の自治体を特定
    lv1_df = pd.read_csv(LV1_CSV_PATH)
    
    # Lv1で除外キーワードを含むカテゴリの自治体を取得
    lv1_exclude_mask = lv1_df['category'].apply(
        lambda x: any(kw in str(x) for kw in LV1_EXCLUDE_KEYWORDS)
    )
    lv1_exclude_municipalities = set(lv1_df[lv1_exclude_mask]['municipality'].tolist())
    print(f"Lv1で除外対象（{LV1_EXCLUDE_KEYWORDS}を含む）: {len(lv1_exclude_municipalities)}")
    
    # 3. Lv2 CSVを読み込み、除外対象の自治体を特定
    lv2_df = pd.read_csv(LV2_CSV_PATH)
    
    # Lv2で除外キーワードを含むカテゴリの自治体を取得
    lv2_exclude_mask = lv2_df['category'].apply(
        lambda x: any(kw in str(x) for kw in LV2_EXCLUDE_KEYWORDS)
    )
    lv2_exclude_municipalities = set(lv2_df[lv2_exclude_mask]['municipality'].tolist())
    print(f"Lv2で除外対象（{LV2_EXCLUDE_KEYWORDS}を含む）: {len(lv2_exclude_municipalities)}")
    
    # 4. 最終結果: 条件1・2を満たし、かつLv1・Lv2で除外されていない自治体
    all_exclude = lv1_exclude_municipalities | lv2_exclude_municipalities
    result_municipalities = target_municipalities - all_exclude
    
    print(f"\n最終結果（条件1-3すべてを満たす）: {len(result_municipalities)}自治体")
    
    # 5. 結果を詳細情報と共に出力
    # 元のDBから詳細情報を取得
    conn = sqlite3.connect(DB_PATH)
    result_df = pd.read_sql_query(
        """
        SELECT name, area_type, regulation_type, cases_count
        FROM municipalities 
        WHERE name IN ({})
        """.format(','.join('?' * len(result_municipalities))),
        conn,
        params=list(result_municipalities)
    )
    conn.close()
    
    # Lv1, Lv2のカテゴリ情報を追加
    result_df = result_df.rename(columns={'name': 'municipality'})
    
    # Lv1のカテゴリを追加（該当自治体のみ）
    lv1_result = lv1_df[lv1_df['municipality'].isin(result_municipalities)][['municipality', 'category']].copy()
    lv1_result = lv1_result.rename(columns={'category': 'lv1_category'})
    lv1_result = lv1_result.drop_duplicates('municipality')
    
    # Lv2のカテゴリを追加（該当自治体のみ）
    lv2_result = lv2_df[lv2_df['municipality'].isin(result_municipalities)][['municipality', 'category']].copy()
    lv2_result = lv2_result.rename(columns={'category': 'lv2_category'})
    lv2_result = lv2_result.drop_duplicates('municipality')
    
    # マージ
    result_df = result_df.merge(lv1_result, on='municipality', how='left')
    result_df = result_df.merge(lv2_result, on='municipality', how='left')
    
    # CSVに出力
    result_df.to_csv(OUTPUT_PATH, index=False, encoding='utf-8-sig')
    print(f"\n結果を保存しました: {OUTPUT_PATH}")
    print("\n--- 結果一覧 ---")
    print(result_df.to_string(index=False))


if __name__ == '__main__':
    main()
