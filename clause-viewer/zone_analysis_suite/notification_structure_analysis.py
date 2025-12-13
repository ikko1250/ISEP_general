"""
届出制構造分析スクリプト
「届出制優位」かつ「抑制区域設定あり」で、
lv1/lv2ファイルで許可・禁止等に分類されていない自治体のテキストを分析する

分類軸:
1. 協議・調整
2. 変更届出
3. 事前届出
4. 完了届出
5. 着手届出
6. 撤去届出
7. 中止休止届出
"""

import pandas as pd
import re
import sqlite3
import os
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

# 設定
# 設定
DB_PATH = '/home/ubuntu/cur/isep/clause-viewer/clause_data4.db'
LV1_FILE = './CLAUSE_ZONE_Lv1_classification_result.csv'
LV2_FILE = './CLAUSE_ZONE_Lv2_classification_result.csv'
OUTPUT_DIR = './'
OUTPUT_FILE = os.path.join(OUTPUT_DIR, 'notification_structure_analysis_result.csv')
OUTPUT_CHART = os.path.join(OUTPUT_DIR, 'notification_structure_chart.png')

# フィルタリング済み自治体リスト（届出制優位 + 抑制区域あり + lv1/lv2で除外されていない）
FILTERED_MUNICIPALITIES = [
    '由布市', 'つくば市', '大宜味村', '笠間市', '龍ケ崎市', '志摩市', '結城市', '千葉県長柄町',
    '美祢市', '茨城県守谷市', '長野県筑北村', '上田市', '五霞町', '原村', '富谷市', '岬町',
    '朝日村', '瀬戸市', '熊取町', '赤磐市', '八幡浜市', '可児市', '川島町', '東栄町', '浜中町',
    '益子町', '真岡市', '下妻市', '加美町', '吉見町', '大崎市', '山形村', '嵐山町', '鉾田市',
    '長沼町', '七ヶ宿町', '入間市', '坂東市', '天草市', '小川町', '村田町', '諏訪市', '南三陸町',
    '大洲市', '寄居町', '牛久市', '茨城町', '大空町', '田村市', '那珂市', '田川市', '野木町',
    '東広島市', '利根町', '嬉野市', '高槻市', '五條市', '市川町', '豊橋市', '美浜町', 'ときがわ町',
    '大網白里市', '鳩山町', '八千代町', '日立市', '標津町', '石巻市', '滑川町', '天理市', '日出町',
    '宇佐市', '南知多町', '色麻町', '熊谷市', '月形町', '山元町', '岩国市', '大津町', '那須塩原市',
    '大町町', '瑞浪市', '東海村', 'ニセコ町', '鶴居村', '武雄市', '栗原市', '佐伯市', '赤穂市',
    '南木曽町', '中津川市', '雫石町', '東村', '鳥羽市'
]


def setup_japanese_font():
    """日本語フォントを設定する"""
    jp_fonts = ['M+ 1c', 'Noto Sans CJK JP', 'IPAGothic', 'TakaoGothic']
    available_fonts = set([f.name for f in fm.fontManager.ttflist])
    found_font = None
    for font in jp_fonts:
        if font in available_fonts:
            found_font = font
            break
    
    if found_font:
        plt.rcParams['font.family'] = found_font
        plt.rcParams['axes.unicode_minus'] = False
        print(f"日本語フォント '{found_font}' を設定しました。")
    else:
        print("適切な日本語フォントが見つかりませんでした。")


def get_municipality_texts(db_path: str, municipality_names: list) -> pd.DataFrame:
    """
    DBから指定された自治体のテキストを取得する
    
    Args:
        db_path: SQLiteデータベースのパス
        municipality_names: 自治体名のリスト
    
    Returns:
        自治体名とテキストを含むDataFrame
    """
    conn = sqlite3.connect(db_path)
    
    # 自治体名をプレースホルダーで結合
    placeholders = ','.join(['?' for _ in municipality_names])
    
    query = f"""
    SELECT 
        m.name AS municipality,
        GROUP_CONCAT(p.text, '\n---\n') AS full_text
    FROM municipalities m
    JOIN paragraphs p ON m.id = p.municipality_id
    WHERE m.name IN ({placeholders})
    GROUP BY m.id, m.name
    """
    
    df = pd.read_sql_query(query, conn, params=municipality_names)
    conn.close()
    
    return df


def create_chart(summary: pd.Series, total: int, output_path: str):
    """
    分類結果のグラフを作成する
    
    Args:
        summary: カテゴリごとの該当自治体数
        total: 対象自治体の総数
        output_path: グラフの保存先パス
    """
    # 日本語フォントの設定
    setup_japanese_font()
    
    # 降順でソート
    counts_sorted = summary.sort_values(ascending=True)
    
    # グラフのサイズを設定
    fig, ax = plt.subplots(figsize=(12, 7))
    
    # カラーパレットを設定
    color_map = {
        '協議': '#1f77b4',           # 青
        '変更届出': '#ff7f0e',        # オレンジ
        '事前届出': '#2ca02c',        # 緑
        '完了届出': '#d62728',        # 赤
        '着手届出': '#9467bd',        # 紫
        '撤去届出': '#8c564b',        # 茶
        '中止休止届出': '#7f7f7f'      # グレー
    }
    colors = [color_map.get(cat, '#333333') for cat in counts_sorted.index]
    
    # 横棒グラフを作成
    bars = ax.barh(counts_sorted.index, counts_sorted.values, color=colors, edgecolor='white', linewidth=0.5)
    
    # 各バーに件数を表示
    for bar, count in zip(bars, counts_sorted.values):
        ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height()/2, 
                f'{count}自治体', ha='left', va='center', fontsize=12, color='black')
    
    # タイトルと軸ラベルを設定
    ax.set_title(f'届出制構造分析結果\n（対象: {total}自治体 - 届出制優位+抑制区域あり）', fontsize=16, fontweight='bold')
    ax.set_xlabel('自治体数', fontsize=14)
    ax.set_xlim(0, max(counts_sorted.values) * 1.25)
    
    # Y軸ラベルのフォントサイズ
    ax.tick_params(axis='y', labelsize=11)
    ax.tick_params(axis='x', labelsize=11)
    
    # グリッド線
    ax.xaxis.grid(True, linestyle='--', alpha=0.3)
    ax.set_axisbelow(True)
    
    # 枠線を薄く
    for spine in ax.spines.values():
        spine.set_alpha(0.3)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\nグラフを保存しました: {output_path}")
    plt.close()


def main():
    print("=== 届出制構造分析スクリプト ===\n")
    
    # 1. DBからテキストを取得
    print(f"対象自治体数: {len(FILTERED_MUNICIPALITIES)}")
    df = get_municipality_texts(DB_PATH, FILTERED_MUNICIPALITIES)
    print(f"テキスト取得成功: {len(df)} 自治体\n")
    
    # 2. 分類条件の設定（PDCAサイクルで改善）
    keywords = {
        # 協議関連（調整・事前協議を含む）
        '協議': r'協議|調整|相談',
        
        # 変更届出関連
        '変更届出': r'変更届出|変更協議|変更.{0,10}届け?出|変更.{0,10}届出|内容を変更',
        
        # 事前届出関連（事前協議も含む）
        '事前届出': r'事前届出|事前確認|事前調整|事前.{0,10}届け?出|事前協議|90日前|60日前|30日前|日前まで',
        
        # 完了届出関連（工事完了、撤去完了も含む）
        '完了届出': r'完了届出|完了の届出|完了確認|完了報告|完了.{0,10}届け?出|工事.{0,10}完了|設置.{0,10}完了|完了した.{0,10}届',
        
        # 着手届出関連（新規追加）
        '着手届出': r'着手.{0,10}届|着手予定|工事.{0,10}着手|着手.{0,10}届出|着手する日',
        
        # 撤去/廃止届出関連（新規追加）
        '撤去届出': r'撤去.{0,10}届|廃止.{0,10}届|撤去.{0,10}完了|発電事業.{0,10}終了|事業.{0,10}廃止',
        
        # 中止/休止届出関連（新規追加）
        '中止休止届出': r'中止.{0,10}届|休止.{0,10}届|中断.{0,10}届|再開.{0,10}届'
    }
    
    print("分類条件:")
    for key, pattern in keywords.items():
        print(f"  {key}: {pattern}")
    print()
    
    # 3. 分類結果を格納するDataFrameを初期化
    classification_df = pd.DataFrame({'自治体名': df['municipality']})
    
    # 4. テキスト検索による分類
    for key, pattern in keywords.items():
        # テキストを取得し、NaNを空文字列に置換
        text_series = df['full_text'].astype(str).fillna('')
        
        # 正規表現でパターンにマッチするかどうかをチェックし、結果を1/0で格納
        classification_df[key] = text_series.apply(
            lambda x: 1 if re.search(pattern, x) else 0
        )
    
    # 5. 結果をCSVファイルとして保存
    classification_df.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')
    print(f"分類結果を保存しました: {OUTPUT_FILE}")
    
    # 6. 分類結果のサマリーを出力
    print("\n--- 分類結果サマリー ---")
    summary = classification_df.drop(columns=['自治体名']).sum()
    print(summary.to_frame(name='該当自治体数'))
    print("------------------------")
    
    # 7. 各カテゴリの該当自治体を表示
    print("\n--- 各カテゴリの該当自治体 ---")
    for key in keywords.keys():
        matching = classification_df[classification_df[key] == 1]['自治体名'].tolist()
        print(f"\n{key} ({len(matching)}件):")
        if matching:
            print(f"  {', '.join(matching)}")
        else:
            print("  なし")
    
    # 8. いずれにも該当しない自治体
    no_match_mask = classification_df[list(keywords.keys())].sum(axis=1) == 0
    no_match = classification_df[no_match_mask]['自治体名'].tolist()
    print(f"\n--- いずれにも該当しない自治体 ({len(no_match)}件) ---")
    if no_match:
        print(f"  {', '.join(no_match)}")
    else:
        print("  なし")
    
    # 9. グラフの作成
    create_chart(summary, len(df), OUTPUT_CHART)


if __name__ == "__main__":
    main()

