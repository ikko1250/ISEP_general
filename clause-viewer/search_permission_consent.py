#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
事業の許可・同意義務に関する条文を検索するスクリプト

検索条件:
( 市長 | 町長 | 村長 ) & ( 許可 | 同意 ) & ( 受けなければならない | 得なければならない )
"""

import sqlite3
import csv
from pathlib import Path

# データベースパス
DB_PATH = Path(__file__).parent / "clause_data4.db"
OUTPUT_PATH = Path(__file__).parent / "CLAUSE_PERMISSION_CONSENT_OBLIGATION.csv"

def search_clauses():
    """条件に合致する条文を検索"""
    
    # 検索条件
    head_terms = ["市長", "町長", "村長"]
    permission_terms = ["許可", "同意"]
    obligation_terms = ["受けなければならない", "得なければならない"]
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 全paragraphsを取得
    cursor.execute("""
        SELECT 
            p.id,
            m.name as municipality_name,
            p.h5,
            p.year,
            p.category,
            p.dan_number,
            p.text
        FROM paragraphs p
        JOIN municipalities m ON p.municipality_id = m.id
        ORDER BY m.name, p.h5, p.dan_number
    """)
    
    results = []
    
    for row in cursor.fetchall():
        para_id, muni_name, h5, year, category, dan_number, text = row
        
        if text is None:
            continue
        
        # 条件1: 市長 | 町長 | 村長
        has_head = any(term in text for term in head_terms)
        
        # 条件2: 許可 | 同意
        has_permission = any(term in text for term in permission_terms)
        
        # 条件3: 受けなければならない | 得なければならない
        has_obligation = any(term in text for term in obligation_terms)
        
        # 全条件を満たす場合
        if has_head and has_permission and has_obligation:
            # マッチした用語を特定
            matched_head = [t for t in head_terms if t in text]
            matched_permission = [t for t in permission_terms if t in text]
            matched_obligation = [t for t in obligation_terms if t in text]
            
            results.append({
                'paragraph_id': para_id,
                'municipality': muni_name,
                'h5': h5,
                'year': year,
                'category': category,
                'dan_number': dan_number,
                'matched_head': '|'.join(matched_head),
                'matched_permission': '|'.join(matched_permission),
                'matched_obligation': '|'.join(matched_obligation),
                'text': text
            })
    
    conn.close()
    
    return results

def main():
    print("検索条件:")
    print("  ( 市長 | 町長 | 村長 ) & ( 許可 | 同意 ) & ( 受けなければならない | 得なければならない )")
    print()
    
    results = search_clauses()
    
    print(f"検索結果: {len(results)} 件")
    print()
    
    # CSVに出力
    if results:
        with open(OUTPUT_PATH, 'w', newline='', encoding='utf-8-sig') as f:
            fieldnames = ['paragraph_id', 'municipality', 'h5', 'year', 'category', 
                          'dan_number', 'matched_head', 'matched_permission', 
                          'matched_obligation', 'text']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        
        print(f"結果を出力しました: {OUTPUT_PATH}")
        print()
        
        # 結果のサマリーを表示
        print("=== 検索結果サマリー ===")
        municipalities = set(r['municipality'] for r in results)
        print(f"対象自治体数: {len(municipalities)}")
        print()
        
        # サンプルを表示
        print("=== 最初の5件 ===")
        for i, r in enumerate(results[:5], 1):
            print(f"\n--- {i}. {r['municipality']} (h5={r['h5']}, 段落{r['dan_number']}) ---")
            print(f"マッチ: [{r['matched_head']}] + [{r['matched_permission']}] + [{r['matched_obligation']}]")
            # テキストは100文字まで表示
            text = r['text']
            if len(text) > 200:
                text = text[:200] + "..."
            print(f"本文: {text}")

if __name__ == "__main__":
    main()
