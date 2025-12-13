#!/usr/bin/env python3
"""
municipalities テーブルに '規制単位' カラムを追加し、
各分類ファイルからのデータを格納するスクリプト
"""

import sqlite3
import pandas as pd
from pathlib import Path

# ファイルパス
DB_PATH = Path('/home/ubuntu/cur/isep/clause-viewer/clause_data4.db')
LV1_PATH = Path('/home/ubuntu/cur/isep/clause-viewer/CLAUSE_ZONE_Lv1_classification_result.csv')
LV2_PATH = Path('/home/ubuntu/cur/isep/clause-viewer/CLAUSE_ZONE_Lv2_classification_result.csv')
NOTIFICATION_PATH = Path('/home/ubuntu/cur/isep/clause-viewer/notification_structure_analysis_result.csv')
UNCLASSIFIED_PATH = Path('/home/ubuntu/cur/isep/clause-viewer/unclassified_no_zone_municipalities.csv')


def main():
    # CSVファイルを読み込み
    print("CSVファイルを読み込み中...")
    lv1_df = pd.read_csv(LV1_PATH)
    lv2_df = pd.read_csv(LV2_PATH)
    notification_df = pd.read_csv(NOTIFICATION_PATH)
    unclassified_df = pd.read_csv(UNCLASSIFIED_PATH)
    
    # 各ファイルの自治体名と分類をマッピング
    regulation_map = {}
    
    # lv2ファイルの分類を追加
    print(f"lv2ファイル: {len(lv2_df)} 件")
    for _, row in lv2_df.iterrows():
        municipality = row['municipality']
        category = row['category']
        if municipality not in regulation_map:
            regulation_map[municipality] = set()
        # カテゴリから分類を抽出 (例: "1. 絶対禁止 (Absolute Prohibition)" -> "絶対禁止")
        if pd.notna(category):
            # 日本語部分を抽出
            cat_parts = category.split('.')
            if len(cat_parts) > 1:
                jp_part = cat_parts[1].split('(')[0].strip()
                regulation_map[municipality].add(f"Lv2:{jp_part}")
    
    # lv1ファイルから '禁止', '許可', '同意' 分類を抽出
    print(f"lv1ファイル: {len(lv1_df)} 件")
    for _, row in lv1_df.iterrows():
        municipality = row['municipality']
        category = row['category']
        conditions = row.get('conditions', '')
        
        if municipality not in regulation_map:
            regulation_map[municipality] = set()
        
        # 条件から禁止、許可、同意を抽出
        if pd.notna(conditions):
            cond_list = str(conditions).split(',')
            for cond in cond_list:
                cond = cond.strip()
                if cond in ['禁止', '許可', '同意']:
                    regulation_map[municipality].add(f"Lv1:{cond}")
    
    # 協議・届出ファイルの分類を追加
    print(f"協議・届出ファイル: {len(notification_df)} 件")
    notification_cols = ['協議', '変更届出', '事前届出', '完了届出', '着手届出', '撤去届出', '中止休止届出']
    for _, row in notification_df.iterrows():
        municipality = row['自治体名']
        if municipality not in regulation_map:
            regulation_map[municipality] = set()
        
        for col in notification_cols:
            if col in row and row[col] == 1:
                regulation_map[municipality].add(f"手続:{col}")
    
    # 区域設定無しファイルの自治体を記録
    print(f"区域設定無しファイル: {len(unclassified_df)} 件")
    unclassified_municipalities = set(unclassified_df['name'].tolist())
    
    # データベースに接続してカラムを追加・更新
    print("\nデータベースに接続中...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 既存のカラムを確認
    cursor.execute("PRAGMA table_info(municipalities)")
    columns = [col[1] for col in cursor.fetchall()]
    
    # 規制単位カラムが存在しない場合は追加
    if '規制単位' not in columns:
        print("'規制単位' カラムを追加中...")
        cursor.execute("ALTER TABLE municipalities ADD COLUMN 規制単位 TEXT")
        conn.commit()
        print("カラム追加完了")
    else:
        print("'規制単位' カラムは既に存在します")
    
    # 全自治体を取得
    cursor.execute("SELECT id, name FROM municipalities")
    municipalities = cursor.fetchall()
    print(f"\nデータベース内の自治体数: {len(municipalities)}")
    
    # 各自治体の規制単位を更新
    updated_count = 0
    for muni_id, muni_name in municipalities:
        # 区域設定無しの場合
        if muni_name in unclassified_municipalities:
            regulation_unit = '区域設定無し'
        # その他のファイルから分類がある場合
        elif muni_name in regulation_map and regulation_map[muni_name]:
            regulation_unit = ','.join(sorted(regulation_map[muni_name]))
        else:
            regulation_unit = None
        
        if regulation_unit:
            cursor.execute(
                "UPDATE municipalities SET 規制単位 = ? WHERE id = ?",
                (regulation_unit, muni_id)
            )
            updated_count += 1
    
    conn.commit()
    print(f"更新された自治体数: {updated_count}")
    
    # 結果を確認
    print("\n=== 更新結果サンプル ===")
    cursor.execute("SELECT name, 規制単位 FROM municipalities WHERE 規制単位 IS NOT NULL LIMIT 20")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]}")
    
    # 区域設定無しの自治体を確認
    print("\n=== 区域設定無しの自治体 ===")
    cursor.execute("SELECT name FROM municipalities WHERE 規制単位 = '区域設定無し'")
    no_zone = cursor.fetchall()
    print(f"  件数: {len(no_zone)}")
    if no_zone:
        for row in no_zone[:5]:
            print(f"  - {row[0]}")
    
    conn.close()
    print("\n処理完了")


if __name__ == '__main__':
    main()
