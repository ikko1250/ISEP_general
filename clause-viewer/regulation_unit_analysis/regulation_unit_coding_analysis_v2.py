#!/usr/bin/env python3
"""
規制単位ごとのコーディング分析スクリプト（パステルカラー・高視認性・大フォント版）

修正点:
1. 解像度統一: すべてのグラフの横幅を20インチに統一
2. フォントサイズ拡大: タイトル、ラベル、凡例、データ値を全体的に大きく調整
"""

import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')
import re
import os

# 日本語フォント設定
plt.rcParams['font.family'] = ['M+ 1C']

# データベース接続
DB_PATH = '/home/ubuntu/cur/isep/clause-viewer/clause_data4.db'
OUTPUT_DIR = '/home/ubuntu/cur/isep/clause-viewer/regulation_unit_analysis'
TEXT_CSV_PATH = '/home/ubuntu/cur/isep/texts/main4.3_2025-11-17.v.3.csv'

# 分析対象コーディング（罰則を2分類に分割）
TARGET_CODINGS = [
    '*Administrative_Guidance',
    '*Administrative_Disposition', 
    '*CLAUSE_PENALTY_NARROW',      # 狭義の罰則（罰金・過料）
    '*CLAUSE_PENALTY_OTHER'        # その他の罰則（公表等）
]

# === 共通パステルカラーパレット定義 ===
# coding_proportionで使用されている色(#FF6B6B, #4ECDC4, #45B7D1, #FFA07A)をベースに拡張
PASTEL_COLORS = {
    'Red': '#FF6B6B',      # Lv2 / 行政指導
    'Orange': '#FFA07A',   # Lv1不同意 / その他罰則
    'Green': '#4ECDC4',    # Lv1許可 / 行政処分
    'Blue': '#45B7D1',     # 抑制区域 / 狭義罰則
    'Purple': '#B39DDB',   # 区域なし許可制 (新規: パステルパープル)
    'Gray': '#BDC3C7',     # 届出のみ (新規: パステルグレー)
    'LightGray': '#D6D6D6' # 条文なし背景 (少し濃いめに調整)
}

# 狭義の罰則を判定するキーワード（基本）
NARROW_PENALTY_KEYWORDS = ['罰金', '過料', '科料', '懲役', '禁錮', '拘留']

def is_narrow_penalty_text(text):
    """狭義の罰則かどうかを判定（通報は首長→国・県のパターンのみ）"""
    if not text:
        return False
    
    # 基本キーワードのチェック
    if any(keyword in text for keyword in NARROW_PENALTY_KEYWORDS):
        return True
    
    # 通報のパターンチェック（首長が国・県・関係機関に通報）
    if '通報' in text:
        has_head = any(w in text for w in ['市長', '町長', '村長', '区長', '知事'])
        has_authority = any(w in text for w in ['県', '国', '知事', '経済産業', '関係機関'])
        if has_head and has_authority:
            return True
    
    return False

def categorize_regulation_unit(reg_unit):
    """規制単位を主要カテゴリに分類する"""
    if not reg_unit or reg_unit == '':
        return '未分類'
    
    # 優先順位に基づいて分類
    has_lv1 = 'Lv1:' in reg_unit
    has_lv2 = 'Lv2:' in reg_unit
    has_procedure = '手続:' in reg_unit
    has_no_zone = '区域設定無し' in reg_unit
    
    if has_no_zone:
        return '区域設定無し'
    
    # 複合型 (Lv1+Lv2、Lv1+手続など)
    if (has_lv1 and has_lv2) or (has_lv1 and has_procedure) or (has_lv2 and has_procedure):
        return '複合型(Lv1+Lv2/手続)'
    
    # Lv2のみ
    if has_lv2:
        if '絶対禁止' in reg_unit:
            return 'Lv2:絶対禁止'
        elif '条件付き禁止' in reg_unit:
            return 'Lv2:条件付き禁止'
        elif '許可制' in reg_unit:
            return 'Lv2:許可制'
        elif '区域指定のみ' in reg_unit:
            return 'Lv2:区域指定のみ'
        elif '区域外規定のみ' in reg_unit:
            return 'Lv2:区域外規定のみ'
        else:
            return 'Lv2:その他'
    
    # Lv1のみ
    if has_lv1:
        if '許可' in reg_unit and '禁止' in reg_unit:
            return 'Lv1:禁止+許可'
        elif '同意' in reg_unit and '禁止' in reg_unit:
            return 'Lv1:同意+禁止'
        elif '同意' in reg_unit and '許可' in reg_unit:
            return 'Lv1:同意+許可'
        elif '許可' in reg_unit:
            return 'Lv1:許可'
        elif '同意' in reg_unit:
            return 'Lv1:同意'
        elif '禁止' in reg_unit:
            return 'Lv1:禁止'
        else:
            return 'Lv1:その他'
    
    # 手続のみ
    if has_procedure:
        return '手続のみ(届出・協議)'
    
    return 'その他'

def get_regulation_unit_stats(conn):
    """規制単位ごとのコーディング統計を取得（罰則を2分類）"""
    
    # 罰則コーディングIDを取得
    cursor = conn.execute(
        "SELECT id FROM coding_types WHERE code = ?", ('*CLAUSE_PENALTY',)
    )
    result = cursor.fetchone()
    penalty_coding_id = result[0] if result else None
    
    # 他のコーディングIDを取得
    coding_ids = {}
    for code in ['*Administrative_Guidance', '*Administrative_Disposition']:
        cursor = conn.execute(
            "SELECT id FROM coding_types WHERE code = ?", (code,)
        )
        result = cursor.fetchone()
        if result:
            coding_ids[code] = result[0]
    
    # 規制単位ごとの統計を取得
    results = []
    
    # 全ての規制単位を取得（area_type, regulation_typeも含める）
    cursor = conn.execute("""
        SELECT DISTINCT m.規制単位, m.id, m.name, m.area_type, m.regulation_type
        FROM municipalities m
        WHERE m.規制単位 IS NOT NULL AND m.規制単位 != ''
    """)
    municipalities = cursor.fetchall()
    
    # 規制単位ごとにグループ化
    regulation_units = {}
    for reg_unit, muni_id, muni_name, area_type, regulation_type in municipalities:
        if reg_unit not in regulation_units:
            regulation_units[reg_unit] = []
        regulation_units[reg_unit].append((muni_id, muni_name, area_type, regulation_type))
    
    for reg_unit, munis in regulation_units.items():
        muni_ids = [m[0] for m in munis]
        muni_count = len(muni_ids)
        # area_typeの集計（最も多いものを使用）
        area_types = [m[2] for m in munis if m[2]]
        dominant_area_type = max(set(area_types), key=area_types.count) if area_types else ''
        # regulation_typeの集計
        regulation_types = [m[3] for m in munis if m[3]]
        dominant_regulation_type = max(set(regulation_types), key=regulation_types.count) if regulation_types else ''
        
        # 条文総数を取得
        placeholders = ','.join('?' * len(muni_ids))
        cursor = conn.execute(f"""
            SELECT COUNT(*) FROM paragraphs
            WHERE municipality_id IN ({placeholders})
        """, muni_ids)
        total_paragraphs = cursor.fetchone()[0]
        
        if total_paragraphs == 0:
            continue
        
        # 行政指導・行政処分の条文数を取得
        coding_counts = {}
        for code, coding_id in coding_ids.items():
            cursor = conn.execute(f"""
                SELECT COUNT(DISTINCT p.id) 
                FROM paragraphs p
                JOIN paragraph_codings pc ON p.id = pc.paragraph_id
                WHERE p.municipality_id IN ({placeholders})
                AND pc.coding_type_id = ?
            """, muni_ids + [coding_id])
            coding_counts[code] = cursor.fetchone()[0]
        
        # 罰則を2分類（狭義：罰金・過料等 / その他：公表等）
        if penalty_coding_id:
            # 罰則条文のテキストを取得
            cursor = conn.execute(f"""
                SELECT DISTINCT p.id, p.text 
                FROM paragraphs p
                JOIN paragraph_codings pc ON p.id = pc.paragraph_id
                WHERE p.municipality_id IN ({placeholders})
                AND pc.coding_type_id = ?
            """, muni_ids + [penalty_coding_id])
            penalty_paragraphs = cursor.fetchall()
            
            narrow_count = 0
            other_count = 0
            for p_id, text in penalty_paragraphs:
                if is_narrow_penalty_text(text):
                    narrow_count += 1
                else:
                    other_count += 1
            
            coding_counts['*CLAUSE_PENALTY_NARROW'] = narrow_count
            coding_counts['*CLAUSE_PENALTY_OTHER'] = other_count
        else:
            coding_counts['*CLAUSE_PENALTY_NARROW'] = 0
            coding_counts['*CLAUSE_PENALTY_OTHER'] = 0
        
        results.append({
            '規制単位': reg_unit,
            'area_type': dominant_area_type,
            'regulation_type': dominant_regulation_type,
            '自治体数': muni_count,
            '条文総数': total_paragraphs,
            **coding_counts
        })
    
    return pd.DataFrame(results)

def create_stacked_bar_chart(df, output_path):
    """帯グラフ（100%積み上げ棒グラフ）を作成"""
    
    # サンプル数でソート（降順）
    df_sorted = df.sort_values('条文総数', ascending=False)
    
    # 割合を計算
    df_plot = pd.DataFrame()
    df_plot['規制単位'] = df_sorted['規制単位']
    df_plot['自治体数'] = df_sorted['自治体数']
    df_plot['条文総数'] = df_sorted['条文総数']
    
    for code in TARGET_CODINGS:
        df_plot[f'{code}_割合'] = (df_sorted[code] / df_sorted['条文総数'] * 100).round(2)
        df_plot[f'{code}_件数'] = df_sorted[code]
    
    # 「その他」の割合を計算
    target_sum = sum(df_plot[f'{code}_割合'] for code in TARGET_CODINGS)
    df_plot['その他_割合'] = 100 - target_sum
    
    # グラフ作成 - 横幅を20に拡大
    fig, ax = plt.subplots(figsize=(20, 14))
    
    # ラベルの準備
    labels = [f"{r}\n(n={n}, 条文={t})" 
              for r, n, t in zip(df_plot['規制単位'], df_plot['自治体数'], df_plot['条文総数'])]
    
    # 色の設定
    colors = {
        '*Administrative_Guidance': PASTEL_COLORS['Red'],
        '*Administrative_Disposition': PASTEL_COLORS['Green'],
        '*CLAUSE_PENALTY_NARROW': PASTEL_COLORS['Blue'],
        '*CLAUSE_PENALTY_OTHER': PASTEL_COLORS['Orange'],
        'その他': '#E8E8E8'
    }
    
    y_pos = range(len(labels))
    
    # 積み上げ棒グラフを描画
    left = [0] * len(labels)
    
    for code in TARGET_CODINGS:
        widths = df_plot[f'{code}_割合'].values
        short_name = code.replace('*', '').replace('Administrative_', 'Admin_')
        bars = ax.barh(y_pos, widths, left=left, label=short_name, color=colors[code], height=0.7)
        
        # 値のラベルを追加（5%以上の場合のみ）
        for i, (width, l) in enumerate(zip(widths, left)):
            if width >= 5:
                # フォントサイズ拡大: 8 -> 14
                ax.text(l + width/2, i, f'{width:.1f}%', 
                        ha='center', va='center', fontsize=14, fontweight='bold', color='black')
        
        left = [l + w for l, w in zip(left, widths)]
    
    # その他を追加
    widths = df_plot['その他_割合'].values
    ax.barh(y_pos, widths, left=left, label='その他', color=colors['その他'], height=0.7)
    
    ax.set_yticks(y_pos)
    # 軸ラベルフォント拡大: 9 -> 16
    ax.set_yticklabels(labels, fontsize=16)
    # X軸ラベル拡大: 12 -> 18
    ax.set_xlabel('条文に占める割合 (%)', fontsize=18)
    # タイトル拡大: 14 -> 24
    ax.set_title('規制単位ごとのコーディング分布\n(行政指導・行政処分・罰則)', fontsize=24, fontweight='bold')
    ax.set_xlim(0, 100)
    # 凡例拡大: 10 -> 16
    ax.legend(loc='lower right', fontsize=16)
    ax.grid(axis='x', alpha=0.3)
    
    # 目盛りサイズ調整
    ax.tick_params(axis='x', labelsize=16)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"\nグラフを保存しました: {output_path}")

def get_categorized_stats(df):
    """規制単位をカテゴリにグループ化した統計を取得"""
    df['カテゴリ'] = df['規制単位'].apply(categorize_regulation_unit)
    
    grouped = df.groupby('カテゴリ').agg({
        '自治体数': 'sum',
        '条文総数': 'sum',
        '*Administrative_Guidance': 'sum',
        '*Administrative_Disposition': 'sum',
        '*CLAUSE_PENALTY_NARROW': 'sum',
        '*CLAUSE_PENALTY_OTHER': 'sum'
    }).reset_index()
    
    return grouped

def create_categorized_chart(df, output_path):
    """カテゴリ別の帯グラフを作成"""
    df_sorted = df.sort_values('条文総数', ascending=False)
    
    df_plot = pd.DataFrame()
    df_plot['カテゴリ'] = df_sorted['カテゴリ']
    df_plot['自治体数'] = df_sorted['自治体数']
    df_plot['条文総数'] = df_sorted['条文総数']
    
    for code in TARGET_CODINGS:
        df_plot[f'{code}_割合'] = (df_sorted[code] / df_sorted['条文総数'] * 100).round(2)
        df_plot[f'{code}_件数'] = df_sorted[code]
    
    target_sum = sum(df_plot[f'{code}_割合'] for code in TARGET_CODINGS)
    df_plot['その他_割合'] = 100 - target_sum
    
    # グラフ作成 - 横幅を20に拡大
    fig, ax = plt.subplots(figsize=(20, 12))
    
    labels = [f"{r}\n(自治体数={n}, 条文数={t})" 
              for r, n, t in zip(df_plot['カテゴリ'], df_plot['自治体数'], df_plot['条文総数'])]
    
    # 色の設定
    colors = {
        '*Administrative_Guidance': PASTEL_COLORS['Red'],
        '*Administrative_Disposition': PASTEL_COLORS['Green'],
        '*CLAUSE_PENALTY_NARROW': PASTEL_COLORS['Blue'],
        '*CLAUSE_PENALTY_OTHER': PASTEL_COLORS['Orange'],
        'その他': '#E8E8E8'
    }
    
    y_pos = range(len(labels))
    
    left = [0] * len(labels)
    
    for code in TARGET_CODINGS:
        widths = df_plot[f'{code}_割合'].values
        display_names = {
            '*Administrative_Guidance': '行政指導',
            '*Administrative_Disposition': '行政処分',
            '*CLAUSE_PENALTY_NARROW': '狭義罰則(罰金・過料)',
            '*CLAUSE_PENALTY_OTHER': 'その他罰則(公表等)'
        }
        short_name = display_names.get(code, code)
        bars = ax.barh(y_pos, widths, left=left, label=short_name, color=colors[code], height=0.7)
        
        for i, (width, l) in enumerate(zip(widths, left)):
            if width >= 3:
                # フォントサイズ拡大: 9 -> 14
                ax.text(l + width/2, i, f'{width:.1f}%', 
                        ha='center', va='center', fontsize=14, fontweight='bold', color='black')
        
        left = [l + w for l, w in zip(left, widths)]
    
    widths = df_plot['その他_割合'].values
    ax.barh(y_pos, widths, left=left, label='その他の条文', color=colors['その他'], height=0.7)
    
    ax.set_yticks(y_pos)
    # 軸ラベルフォント拡大: 10 -> 16
    ax.set_yticklabels(labels, fontsize=16)
    # X軸ラベル拡大: 12 -> 18
    ax.set_xlabel('条文に占める割合 (%)', fontsize=18)
    # タイトル拡大: 14 -> 24
    ax.set_title('規制単位カテゴリ別のコーディング分布\n(行政指導・行政処分・罰則)', fontsize=24, fontweight='bold')
    ax.set_xlim(0, 100)
    # 凡例拡大: 10 -> 16
    ax.legend(loc='lower right', fontsize=16, bbox_to_anchor=(1.0, 0.0))
    ax.grid(axis='x', alpha=0.3)
    
    # 目盛りサイズ調整
    ax.tick_params(axis='x', labelsize=16)
    
    for x in [0, 25, 50, 75, 100]:
        ax.axvline(x=x, color='gray', linestyle='--', alpha=0.3, linewidth=0.5)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"\nカテゴリ別グラフを保存しました: {output_path}")

def categorize_7level(row):
    """規制単位、area_type、regulation_typeを考慮して8段階に分類する
    
    カテゴリ:
    - 0_Lv1,2複合型: Lv2(条件付き禁止/絶対禁止) + Lv1(許可/同意/禁止)、またはLv2 + 手続
    - 1a_Lv2(区域・許可制優位)
    - 1b_Lv2(区域・届出制優位)
    - 2_Lv1不同意(禁止)
    - 3_Lv1許可or同意
    - 5_抑制区域+届出
    - 6_区域なし+許可制
    - 7_届出・協議のみ
    """
    reg_unit = row['規制単位'] if isinstance(row, dict) or hasattr(row, '__getitem__') else row
    area_type = row.get('area_type', '') if isinstance(row, dict) or hasattr(row, 'get') else ''
    regulation_type = row.get('regulation_type', '') if isinstance(row, dict) or hasattr(row, 'get') else ''
    
    if not reg_unit or reg_unit == '':
        if area_type in ['抑制地区制', '禁止地区制', '2層構造(抑制+禁止)']:
            return '5_抑制区域+届出'
        if regulation_type == '許可制優位':
            return '6_区域なし+許可制'
        return '7_届出・協議のみ'
    
    has_lv1 = 'Lv1:' in reg_unit
    has_lv2 = 'Lv2:' in reg_unit
    has_procedure = '手続:' in reg_unit
    
    # Lv1,2複合型の判定（最優先）
    # 条件1: Lv2(条件付き禁止または絶対禁止) + Lv1(許可・同意・禁止のいずれか)
    # 条件2: Lv2 + 手続（Lv2と届出・協議等の手続が併用されている場合）
    if has_lv1 and has_lv2:
        has_lv2_prohibition = '条件付き禁止' in reg_unit or '絶対禁止' in reg_unit
        has_lv1_regulation = '許可' in reg_unit or '同意' in reg_unit or '禁止' in reg_unit
        if has_lv2_prohibition and has_lv1_regulation:
            return '0_Lv1,2複合型'
    
    # Lv2 + 手続の組み合わせも複合型として分類
    if has_lv2 and has_procedure:
        return '0_Lv1,2複合型'
    
    if has_lv2:
        # Lv2を許可制優位/届出制優位で分割
        if regulation_type == '許可制優位':
            return '1a_Lv2(区域・許可制優位)'
        else:
            return '1b_Lv2(区域・届出制優位)'
    
    if has_lv1:
        if has_procedure:
            return '5_抑制区域+届出'
        if '禁止' in reg_unit:
            return '2_Lv1不同意(禁止)'
        if '許可' in reg_unit or '同意' in reg_unit:
            return '3_Lv1許可or同意'
        return '3_Lv1許可or同意'
    
    if has_procedure:
        if area_type in ['抑制地区制', '禁止地区制', '2層構造(抑制+禁止)']:
            return '5_抑制区域+届出'
    
    if regulation_type == '許可制優位':
        return '6_区域なし+許可制'
    return '7_届出・協議のみ'

def get_7level_stats(conn):
    """規制単位を7段階にグループ化した統計を取得（自治体レベルで分類）"""
    # 罰則コーディングIDを取得
    cursor = conn.execute("SELECT id FROM coding_types WHERE code = ?", ('*CLAUSE_PENALTY',))
    result = cursor.fetchone()
    penalty_coding_id = result[0] if result else None
    
    coding_ids = {}
    for code in ['*Administrative_Guidance', '*Administrative_Disposition']:
        cursor = conn.execute("SELECT id FROM coding_types WHERE code = ?", (code,))
        result = cursor.fetchone()
        if result:
            coding_ids[code] = result[0]
    
    cursor = conn.execute("""
        SELECT m.id, m.name, m.規制単位, m.area_type, m.regulation_type
        FROM municipalities m
    """)
    municipalities = cursor.fetchall()
    
    category_stats = {}
    
    for muni_id, muni_name, reg_unit, area_type, regulation_type in municipalities:
        row = {'規制単位': reg_unit or '', 'area_type': area_type or '', 'regulation_type': regulation_type or ''}
        category = categorize_7level(row)
        
        if category not in category_stats:
            category_stats[category] = {
                '7段階': category,
                '自治体数': 0,
                '条文総数': 0,
                '*Administrative_Guidance': 0,
                '*Administrative_Disposition': 0,
                '*CLAUSE_PENALTY_NARROW': 0,
                '*CLAUSE_PENALTY_OTHER': 0
            }
        
        category_stats[category]['自治体数'] += 1
        
        cursor = conn.execute("SELECT COUNT(*) FROM paragraphs WHERE municipality_id = ?", (muni_id,))
        para_count = cursor.fetchone()[0]
        category_stats[category]['条文総数'] += para_count
        
        for code, coding_id in coding_ids.items():
            cursor = conn.execute("""
                SELECT COUNT(DISTINCT p.id) FROM paragraphs p
                JOIN paragraph_codings pc ON p.id = pc.paragraph_id
                WHERE p.municipality_id = ? AND pc.coding_type_id = ?
            """, (muni_id, coding_id))
            category_stats[category][code] += cursor.fetchone()[0]
        
        if penalty_coding_id:
            cursor = conn.execute("""
                SELECT p.text FROM paragraphs p
                JOIN paragraph_codings pc ON p.id = pc.paragraph_id
                WHERE p.municipality_id = ? AND pc.coding_type_id = ?
            """, (muni_id, penalty_coding_id))
            for (text,) in cursor.fetchall():
                if is_narrow_penalty_text(text):
                    category_stats[category]['*CLAUSE_PENALTY_NARROW'] += 1
                else:
                    category_stats[category]['*CLAUSE_PENALTY_OTHER'] += 1
    
    df = pd.DataFrame(list(category_stats.values()))
    df = df.sort_values('7段階')
    return df

def create_7level_chart(df, output_path):
    """7段階比較の帯グラフを作成"""
    df_sorted = df.sort_values('7段階')
    
    df_plot = pd.DataFrame()
    df_plot['7段階'] = df_sorted['7段階']
    df_plot['自治体数'] = df_sorted['自治体数']
    df_plot['条文総数'] = df_sorted['条文総数']
    
    for code in TARGET_CODINGS:
        df_plot[f'{code}_割合'] = (df_sorted[code] / df_sorted['条文総数'] * 100).round(2)
        df_plot[f'{code}_件数'] = df_sorted[code]
    
    target_sum = sum(df_plot[f'{code}_割合'] for code in TARGET_CODINGS)
    df_plot['その他_割合'] = 100 - target_sum
    
    # グラフ作成 - 横幅を20、高さを12に拡大（7段階になるため）
    fig, ax = plt.subplots(figsize=(20, 12))
    
    label_names = {
        '0_Lv1,2複合型': '禁止・抑制複合',
        '1a_Lv2(区域・許可制優位)': '禁止区域(許可)',
        '1b_Lv2(区域・届出制優位)': '禁止区域(届出)',
        '2_Lv1不同意(禁止)': '抑制区域(不同意)',
        '3_Lv1許可or同意': '抑制区域(許可)',
        '5_抑制区域+届出': '抑制区域(届出)',
        '6_区域なし+許可制': '区域なし(許可)',
        '7_届出・協議のみ': '区域なし(届出)'
    }
    labels = [f"{label_names.get(r, r)}\n(自治体数={n}, 条文数={t})" 
              for r, n, t in zip(df_plot['7段階'], df_plot['自治体数'], df_plot['条文総数'])]
    
    colors = {
        '*Administrative_Guidance': PASTEL_COLORS['Red'],
        '*Administrative_Disposition': PASTEL_COLORS['Green'],
        '*CLAUSE_PENALTY_NARROW': PASTEL_COLORS['Blue'],
        '*CLAUSE_PENALTY_OTHER': PASTEL_COLORS['Orange'],
        'その他': '#E8E8E8'
    }
    
    y_pos = range(len(labels))
    
    left = [0] * len(labels)
    
    for code in TARGET_CODINGS:
        widths = df_plot[f'{code}_割合'].values
        display_names = {
            '*Administrative_Guidance': '行政指導',
            '*Administrative_Disposition': '行政処分',
            '*CLAUSE_PENALTY_NARROW': '狭義罰則(罰金・過料)',
            '*CLAUSE_PENALTY_OTHER': 'その他罰則(公表等)'
        }
        short_name = display_names.get(code, code)
        bars = ax.barh(y_pos, widths, left=left, label=short_name, color=colors[code], height=0.6)
        
        for i, (width, l) in enumerate(zip(widths, left)):
            if width >= 2:
                # フォントサイズ拡大: 10 -> 14
                ax.text(l + width/2, i, f'{width:.1f}%', 
                        ha='center', va='center', fontsize=14, fontweight='bold', color='black')
        
        left = [l + w for l, w in zip(left, widths)]
    
    widths = df_plot['その他_割合'].values
    ax.barh(y_pos, widths, left=left, label='その他の条文', color=colors['その他'], height=0.6)
    
    ax.set_yticks(y_pos)
    # 軸ラベルフォント拡大: 11 -> 16
    ax.set_yticklabels(labels, fontsize=16)
    # X軸ラベル拡大: 12 -> 18
    ax.set_xlabel('条文に占める割合 (%)', fontsize=18)
    # タイトル拡大: 14 -> 24
    ax.set_title('規制強度7段階別のコーディング分布\n(行政指導・行政処分・罰則)', fontsize=24, fontweight='bold')
    ax.set_xlim(0, 100)
    # 凡例拡大: 10 -> 16
    ax.legend(loc='lower right', fontsize=16, bbox_to_anchor=(1.0, 0.0))
    ax.grid(axis='x', alpha=0.3)
    
    # 目盛りサイズ調整
    ax.tick_params(axis='x', labelsize=16)
    
    for x in [0, 25, 50, 75, 100]:
        ax.axvline(x=x, color='gray', linestyle='--', alpha=0.3, linewidth=0.5)
    
    ax.axhline(y=0.5, color='#333', linestyle='-', alpha=0.1, linewidth=10)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"\n7段階比較グラフを保存しました: {output_path}")

def create_7level_municipality_distribution_chart(df_7level, output_path):
    """7段階カテゴリの自治体数分布を帯グラフで作成（カラーパレット適用版）"""
    
    label_names = {
        '0_Lv1,2複合型': '禁止・抑制\n複合',
        '1a_Lv2(区域・許可制優位)': '禁止区域\n(許可)',
        '1b_Lv2(区域・届出制優位)': '禁止区域\n(届出)',
        '2_Lv1不同意(禁止)': '抑制区域\n(不同意)',
        '3_Lv1許可or同意': '抑制区域\n(許可)',
        '5_抑制区域+届出': '抑制区域\n(届出)',
        '6_区域なし+許可制': '区域なし\n(許可)',
        '7_届出・協議のみ': '区域なし\n(届出)'
    }
    
    # パステルカラーパレットの適用（8色に拡張）
    colors = [
        '#E91E63',               # Lv1,2複合型（ピンク系で目立つ色）
        PASTEL_COLORS['Red'],    # Lv2許可制優位
        '#FF9999',               # Lv2届出制優位（Redより薄め）
        PASTEL_COLORS['Orange'], # Lv1不同意
        PASTEL_COLORS['Green'],  # Lv1許可
        PASTEL_COLORS['Blue'],   # 抑制区域
        PASTEL_COLORS['Purple'], # 区域なし許可制
        PASTEL_COLORS['Gray']    # 届出のみ
    ]
    
    df_sorted = df_7level.sort_values('7段階')
    categories = df_sorted['7段階'].tolist()
    muni_counts = df_sorted['自治体数'].tolist()
    total_munis = sum(muni_counts)
    
    percentages = [(c / total_munis * 100) for c in muni_counts]
    
    # グラフ作成 - 横幅を20に拡大 (高さは調整)
    fig, ax = plt.subplots(figsize=(20, 5.5))
    
    left = 0
    for i, (cat, count, pct) in enumerate(zip(categories, muni_counts, percentages)):
        # 枠線(edgecolor)を追加して区分けをはっきりさせる
        bar = ax.barh(0, pct, left=left, color=colors[i], height=0.6,
                      edgecolor='white', linewidth=1.5,
                      label=f"{label_names.get(cat, cat)}: {count}自治体 ({pct:.1f}%)")
        
        # ラベル追加: 文字色を黒・太字にして視認性向上
        if pct >= 5:
            # フォントサイズ拡大: 11 -> 16
            ax.text(left + pct/2, 0, f"{count}\n({pct:.1f}%)", 
                    ha='center', va='center', fontsize=16, fontweight='bold', color='black')
        
        left += pct
    
    ax.set_xlim(0, 100)
    ax.set_ylim(-0.5, 0.5)
    ax.set_yticks([])
    # X軸ラベル拡大: 12 -> 18
    ax.set_xlabel('自治体数の割合 (%)', fontsize=18)
    # タイトル拡大: 14 -> 24
    ax.set_title(f'規制レベル別 自治体数分布（総計: {total_munis}自治体）', fontsize=24, fontweight='bold')
    # 凡例拡大: 14 -> 18
    ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.35), ncol=4, fontsize=18)
    
    # 目盛りサイズ調整
    ax.tick_params(axis='x', labelsize=16)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"\n自治体数分布グラフを保存しました: {output_path}")

def get_municipality_level_stats(conn):
    """自治体レベルでのコーディング統計を取得"""
    cursor = conn.execute("SELECT id FROM coding_types WHERE code = ?", ('*CLAUSE_PENALTY',))
    result = cursor.fetchone()
    penalty_coding_id = result[0] if result else None
    
    coding_ids = {}
    for code in ['*Administrative_Guidance', '*Administrative_Disposition']:
        cursor = conn.execute("SELECT id FROM coding_types WHERE code = ?", (code,))
        result = cursor.fetchone()
        if result:
            coding_ids[code] = result[0]
    
    cursor = conn.execute("""
        SELECT m.id, m.name, m.規制単位, m.area_type, m.regulation_type
        FROM municipalities m
    """)
    municipalities = cursor.fetchall()
    
    results = []
    for muni_id, muni_name, reg_unit, area_type, regulation_type in municipalities:
        row = {'規制単位': reg_unit or '', 'area_type': area_type or '', 'regulation_type': regulation_type or ''}
        category = categorize_7level(row)
        
        coding_exists = {}
        for code, coding_id in coding_ids.items():
            cursor = conn.execute("""
                SELECT COUNT(*) FROM paragraphs p
                JOIN paragraph_codings pc ON p.id = pc.paragraph_id
                WHERE p.municipality_id = ? AND pc.coding_type_id = ?
            """, (muni_id, coding_id))
            count = cursor.fetchone()[0]
            coding_exists[f'{code}_有'] = 1 if count > 0 else 0
        
        if penalty_coding_id:
            cursor = conn.execute("""
                SELECT p.text FROM paragraphs p
                JOIN paragraph_codings pc ON p.id = pc.paragraph_id
                WHERE p.municipality_id = ? AND pc.coding_type_id = ?
            """, (muni_id, penalty_coding_id))
            penalty_texts = cursor.fetchall()
            
            has_narrow = 0
            has_other = 0
            for (text,) in penalty_texts:
                if is_narrow_penalty_text(text):
                    has_narrow = 1
                else:
                    has_other = 1
            
            coding_exists['*CLAUSE_PENALTY_NARROW_有'] = has_narrow
            coding_exists['*CLAUSE_PENALTY_OTHER_有'] = has_other
        else:
            coding_exists['*CLAUSE_PENALTY_NARROW_有'] = 0
            coding_exists['*CLAUSE_PENALTY_OTHER_有'] = 0
        
        results.append({
            '自治体名': muni_name,
            '7段階': category,
            **coding_exists
        })
    
    return pd.DataFrame(results)

def create_municipality_proportion_chart(df, output_path):
    """7段階カテゴリごとの自治体数グラフを作成（実数表示版）
    
    変更点:
    - 割合表示から実数表示に変更
    - カテゴリ内の全自治体数をグレーで表示（背景）
    - 該当条件を満たす自治体数を色付きで重ねて表示
    """
    
    summary_data = []
    for category in sorted(df['7段階'].unique()):
        cat_df = df[df['7段階'] == category]
        total = len(cat_df)
        
        row = {'7段階': category, '自治体数': total}
        for code in TARGET_CODINGS:
            col = f'{code}_有'
            has_count = cat_df[col].sum()
            row[f'{code}_有数'] = has_count
            row[f'{code}_有率'] = (has_count / total * 100) if total > 0 else 0
        
        summary_data.append(row)
    
    df_summary = pd.DataFrame(summary_data)
    
    # グラフ作成 - 横幅を20に拡大、高さを14に調整
    fig, axes = plt.subplots(2, 2, figsize=(20, 14))
    axes = axes.flatten()
    
    label_names = {
        '0_Lv1,2複合型': '禁止・抑制\n複合',
        '1a_Lv2(区域・許可制優位)': '禁止区域\n(許可)',
        '1b_Lv2(区域・届出制優位)': '禁止区域\n(届出)',
        '2_Lv1不同意(禁止)': '抑制区域\n(不同意)',
        '3_Lv1許可or同意': '抑制区域\n(許可)',
        '5_抑制区域+届出': '抑制区域\n(届出)',
        '6_区域なし+許可制': '区域なし\n(許可)',
        '7_届出・協議のみ': '区域なし\n(届出)'
    }
    
    coding_names = {
        '*Administrative_Guidance': '行政指導',
        '*Administrative_Disposition': '行政処分',
        '*CLAUSE_PENALTY_NARROW': '狭義の罰則（罰金・過料）',
        '*CLAUSE_PENALTY_OTHER': 'その他罰則（公表等）'
    }
    
    # パステルカラーパレットの適用（統一感）
    colors = {
        '*Administrative_Guidance': PASTEL_COLORS['Red'],
        '*Administrative_Disposition': PASTEL_COLORS['Green'],
        '*CLAUSE_PENALTY_NARROW': PASTEL_COLORS['Blue'],
        '*CLAUSE_PENALTY_OTHER': PASTEL_COLORS['Orange']
    }
    
    for idx, code in enumerate(TARGET_CODINGS):
        ax = axes[idx]
        
        categories = df_summary['7段階'].tolist()
        labels = [label_names.get(c, c) for c in categories]
        totals = df_summary['自治体数'].tolist()
        has_counts = df_summary[f'{code}_有数'].tolist()
        has_rates = df_summary[f'{code}_有率'].tolist()
        
        x = range(len(labels))
        
        # Y軸の最大値を動的に設定（全カテゴリの最大自治体数に基づく）
        max_total = max(totals) if totals else 1
        y_limit = int(max_total * 1.15)  # 15%余裕を持たせる
        
        # 背景: カテゴリ内の全自治体数（グレー）
        bars_total = ax.bar(x, totals, color=PASTEL_COLORS['LightGray'], label='全自治体', alpha=0.6)
        
        # 前面: 該当条件を満たす自治体数（色付き）
        bars_has = ax.bar(x, has_counts, color=colors[code], label='条文あり', alpha=1.0)
        
        # ラベルを追加: 該当数/総数 と割合を表示
        for i, (count, total, rate) in enumerate(zip(has_counts, totals, has_rates)):
            # バーの上部に表示
            label_y = total + (y_limit * 0.02)
            ax.text(i, label_y, f'{count}/{total}\n({rate:.1f}%)', 
                    ha='center', va='bottom', fontsize=12, fontweight='bold', color='black')
        
        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=14)
        ax.set_ylabel('自治体数', fontsize=18)
        ax.set_title(f'{coding_names[code]}条文を持つ自治体数', fontsize=20, fontweight='bold')
        ax.set_ylim(0, y_limit)
        
        # 凡例: 全自治体（グレー）と条文あり（色）を表示
        ax.legend([bars_total, bars_has], ['全自治体', '条文あり'], loc='upper right', fontsize=14)
        ax.grid(axis='y', alpha=0.3)
        
        ax.tick_params(axis='y', labelsize=14)
    
    plt.suptitle('規制レベル別 - コーディング条文を持つ自治体数', 
                 fontsize=28, fontweight='bold', y=0.95)
    plt.tight_layout(h_pad=5.0, w_pad=3.0, rect=[0, 0.03, 1, 0.95])
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"\n自治体数グラフを保存しました: {output_path}")
    
    return df_summary



def is_clean_text(text):
    """テキストが条例本文（制定時）として適切か判定する"""
    if not isinstance(text, str) or not text:
        return False
    text = text.strip()
    if text.startswith('○'): return False
    if text.startswith('(目的)'): return True
    if text.startswith('(趣旨)'): return True
    if text.startswith('第1条'): return True
    return False

def get_enactment_years_from_csv():
    """CSVから自治体ごとの制定年を取得する（クリーニングロジック適用）"""
    if not os.path.exists(TEXT_CSV_PATH):
        print(f"Error: CSV file not found at {TEXT_CSV_PATH}")
        return {}
        
    try:
        # 本文も読み込む
        df = pd.read_csv(TEXT_CSV_PATH, usecols=['自治体', '制定年', '本文'])
        
        muni_data = {} # muni -> list of (year, is_clean)
        
        for _, row in df.iterrows():
            muni_name = row['自治体']
            year_str = str(row['制定年'])
            text = row['本文']
            
            if pd.isna(muni_name) or pd.isna(year_str):
                continue
                
            match = re.search(r'(\d{4})', year_str)
            if match:
                year = int(match.group(1))
                is_clean = is_clean_text(text)
                
                if muni_name not in muni_data:
                    muni_data[muni_name] = []
                muni_data[muni_name].append((year, is_clean))
        
        # 最終的な年の決定ロジック
        final_year_map = {}
        for muni, records in muni_data.items():
            clean_years = [r[0] for r in records if r[1]]
            all_years = [r[0] for r in records]
            
            if clean_years:
                # クリーンなテキストがある場合は、その中で最も古い年を採用
                # （例：改正などではなく、最初の制定と思われるもの）
                final_year_map[muni] = min(clean_years)
            else:
                # クリーンなものがなければ、存在する中で最も古い年を採用（バックアップ）
                final_year_map[muni] = min(all_years)
                    
        print(f"制定年データをCSVから取得しました: {len(final_year_map)}件")
        return final_year_map
        
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return {}

def export_csc_bun_municipalities_classification(conn, output_dir):
    """*CSC_bunが付与された自治体を抽出し、7段階カテゴリと各種条文の有無を出力"""
    print("\n*CSC_bun付与自治体の分析を開始します...")
    
    # *CSC_bunを持つ自治体を取得
    cursor = conn.execute("""
        SELECT DISTINCT m.id, m.name, m.規制単位, m.area_type, m.regulation_type
        FROM municipalities m
        JOIN paragraphs p ON m.id = p.municipality_id
        JOIN paragraph_codings pc ON p.id = pc.paragraph_id
        JOIN coding_types ct ON pc.coding_type_id = ct.id
        WHERE ct.code = '*CSC_bun'
    """)
    municipalities = cursor.fetchall()
    
    # コーディングIDの取得
    cursor = conn.execute("SELECT id FROM coding_types WHERE code = ?", ('*CLAUSE_PENALTY',))
    result = cursor.fetchone()
    penalty_coding_id = result[0] if result else None
    
    coding_ids = {}
    for code in ['*Administrative_Guidance', '*Administrative_Disposition']:
        cursor = conn.execute("SELECT id FROM coding_types WHERE code = ?", (code,))
        result = cursor.fetchone()
        if result:
            coding_ids[code] = result[0]
            
    results = []
    for muni_id, muni_name, reg_unit, area_type, regulation_type in municipalities:
        # 7段階カテゴリ判定
        row = {'規制単位': reg_unit or '', 'area_type': area_type or '', 'regulation_type': regulation_type or ''}
        category = categorize_7level(row)
        
        # 各種条文の有無チェック
        coding_status = {}
        
        # 行政指導・行政処分
        for code, coding_id in coding_ids.items():
            cursor = conn.execute("""
                SELECT COUNT(*) FROM paragraphs p
                JOIN paragraph_codings pc ON p.id = pc.paragraph_id
                WHERE p.municipality_id = ? AND pc.coding_type_id = ?
            """, (muni_id, coding_id))
            count = cursor.fetchone()[0]
            coding_status[code] = '有' if count > 0 else '無'
            
        # 罰則（2分類）
        if penalty_coding_id:
            cursor = conn.execute("""
                SELECT p.text FROM paragraphs p
                JOIN paragraph_codings pc ON p.id = pc.paragraph_id
                WHERE p.municipality_id = ? AND pc.coding_type_id = ?
            """, (muni_id, penalty_coding_id))
            penalty_texts = cursor.fetchall()
            
            has_narrow = False
            has_other = False
            for (text,) in penalty_texts:
                if is_narrow_penalty_text(text):
                    has_narrow = True
                else:
                    has_other = True
            
            coding_status['*CLAUSE_PENALTY_NARROW'] = '有' if has_narrow else '無'
            coding_status['*CLAUSE_PENALTY_OTHER'] = '有' if has_other else '無'
        else:
            coding_status['*CLAUSE_PENALTY_NARROW'] = '無'
            coding_status['*CLAUSE_PENALTY_OTHER'] = '無'
            
        results.append({
            '自治体名': muni_name,
            '7段階カテゴリ': category,
            '行政指導': coding_status.get('*Administrative_Guidance', '無'),
            '行政処分': coding_status.get('*Administrative_Disposition', '無'),
            '狭義の罰則': coding_status.get('*CLAUSE_PENALTY_NARROW', '無'),
            'その他の罰則': coding_status.get('*CLAUSE_PENALTY_OTHER', '無')
        })
        
    df = pd.DataFrame(results)
    
    # カラムの並び順を指定（見やすくするため）
    columns_order = ['自治体名', '7段階カテゴリ', '行政指導', '行政処分', '狭義の罰則', 'その他の罰則']
    df = df[columns_order]
    
    output_path = f"{output_dir}/csc_bun_municipalities_classification.csv"
    df.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"分析結果を保存しました: {output_path}")
    return df



def get_7level_time_series_stats(conn, year_map):
    """7段階カテゴリと制定年を結合して時系列データを生成"""
    
    # 全自治体のデータを取得
    cursor = conn.execute("SELECT name, 規制単位, area_type, regulation_type FROM municipalities")
    municipalities = cursor.fetchall()
    
    results = []
    
    for muni_name, reg_unit, area_type, regulation_type in municipalities:
        if muni_name not in year_map:
            continue
            
        year = year_map[muni_name]
        
        # フィルタリング（例: 2012年〜2024年）
        # FIT法開始(2012)前後からの推移を見るのが適切か
        if year < 2010 or year > 2025:
            continue
            
        row = {'規制単位': reg_unit or '', 'area_type': area_type or '', 'regulation_type': regulation_type or ''}
        category = categorize_7level(row)
        
        results.append({
            '制定年': year,
            '7段階': category,
            'count': 1
        })
    
    df = pd.DataFrame(results)
    
    # 年×カテゴリで集計
    df_agg = df.groupby(['制定年', '7段階']).size().unstack(fill_value=0)
    
    return df_agg

def create_7level_time_series_chart(df_agg, output_path):
    """7段階カテゴリの時系列推移グラフを作成（実数・割合）
    
    df_agg: index=制定年, columns=7段階カテゴリ, value=件数
    """
    
    # 欠損しているカテゴリがあれば0埋めで追加
    all_categories = [
        '0_Lv1,2複合型',
        '1a_Lv2(区域・許可制優位)', '1b_Lv2(区域・届出制優位)',
        '2_Lv1不同意(禁止)', '3_Lv1許可or同意',
        '5_抑制区域+届出', '6_区域なし+許可制', '7_届出・協議のみ'
    ]
    
    for cat in all_categories:
        if cat not in df_agg.columns:
            df_agg[cat] = 0
            
    # 指定順序で並べ替え
    df_agg = df_agg[all_categories]
    
    # カテゴリ対応カラー
    # カテゴリ対応カラー（8色）
    colors = [
        '#E91E63',               # Lv1,2複合型（ピンク系で目立つ色）
        PASTEL_COLORS['Red'],    # Lv2許可制優位
        '#FF9999',               # Lv2届出制優位
        PASTEL_COLORS['Orange'], # Lv1不同意
        PASTEL_COLORS['Green'],  # Lv1許可
        PASTEL_COLORS['Blue'],   # 抑制区域
        PASTEL_COLORS['Purple'], # 区域なし許可制
        PASTEL_COLORS['Gray']    # 届出のみ
    ]
    
    # ラベル名
    label_names = {
        '0_Lv1,2複合型': '禁止・抑制\n複合',
        '1a_Lv2(区域・許可制優位)': '禁止区域\n(許可)',
        '1b_Lv2(区域・届出制優位)': '禁止区域\n(届出)',
        '2_Lv1不同意(禁止)': '抑制区域\n(不同意)',
        '3_Lv1許可or同意': '抑制区域\n(許可)',
        '5_抑制区域+届出': '抑制区域\n(届出)',
        '6_区域なし+許可制': '区域なし\n(許可)',
        '7_届出・協議のみ': '区域なし\n(届出)'
    }
    
    # グラフ作成 - 横幅20、高さ7
    fig, axes = plt.subplots(1, 2, figsize=(20, 7))
    
    # 1. 実数（積み上げ棒グラフ）
    ax1 = axes[0]
    df_agg.plot(kind='bar', stacked=True, ax=ax1, color=colors, width=0.8, edgecolor='white', linewidth=0.5)
    
    ax1.set_title('条例制定数の推移（件数）', fontsize=20, fontweight='bold')
    ax1.set_xlabel('制定年', fontsize=16)
    ax1.set_ylabel('制定件数', fontsize=16)
    ax1.grid(axis='y', alpha=0.3)
    ax1.tick_params(axis='x', rotation=45, labelsize=14)
    ax1.tick_params(axis='y', labelsize=14)
    
    # --- 修正箇所: 凡例を左側のグラフ(ax1)の左上に配置 ---
    handles, labels = ax1.get_legend_handles_labels()
    new_labels = [label_names.get(l, l).replace('\n', '') for l in labels] # 凡例は1行で表示
    # loc='upper left' で左上に配置します
    ax1.legend(handles, new_labels, loc='upper left', fontsize=14, title='規制強度区分')
    
    # 2. 割合（100%積み上げ棒グラフ）
    ax2 = axes[1]
    df_pct = df_agg.div(df_agg.sum(axis=1), axis=0) * 100
    df_pct.plot(kind='bar', stacked=True, ax=ax2, color=colors, width=0.8, edgecolor='white', linewidth=0.5)
    
    ax2.set_title('条例制定数の推移（割合）', fontsize=20, fontweight='bold')
    ax2.set_xlabel('制定年', fontsize=16)
    ax2.set_ylabel('割合 (%)', fontsize=16)
    ax2.set_ylim(0, 100)
    ax2.grid(axis='y', alpha=0.3)
    ax2.tick_params(axis='x', rotation=45, labelsize=14)
    ax2.tick_params(axis='y', labelsize=14)
    
    # --- 修正箇所: 右側のグラフ(ax2)の凡例は非表示にする ---
    ax2.legend().set_visible(False)
    
    plt.suptitle('規制強度7段階カテゴリごとの条例制定推移', fontsize=24, fontweight='bold', y=0.98)
    plt.tight_layout()
    
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"\n時系列推移グラフを保存しました: {output_path}")


def get_specific_variable_stats(conn):
    """特定変数（騒音、資金、情報公開、住民同意）の統計を取得"""
    
    # コーディングとの対応
    # 騒音防止: ＊CLAUSE_NOISE_FULL (ID 19) (Full-width asterisk assumed based on DB check)
    # 資金計画: *CLAUSE_FINANCE (ID 18)
    # 情報公開: ＊CLAUSE_INFORMATION_PROVISION (ID 17)
    
    target_codings = {
        '＊CLAUSE_NOISE_FULL': '騒音防止',
        '*CLAUSE_FINANCE': '資金計画',
        '＊CLAUSE_INFORMATION_PROVISION': '情報公開',
        '*CSC_bun': '住民同意'
    }
    
    coding_ids = {}
    for code, name in target_codings.items():
        # ワイルドカード検索ではなく完全一致でID取得を試みる
        cursor = conn.execute("SELECT id FROM coding_types WHERE code = ?", (code,))
        result = cursor.fetchone()
        if result:
            coding_ids[name] = result[0]
        else:
            # 見つからない場合、全角/半角の違いなどを考慮してLIKE検索
            cursor = conn.execute("SELECT id, code FROM coding_types WHERE code LIKE ?", (code.replace('*', '%').replace('＊', '%'),))
            result = cursor.fetchone()
            if result:
                coding_ids[name] = result[0]
                print(f"Code '{code}' matched to '{result[1]}' (ID: {result[0]})")
            else:
                print(f"Warning: Coding {code} not found.")

    cursor = conn.execute("""
        SELECT m.id, m.name, m.規制単位, m.area_type, m.regulation_type
        FROM municipalities m
    """)
    municipalities = cursor.fetchall()
    
    results = []
    for muni_id, muni_name, reg_unit, area_type, regulation_type in municipalities:
        row = {'規制単位': reg_unit or '', 'area_type': area_type or '', 'regulation_type': regulation_type or ''}
        category = categorize_7level(row)
        
        # 変数ごとの有無チェック
        coding_exists = {}
        for name, coding_id in coding_ids.items():
            cursor = conn.execute("""
                SELECT COUNT(*) FROM paragraphs p
                JOIN paragraph_codings pc ON p.id = pc.paragraph_id
                WHERE p.municipality_id = ? AND pc.coding_type_id = ?
            """, (muni_id, coding_id))
            count = cursor.fetchone()[0]
            coding_exists[f'{name}_有'] = 1 if count > 0 else 0
            
        results.append({
            '自治体名': muni_name,
            '7段階': category,
            **coding_exists
        })
        
    return pd.DataFrame(results)

def create_specific_variable_chart(df, output_path):
    """特定変数の自治体数グラフを作成（実数表示版）
    
    変更点:
    - 割合表示から実数表示に変更
    - カテゴリ内の全自治体数をグレーで表示（背景）
    - 該当条件を満たす自治体数を色付きで重ねて表示
    """
    
    variables = ['騒音防止', '資金計画', '情報公開', '住民同意']
    
    summary_data = []
    for category in sorted(df['7段階'].unique()):
        cat_df = df[df['7段階'] == category]
        total = len(cat_df)
        
        row = {'7段階': category, '自治体数': total}
        for var in variables:
            col = f'{var}_有'
            if col in df.columns:
                has_count = cat_df[col].sum()
                row[f'{var}_有数'] = has_count
                row[f'{var}_有率'] = (has_count / total * 100) if total > 0 else 0
            else:
                row[f'{var}_有数'] = 0
                row[f'{var}_有率'] = 0
        
        summary_data.append(row)
    
    df_summary = pd.DataFrame(summary_data)
    
    # グラフ作成
    fig, axes = plt.subplots(2, 2, figsize=(20, 14))
    axes = axes.flatten()
    
    label_names = {
        '0_Lv1,2複合型': '禁止・抑制\n複合',
        '1a_Lv2(区域・許可制優位)': '禁止区域\n(許可)',
        '1b_Lv2(区域・届出制優位)': '禁止区域\n(届出)',
        '2_Lv1不同意(禁止)': '抑制区域\n(不同意)',
        '3_Lv1許可or同意': '抑制区域\n(許可)',
        '5_抑制区域+届出': '抑制区域\n(届出)',
        '6_区域なし+許可制': '区域なし\n(許可)',
        '7_届出・協議のみ': '区域なし\n(届出)'
    }
    
    # 変数ごとの色設定（以前のパレットを活用）
    var_colors = {
        '騒音防止': PASTEL_COLORS['Red'],
        '資金計画': PASTEL_COLORS['Green'],
        '情報公開': PASTEL_COLORS['Blue'],
        '住民同意': PASTEL_COLORS['Orange']
    }
    
    for idx, var in enumerate(variables):
        ax = axes[idx]
        
        categories = df_summary['7段階'].tolist()
        labels = [label_names.get(c, c) for c in categories]
        totals = df_summary['自治体数'].tolist()
        has_counts = df_summary[f'{var}_有数'].tolist()
        has_rates = df_summary[f'{var}_有率'].tolist()
        
        x = range(len(labels))
        
        # Y軸の最大値を動的に設定（全カテゴリの最大自治体数に基づく）
        max_total = max(totals) if totals else 1
        y_limit = int(max_total * 1.15)  # 15%余裕を持たせる
        
        # 背景: カテゴリ内の全自治体数（グレー）
        bars_total = ax.bar(x, totals, color=PASTEL_COLORS['LightGray'], label='全自治体', alpha=0.6)
        
        # 前面: 該当条件を満たす自治体数（色付き）
        bars_has = ax.bar(x, has_counts, color=var_colors.get(var, '#999999'), label='条文あり', alpha=1.0)
        
        # ラベルを追加: 該当数/総数 と割合を表示
        for i, (count, total, rate) in enumerate(zip(has_counts, totals, has_rates)):
            # バーの上部に表示
            label_y = total + (y_limit * 0.02)
            ax.text(i, label_y, f'{count}/{total}\n({rate:.1f}%)', 
                    ha='center', va='bottom', fontsize=12, fontweight='bold', color='black')
        
        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=14)
        ax.set_ylabel('自治体数', fontsize=18)
        ax.set_title(f'{var}条文を持つ自治体数', fontsize=20, fontweight='bold')
        ax.set_ylim(0, y_limit)
        
        # 凡例: 全自治体（グレー）と条文あり（色）を表示
        ax.legend([bars_total, bars_has], ['全自治体', '条文あり'], loc='upper right', fontsize=14)
        
        ax.grid(axis='y', alpha=0.3)
        ax.tick_params(axis='y', labelsize=14)

    plt.suptitle('規制レベル別 - 特定項目（騒音・資金・情報・同意）の保有自治体数', 
                 fontsize=28, fontweight='bold', y=0.95)
    plt.tight_layout(h_pad=5.0, w_pad=3.0, rect=[0, 0.03, 1, 0.95])
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"\n特定変数自治体数グラフを保存しました: {output_path}")

def main():
    conn = sqlite3.connect(DB_PATH)
    try:
        df = get_regulation_unit_stats(conn)
        if df.empty:
            print("データが見つかりませんでした")
            return
        
        # CSVとグラフの作成
        df.to_csv(f"{OUTPUT_DIR}/regulation_unit_coding_analysis.csv", index=False, encoding='utf-8-sig')
        create_stacked_bar_chart(df, f"{OUTPUT_DIR}/regulation_unit_coding_chart.png")
        
        df_categorized = get_categorized_stats(df)
        df_categorized.to_csv(f"{OUTPUT_DIR}/regulation_unit_coding_analysis_categorized.csv", index=False, encoding='utf-8-sig')
        create_categorized_chart(df_categorized, f"{OUTPUT_DIR}/regulation_unit_coding_chart_categorized.png")
        
        df_7level = get_7level_stats(conn)
        df_7level.to_csv(f"{OUTPUT_DIR}/regulation_unit_coding_analysis_7level.csv", index=False, encoding='utf-8-sig')
        create_7level_chart(df_7level, f"{OUTPUT_DIR}/regulation_unit_coding_chart_7level.png")
        
        # デザイン修正対象1: 自治体数分布グラフ
        create_7level_municipality_distribution_chart(df_7level, f"{OUTPUT_DIR}/municipality_distribution_basic_unit.png")
        
        df_muni = get_municipality_level_stats(conn)
        df_muni.to_csv(f"{OUTPUT_DIR}/municipality_coding_presence.csv", index=False, encoding='utf-8-sig')
        
        # デザイン修正対象2: 自治体割合グラフ
        create_municipality_proportion_chart(df_muni, f"{OUTPUT_DIR}/municipality_coding_proportion_chart.png")
        
        # 新機能: 時系列推移グラフ
        print("\n時系列データの分析を開始します...")
        year_map = get_enactment_years_from_csv()
        if year_map:
            df_time_series = get_7level_time_series_stats(conn, year_map)
            df_time_series.to_csv(f"{OUTPUT_DIR}/regulation_unit_coding_analysis_time_series.csv", encoding='utf-8-sig')
            create_7level_time_series_chart(df_time_series, f"{OUTPUT_DIR}/regulation_unit_coding_chart_time_series.png")
        else:
            print("制定年データが取得できなかったため、時系列分析をスキップします。")
            
        # 新機能: *CSC_bun付与自治体の詳細分析
        export_csc_bun_municipalities_classification(conn, OUTPUT_DIR)

        # 新機能: 特定変数（騒音・資金・情報・同意）の分析
        print("\n特定変数の分析を開始します...")
        df_specific = get_specific_variable_stats(conn)
        df_specific.to_csv(f"{OUTPUT_DIR}/specific_variable_analysis.csv", index=False, encoding='utf-8-sig')
        create_specific_variable_chart(df_specific, f"{OUTPUT_DIR}/specific_variable_chart.png") # ファイル名統一
        
        print("\n全ての処理が完了しました。")
        
    finally:
        conn.close()

if __name__ == '__main__':
    main()