import matplotlib.pyplot as plt
import pandas as pd
import re
import sys
from pathlib import Path

def get_font_properties(font_path):
    """Get font properties from a font file."""
    try:
        import matplotlib.font_manager as fm
        prop = fm.FontProperties(fname=font_path)
        plt.rcParams['font.family'] = prop.get_name()
        return prop
    except Exception as e:
        print(f"Error loading font file {font_path}: {e}")
        return None

def create_and_save_graphs(df, title_base, filename_base, font_prop):
    """Create and save graphs from a DataFrame."""
    # pivot_tableを使って集計: 行=年, 列=area_type
    pivot_df = df.groupby(['enactment_year', 'area_type']).size().unstack(fill_value=0)
    
    if pivot_df.empty:
        print(f"No data to plot for {filename_base}.")
        return

    # 積み上げ順序の指定（下から順に）
    desired_order = ['区域設定なし', '抑制地区制', '禁止区域制', '2層構造(抑制+禁止)']
    
    # データに存在する列のみを抽出して並べ替え
    existing_order = [col for col in desired_order if col in pivot_df.columns]
    # 指定に含まれていない列（Unknownなど）は上部に配置
    remaining_cols = [col for col in pivot_df.columns if col not in desired_order]
    new_order = existing_order + remaining_cols
    
    pivot_df = pivot_df[new_order]

    # フォント設定
    title_font = font_prop.copy() if font_prop else None
    if title_font: title_font.set_size(16)
    
    label_font = font_prop.copy() if font_prop else None
    if label_font: label_font.set_size(12)

    # --- グラフ1: 実数 ---
    # 新しいFigureを作成
    fig1, ax1 = plt.subplots(figsize=(14, 8))
    pivot_df.plot(kind='bar', stacked=True, ax=ax1, colormap='viridis', width=0.8)
    
    if font_prop:
        ax1.set_title(f'{title_base}（地域区分別）', fontproperties=title_font)
        ax1.set_xlabel('制定年', fontproperties=label_font)
        ax1.set_ylabel('自治体数', fontproperties=label_font)
        ax1.legend(title='地域区分', prop=label_font)
        # x軸ラベルの回転とフォント設定
        for label in ax1.get_xticklabels():
            label.set_rotation(45)
            label.set_fontproperties(label_font)
        for label in ax1.get_yticklabels():
            label.set_fontproperties(label_font)
    else:
        ax1.set_title(f'{title_base} (by Area Type)')
        ax1.set_xlabel('Enactment Year')
        ax1.set_ylabel('Count')
        ax1.legend(title='Area Type')
        plt.xticks(rotation=45)

    ax1.grid(axis='y', linestyle='--', alpha=0.7)
    plt.tight_layout()
    
    # バージョン付きファイル名で保存
    output_path_count = make_dated_versioned_path(Path('.'), f'{filename_base}_count_', '.png')
    plt.savefig(output_path_count)
    print(f"Count graph saved to {output_path_count}")
    plt.close(fig1)

    # --- グラフ2: 割合 ---
    # 行ごとの合計で割って100を掛ける
    pivot_df_ratio = pivot_df.div(pivot_df.sum(axis=1), axis=0) * 100
    
    fig2, ax2 = plt.subplots(figsize=(14, 8))
    pivot_df_ratio.plot(kind='bar', stacked=True, ax=ax2, colormap='viridis', width=0.8)
    
    if font_prop:
        ax2.set_title(f'{title_base}割合（地域区分別）', fontproperties=title_font)
        ax2.set_xlabel('制定年', fontproperties=label_font)
        ax2.set_ylabel('割合 (%)', fontproperties=label_font)
        # 凡例をグラフの外に出す
        ax2.legend(title='地域区分', prop=label_font, bbox_to_anchor=(1.01, 1), loc='upper left')
        
        for label in ax2.get_xticklabels():
            label.set_rotation(45)
            label.set_fontproperties(label_font)
        for label in ax2.get_yticklabels():
            label.set_fontproperties(label_font)
    else:
        ax2.set_title(f'{title_base} Ratio (by Area Type)')
        ax2.set_xlabel('Enactment Year')
        ax2.set_ylabel('Ratio (%)')
        ax2.legend(title='Area Type', bbox_to_anchor=(1.01, 1), loc='upper left')
        plt.xticks(rotation=45)

    ax2.grid(axis='y', linestyle='--', alpha=0.7)
    plt.tight_layout()
    
    # バージョン付きファイル名で保存
    output_path_ratio = make_dated_versioned_path(Path('.'), f'{filename_base}_ratio_', '.png')
    plt.savefig(output_path_ratio)
    print(f"Ratio graph saved to {output_path_ratio}")
    plt.close(fig2)

def main():
    """Main function."""
    # フォントファイルのパス
    font_path = 'NotoSansCJK-Regular.ttc'
    
    # フォントプロパティの取得
    font_prop = get_font_properties(font_path)
    
    if font_prop:
        print(f"Font loaded: {font_prop.get_name()}")
    else:
        print("日本語フォントが見つかりませんでした。デフォルトフォントを使用します。")
    
    # データの読み込み
    df = pd.read_csv('data.csv')
    
    # グラフの生成
    create_and_save_graphs(df, 'Title', 'filename', font_prop)

if __name__ == '__main__':
    main()