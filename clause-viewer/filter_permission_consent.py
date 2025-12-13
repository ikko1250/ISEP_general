#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CLAUSE_PERMISSION_CONSENT_OBLIGATION.csv から、
lv1ファイルとlv2ファイルで禁止/許可/同意に分類されていない自治体の条文を抽出する

除外するカテゴリ:
- 絶対禁止
- 条件付き禁止
- 許可制
- 禁止
- 許可
- 同意
"""

import csv
from pathlib import Path

# パス設定
BASE_DIR = Path(__file__).parent
INPUT_FILE = BASE_DIR / "CLAUSE_PERMISSION_CONSENT_OBLIGATION.csv"
LV1_FILE = BASE_DIR / "CLAUSE_ZONE_Lv1_classification_result.csv"
LV2_FILE = BASE_DIR / "CLAUSE_ZONE_Lv2_classification_result.csv"
OUTPUT_FILE = BASE_DIR / "CLAUSE_PERMISSION_CONSENT_FILTERED.csv"

# 除外するカテゴリ（部分一致で判定）
EXCLUDE_CATEGORIES = [
    "絶対禁止",
    "条件付き禁止",
    "許可制",
    "禁止",  # "1. 禁止 (Prohibition)" など
    "許可",  # "2. 許可 (Permission)" など  
    "同意",  # "3. 同意 (Consent)" など
]

def load_classified_municipalities(filepath):
    """分類ファイルから自治体と分類を読み込む"""
    municipalities = {}
    
    try:
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                muni = row.get('municipality', '').strip()
                category = row.get('category', '').strip()
                
                if muni:
                    if muni not in municipalities:
                        municipalities[muni] = []
                    municipalities[muni].append(category)
    except FileNotFoundError:
        print(f"警告: ファイルが見つかりません: {filepath}")
    
    return municipalities

def is_excluded_category(categories):
    """カテゴリが除外対象かどうかを判定"""
    for cat in categories:
        for exclude in EXCLUDE_CATEGORIES:
            if exclude in cat:
                return True
    return False

def main():
    print("=== フィルタリング処理 ===")
    print()
    
    # Lv1, Lv2の分類を読み込む
    print(f"Lv1ファイル読み込み: {LV1_FILE}")
    lv1_munis = load_classified_municipalities(LV1_FILE)
    print(f"  -> {len(lv1_munis)} 自治体")
    
    print(f"Lv2ファイル読み込み: {LV2_FILE}")
    lv2_munis = load_classified_municipalities(LV2_FILE)
    print(f"  -> {len(lv2_munis)} 自治体")
    print()
    
    # 除外する自治体を特定
    excluded_munis = set()
    
    for muni, categories in lv1_munis.items():
        if is_excluded_category(categories):
            excluded_munis.add(muni)
    
    for muni, categories in lv2_munis.items():
        if is_excluded_category(categories):
            excluded_munis.add(muni)
    
    print(f"除外対象のカテゴリ: {EXCLUDE_CATEGORIES}")
    print(f"除外自治体数: {len(excluded_munis)}")
    print()
    
    # 入力ファイルを読み込んでフィルタリング
    print(f"入力ファイル読み込み: {INPUT_FILE}")
    
    filtered_results = []
    total_count = 0
    excluded_count = 0
    
    with open(INPUT_FILE, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        
        for row in reader:
            total_count += 1
            muni = row.get('municipality', '').strip()
            
            if muni in excluded_munis:
                excluded_count += 1
            else:
                filtered_results.append(row)
    
    print(f"  -> 全{total_count}件のうち、{excluded_count}件を除外")
    print(f"  -> 残り: {len(filtered_results)} 件")
    print()
    
    # 結果を出力
    if filtered_results:
        with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(filtered_results)
        
        print(f"出力ファイル: {OUTPUT_FILE}")
        print()
        
        # サマリー
        filtered_munis = set(r['municipality'] for r in filtered_results)
        print(f"=== フィルタリング結果サマリー ===")
        print(f"対象自治体数: {len(filtered_munis)}")
        print()
        
        # 自治体一覧
        print("対象自治体一覧:")
        for muni in sorted(filtered_munis):
            count = sum(1 for r in filtered_results if r['municipality'] == muni)
            print(f"  - {muni}: {count}件")
        print()
        
        # サンプル表示
        print("=== 最初の5件 ===")
        for i, r in enumerate(filtered_results[:5], 1):
            print(f"\n--- {i}. {r['municipality']} ---")
            print(f"マッチ: [{r['matched_head']}] + [{r['matched_permission']}] + [{r['matched_obligation']}]")
            text = r['text']
            if len(text) > 200:
                text = text[:200] + "..."
            print(f"本文: {text}")
    else:
        print("フィルタリング後の結果が0件でした。")

if __name__ == "__main__":
    main()
