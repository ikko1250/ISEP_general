import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import os
import re
from pathlib import Path
# import seaborn as sns
from versioning.filename import make_dated_versioned_path

# 日本語フォントの設定
def set_japanese_font():
    # 優先順位の高いフォントリスト
    fonts = [
        '/usr/share/fonts/truetype/mplus/mplus-1c-regular.ttf',
        '/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf',
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/truetype/fonts-japanese-gothic.ttf',
        '/usr/share/fonts/opentype/ipafont-mincho/ipam.ttf'
    ]
    
    font_path = None
    for f in fonts:
        if os.path.exists(f):
            font_path = f
            break
            
    if font_path:
        prop = fm.FontProperties(fname=font_path)
        plt.rcParams['font.family'] = prop.get_name()
        return prop
    else:
        print("日本語フォントが見つかりませんでした。デフォルトフォントを使用します。")
        return None

def create_and_save_graphs(df, group_col, title_base, filename_base, font_prop, legend_label, order_list=None):
    # pivot_tableを使って集計: 行=年, 列=group_col
    pivot_df = df.groupby(['enactment_year', group_col]).size().unstack(fill_value=0)
    
    if pivot_df.empty:
        print(f"No data to plot for {filename_base}.")
        return

    # 積み上げ順序の指定
    if order_list:
        # データに存在する列のみを抽出して並べ替え
        existing_order = [col for col in order_list if col in pivot_df.columns]
        # 指定に含まれていない列（Unknownなど）は上部に配置
        remaining_cols = [col for col in pivot_df.columns if col not in order_list]
        new_order = existing_order + remaining_cols
        pivot_df = pivot_df[new_order]

    # フォント設定
    title_font = font_prop.copy() if font_prop else None
    if title_font: title_font.set_size(22)
    
    label_font = font_prop.copy() if font_prop else None
    if label_font: label_font.set_size(16)

    # --- グラフ1: 実数 ---
    # 新しいFigureを作成
    fig1, ax1 = plt.subplots(figsize=(14, 8))
    pivot_df.plot(kind='bar', stacked=True, ax=ax1, colormap='viridis', width=0.8)
    
    if font_prop:
        ax1.set_title(f'{title_base}\n（{legend_label}別）', fontproperties=title_font)
        ax1.set_xlabel('制定年', fontproperties=label_font)
        ax1.set_ylabel('自治体数', fontproperties=label_font)
        ax1.legend(title=legend_label, prop=label_font, title_fontproperties=label_font)
        # x軸ラベルの回転とフォント設定
        for label in ax1.get_xticklabels():
            label.set_rotation(45)
            label.set_fontproperties(label_font)
        for label in ax1.get_yticklabels():
            label.set_fontproperties(label_font)
    else:
        ax1.set_title(f'{title_base} (by {legend_label})')
        ax1.set_xlabel('Enactment Year')
        ax1.set_ylabel('Count')
        ax1.legend(title=legend_label)
        plt.xticks(rotation=45)

    ax1.grid(axis='y', linestyle='--', alpha=0.7)
    plt.tight_layout()
    
    # バージョン付きファイル名で保存
    output_dir = Path('out/enactment_analyze')
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path_count = make_dated_versioned_path(output_dir, f'{filename_base}_count_', '.png')
    plt.savefig(output_path_count)
    print(f"Count graph saved to {output_path_count}")
    plt.close(fig1)

    # --- グラフ2: 割合 ---
    # 行ごとの合計で割って100を掛ける
    pivot_df_ratio = pivot_df.div(pivot_df.sum(axis=1), axis=0) * 100
    
    fig2, ax2 = plt.subplots(figsize=(14, 8))
    pivot_df_ratio.plot(kind='bar', stacked=True, ax=ax2, colormap='viridis', width=0.8)
    
    if font_prop:
        ax2.set_title(f'{title_base}割合\n（{legend_label}別）', fontproperties=title_font)
        ax2.set_xlabel('制定年', fontproperties=label_font)
        ax2.set_ylabel('割合 (%)', fontproperties=label_font)
        # 凡例をグラフの外に出す
        ax2.legend(title=legend_label, prop=label_font, bbox_to_anchor=(1.01, 1), loc='upper left', title_fontproperties=label_font)
        
        for label in ax2.get_xticklabels():
            label.set_rotation(45)
            label.set_fontproperties(label_font)
        for label in ax2.get_yticklabels():
            label.set_fontproperties(label_font)
    else:
        ax2.set_title(f'{title_base} Ratio (by {legend_label})')
        ax2.set_xlabel('Enactment Year')
        ax2.set_ylabel('Ratio (%)')
        ax2.legend(title=legend_label, bbox_to_anchor=(1.01, 1), loc='upper left')
        plt.xticks(rotation=45)

    ax2.grid(axis='y', linestyle='--', alpha=0.7)
    plt.tight_layout()
    
    # バージョン付きファイル名で保存
    output_path_ratio = make_dated_versioned_path(output_dir, f'{filename_base}_ratio_', '.png')
    plt.savefig(output_path_ratio)
    print(f"Ratio graph saved to {output_path_ratio}")
    plt.close(fig2)

def main():
    # データベースパスの候補
    db_paths = [
        'clause-viewer/clause_data3.db',
        'clause_data3.db'
    ]
    
    db_path = None
    for path in db_paths:
        if os.path.exists(path) and os.path.getsize(path) > 0:
            db_path = path
            break
            
    if not db_path:
        print("Error: clause_data3.db not found or empty.")
        return

    print(f"Using database: {db_path}")
    conn = sqlite3.connect(db_path)
    
    # データを抽出するクエリ
    # municipalitiesテーブルとparagraphsテーブルを結合
    # 各自治体について、最も古いyearを取得してenactment_yearとする
    # area_typeも取得
    query = """
    SELECT 
        m.name as municipality_name,
        m.area_type,
        m.regulation_type,
        m.resident_consent,
        MIN(p.year) as enactment_year
    FROM 
        municipalities m
    JOIN 
        paragraphs p ON m.id = p.municipality_id
    WHERE
        p.year IS NOT NULL AND p.year != ''
    GROUP BY 
        m.id
    """
    
    try:
        df = pd.read_sql_query(query, conn)
    except Exception as e:
        print(f"Error executing query: {e}")
        conn.close()
        return
    
    conn.close()
    
    if df.empty:
        print("No data found.")
        return

    print(f"Extracted {len(df)} records.")

    # enactment_yearのクリーニング
    # 4桁の数字を抽出
    df['enactment_year_clean'] = df['enactment_year'].astype(str).apply(lambda x: re.search(r'(\d{4})', x).group(1) if re.search(r'(\d{4})', x) else None)
    
    df = df.dropna(subset=['enactment_year_clean'])
    df['enactment_year'] = df['enactment_year_clean'].astype(int)
    
    # 異常な年のフィルタリング（1990年〜2030年）
    df = df[(df['enactment_year'] >= 1990) & (df['enactment_year'] <= 2030)]

    # area_typeの欠損処理
    df['area_type'] = df['area_type'].fillna('Unknown')
    df.loc[df['area_type'] == '', 'area_type'] = 'Unknown'
    
    # regulation_typeの欠損処理
    df['regulation_type'] = df['regulation_type'].fillna('Unknown')
    df.loc[df['regulation_type'] == '', 'regulation_type'] = 'Unknown'
    
    # resident_consentの欠損処理
    df['resident_consent'] = df['resident_consent'].fillna('')

    # グラフ作成
    font_prop = set_japanese_font()
    # area_type 用の設定
    area_order = ['区域設定なし', '抑制地区制', '禁止地区制', '2層構造(抑制+禁止)']
    
    # 1. 全自治体
    print("\n--- Generating graphs for ALL municipalities ---")
    # Area Type
    create_and_save_graphs(df, 'area_type', '制定年ごとの自治体数', 'enactment_year_area', font_prop, '地域区分', area_order)
    # Regulation Type
    create_and_save_graphs(df, 'regulation_type', '制定年ごとの自治体数', 'enactment_year_reg', font_prop, '条例タイプ')
    
    # 2. 住民同意要件あり ('有') の自治体
    print("\n--- Generating graphs for municipalities with Resident Consent ---")
    df_consent = df[df['resident_consent'] == '有']
    if not df_consent.empty:
        print(f"Found {len(df_consent)} municipalities with resident consent.")
        # Area Type
        create_and_save_graphs(df_consent, 'area_type', '制定年ごとの自治体数（住民同意要件あり）', 'enactment_year_consent_area', font_prop, '地域区分', area_order)
        # Regulation Type
        create_and_save_graphs(df_consent, 'regulation_type', '制定年ごとの自治体数（住民同意要件あり）', 'enactment_year_consent_reg', font_prop, '条例タイプ')
    else:
        print("No municipalities found with resident_consent = '有'")

if __name__ == "__main__":
    main()
