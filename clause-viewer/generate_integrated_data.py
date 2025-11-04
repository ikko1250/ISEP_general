#!/usr/bin/env python3
"""
統合データ生成スクリプト

data.json に分析結果(result_solar_rule_v1.1.csv)を統合し、
拡張版ビューア用の data-integrated.json を生成します。
"""

import json
import pandas as pd
from pathlib import Path

def load_data():
    """データファイルを読み込む"""
    # 分析結果CSVを読み込み
    csv_path = Path('/home/ubuntu/cur/isep/result_solar_rule_v1.1.csv')
    df_analysis = pd.read_csv(csv_path)
    
    # 既存のdata.jsonを読み込み
    json_path = Path('/home/ubuntu/cur/isep/clause-viewer/data.json')
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    return df_analysis, data

def create_municipality_info(df_analysis):
    """自治体ごとの分析情報を辞書化"""
    municipality_info = {}
    
    for _, row in df_analysis.iterrows():
        municipality_name = row['自治体']
        municipality_info[municipality_name] = {
            'ケース数': int(row['ケース数']),
            '規制タイプ': row['規制タイプ'],
            '区域類型': row['区域類型'],
            '禁止区域比率': float(row['禁止区域比率']),
            '厳格度_絶対': row['厳格度(絶対)'],
            '厳格度_相対': row['厳格度(相対)'],
            'プロセス重視度': row['プロセス重視度'],
            '厳格度スコア': float(row['厳格度スコア(正規化)']),
            '住民参加スコア': float(row['住民参加(正規化)']),
            '手続きスコア': float(row['手続き(正規化)'])
        }
    
    return municipality_info

def calculate_statistics(df_analysis):
    """全体統計情報を計算"""
    stats = {
        '規制タイプ分布': df_analysis['規制タイプ'].value_counts().to_dict(),
        '区域類型分布': df_analysis['区域類型'].value_counts().to_dict(),
        '厳格度_絶対分布': df_analysis['厳格度(絶対)'].value_counts().to_dict(),
        '厳格度_相対分布': df_analysis['厳格度(相対)'].value_counts().to_dict(),
        'プロセス重視度分布': df_analysis['プロセス重視度'].value_counts().to_dict(),
        '厳格度スコア統計': {
            '平均': float(df_analysis['厳格度スコア(正規化)'].mean()),
            '中央値': float(df_analysis['厳格度スコア(正規化)'].median()),
            '最小値': float(df_analysis['厳格度スコア(正規化)'].min()),
            '最大値': float(df_analysis['厳格度スコア(正規化)'].max()),
            '標準偏差': float(df_analysis['厳格度スコア(正規化)'].std())
        },
        '住民参加スコア統計': {
            '平均': float(df_analysis['住民参加(正規化)'].mean()),
            '中央値': float(df_analysis['住民参加(正規化)'].median()),
            '最小値': float(df_analysis['住民参加(正規化)'].min()),
            '最大値': float(df_analysis['住民参加(正規化)'].max()),
            '標準偏差': float(df_analysis['住民参加(正規化)'].std())
        },
        '手続きスコア統計': {
            '平均': float(df_analysis['手続き(正規化)'].mean()),
            '中央値': float(df_analysis['手続き(正規化)'].median()),
            '最小値': float(df_analysis['手続き(正規化)'].min()),
            '最大値': float(df_analysis['手続き(正規化)'].max()),
            '標準偏差': float(df_analysis['手続き(正規化)'].std())
        }
    }
    
    return stats

def integrate_data(df_analysis, data):
    """データを統合"""
    municipality_info = create_municipality_info(df_analysis)
    stats = calculate_statistics(df_analysis)
    
    # 統合データ構造を作成
    integrated_data = {
        'municipalities': sorted(data.get('municipalities', [])),
        'coding_types': data.get('coding_types', []),
        'municipality_info': municipality_info,
        'statistics': stats,
        'paragraphs': data['paragraphs']
    }
    
    # 分析メタデータを追加
    integrated_data['metadata'] = {
        'version': '1.1',
        'created_at': '2025-11-02',
        'total_municipalities': len(municipality_info),
        'total_paragraphs': len(data['paragraphs']),
        'analysis_fields': [
            '規制タイプ', '区域類型', '厳格度', 'プロセス重視度'
        ]
    }
    
    return integrated_data

def save_integrated_data(integrated_data):
    """統合データをJSONファイルとして保存"""
    output_path = Path('/home/ubuntu/cur/isep/clause-viewer/data-integrated.json')
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(integrated_data, f, ensure_ascii=False, indent=2)
    
    print(f"✓ 統合データを保存しました: {output_path}")
    print(f"  - 自治体数: {len(integrated_data['municipality_info'])}")
    print(f"  - 段落数: {len(integrated_data['paragraphs'])}")
    print(f"  - ファイルサイズ: {output_path.stat().st_size / 1024 / 1024:.2f} MB")

def main():
    print("=" * 60)
    print("統合データ生成スクリプト")
    print("=" * 60)
    
    # データ読み込み
    print("\n[1/3] データ読み込み中...")
    df_analysis, data = load_data()
    print(f"  - 分析結果: {len(df_analysis)} 自治体")
    print(f"  - 段落データ: {len(data['paragraphs'])} 段落")
    
    # データ統合
    print("\n[2/3] データ統合中...")
    integrated_data = integrate_data(df_analysis, data)
    
    # 統計情報表示
    print("\n統計情報:")
    print(f"  規制タイプ: {integrated_data['statistics']['規制タイプ分布']}")
    print(f"  区域類型: {integrated_data['statistics']['区域類型分布']}")
    
    # 保存
    print("\n[3/3] ファイル保存中...")
    save_integrated_data(integrated_data)
    
    print("\n" + "=" * 60)
    print("完了!")
    print("=" * 60)

if __name__ == '__main__':
    main()
