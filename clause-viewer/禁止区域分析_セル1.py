"""
禁止区域分析 - セル1 コード
このコードを禁止区域分析.ipynbのセル1にコピペしてください。

機能追加：
- clause_data4.dbから次の条項を取得
- 次の条項が「2 事業者は...」のように数字で始まる場合のみ取得
- 「第x条」や「(事前協議)」で始まる場合は取得しない
"""

import pandas as pd
import re
import os
import sqlite3

def main():
    # 出力先ディレクトリ（ノートブックと同じフォルダ）
    OUTPUT_DIR = '/home/ubuntu/cur/isep/clause-viewer/'
    
    # データベースパス
    DB_PATH = '/home/ubuntu/cur/isep/clause-viewer/clause_data4.db'
    
    # 1. データの読み込み（Zone Lv2: 禁止区域）
    input_file = '/home/ubuntu/cur/isep/clause-viewer/csv_by_coding/CLAUSE_ZONE_Lv2.csv'
    try:
        df = pd.read_csv(input_file)
        print(f"ファイル読み込み成功: {input_file} (全{len(df)}行)")
    except FileNotFoundError:
        print(f"エラー: ファイル '{input_file}' が見つかりません。")
        return

    # 1.5. 次の条項を取得して連結（項をまたぐ規定の対応）
    # 例：第1項「禁止区域として指定できる」→第2項「含めてはならない」
    print("\n次条項の取得を開始...")
    
    def get_next_paragraph_text(original_paragraph_id, db_path):
        """次の段落のテキストを取得する。条件に合う場合のみ返す。"""
        if pd.isna(original_paragraph_id):
            return None
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # 次の段落（id + 1）のテキストを取得
            next_id = int(original_paragraph_id) + 1
            cursor.execute(
                "SELECT text FROM paragraphs WHERE id = ?",
                (next_id,)
            )
            result = cursor.fetchone()
            conn.close()
            
            if result:
                next_text = result[0]
                if next_text:
                    # 取得条件のチェック
                    # 「第x条」で始まる場合は取得しない
                    if re.match(r'^第\d+条', next_text.strip()):
                        return None
                    # 括弧で始まる見出し（例：(事前協議)）の場合は取得しない
                    if re.match(r'^[（\(].+?[）\)]', next_text.strip()):
                        return None
                    # 数字で始まる場合（例：「2 事業者は...」）は取得する
                    if re.match(r'^\d+\s', next_text.strip()):
                        return next_text
            return None
        except Exception as e:
            return None
    
    # 次条項テキストを取得
    df['next_paragraph_text'] = df['original_paragraph_id'].apply(
        lambda x: get_next_paragraph_text(x, DB_PATH)
    )
    
    # 次条項が取得された件数を表示
    next_para_count = df['next_paragraph_text'].notna().sum()
    print(f"次条項が追加された件数: {next_para_count} 件")
    
    # 分析用テキストを作成（元テキスト + 次条項テキスト）
    def create_analysis_text(row):
        text = row['text'] if pd.notna(row['text']) else ''
        next_text = row['next_paragraph_text'] if pd.notna(row['next_paragraph_text']) else ''
        if next_text:
            return text + '\n' + next_text
        return text
    
    df['analysis_text'] = df.apply(create_analysis_text, axis=1)

    # 2. フィルタリング条件の設定（Zone Lv2 禁止区域向け）
    # 禁止区域の特性：「禁止」「区域指定」が主テーマ、例外規定も多い
    # 抑制区域（Zone Lv1）との違い：許可・同意より禁止が中心

    search_criteria = {
        # 【禁止】: 明示的な禁止（最も強い規制）
        '禁止': [
            r'してはならない',          # 「事業を行ってはならない」「実施してはならない」
            r'含めてはならない',         # 「事業区域に含めてはならない」
            r'認めない',                # 「設置を認めない」「実施を認めない」
            r'同意しない',              # 「同意しないものとする」
        ],

        # 【例外】: ただし書きによる例外規定
        '例外': [
            r'この限りでない',           # 「ただし、～この限りでない」
            r'この限りではない',
            r'適用しない',              # 「規定は、適用しない」
            r'除く',                    # 「～を除く」「～は除く」
        ],

        # 【裁量】: 首長の判断による例外
        '裁量': [
            r'(市長|町長|村長)が.{0,30}認め',  # 「市長が特に必要と認めるとき」
            r'支障がないと.{0,10}認め',
            r'やむを得ないと認め',
            r'相当の理由があると認め',
            r'(市長|町長|村長)が判断',
        ],

        # 【許可】: 許可を受ければ可能
        '許可': [
            r'許可を受け',              # 「許可を受けなければならない」
            r'許可されている場合',       # 「設置が許可されている場合」
            r'(市長|町長|村長)の許可',
            r'許認可',
        ],

        # 【指定】: 禁止区域の指定に関する規定（定義条項）
        '指定': [
            r'禁止区域として指定',       # 「禁止区域として指定する」
            r'禁止区域に指定',
            r'指定することができる',
            r'定めるものとする',
            r'禁止区域は.{0,20}とする',  # 「禁止区域は、次のとおりとする」
        ],

        # 【手続】: 届出・申請・協議等の手続き
        '手続': [
            r'届出',
            r'届け出',
            r'申請',
            r'協議',
        ],
    }

    print(f"\n検索条件をZone Lv2（禁止区域）向けに設定しました。")
    print(f"カテゴリ: {list(search_criteria.keys())}")

    # 3. マッチング処理（analysis_textを使用）

    def identify_conditions(text):
        if not isinstance(text, str):
            return None

        hits = set()

        for category, patterns in search_criteria.items():
            for pattern in patterns:
                if re.search(pattern, text):
                    hits.add(category)
                    break  # そのカテゴリ内で1つヒットすればOK

        if not hits:
            return None

        # リスト化してソート（表示順を一定にするため）
        return ','.join(sorted(list(hits)))

    # 新しいカラム 'matched_condition' に結果を格納（analysis_textを使用）
    df['matched_condition'] = df['analysis_text'].apply(identify_conditions)

    # 4. フィルタリング
    matched_df = df[df['matched_condition'].notna()]
    unmatched_df = df[df['matched_condition'].isna()]

    # 5. 結果の出力
    print(f"\n--- 実行結果 ---")
    print(f"抽出された件数: {len(matched_df)} 件")
    print(f"抽出されなかった件数: {len(unmatched_df)} 件")

    # CSVファイルへの書き出し
    output_matched = os.path.join(OUTPUT_DIR, 'CLAUSE_ZONE_Lv2_matched_final.csv')
    output_unmatched = os.path.join(OUTPUT_DIR, 'CLAUSE_ZONE_Lv2_unmatched_final.csv')

    matched_df.to_csv(output_matched, index=False)
    unmatched_df.to_csv(output_unmatched, index=False)

    print(f"ファイルを保存しました:\n 1. {output_matched}\n 2. {output_unmatched}")

    # 6. 分析用サンプル表示
    print("\n--- カテゴリごとの抽出内訳 ---")
    print(matched_df['matched_condition'].value_counts().head(15))

    # 7. カテゴリ別の詳細統計
    print("\n--- 単一カテゴリ vs 複合カテゴリ ---")
    single_cat = matched_df[~matched_df['matched_condition'].str.contains(',')]
    multi_cat = matched_df[matched_df['matched_condition'].str.contains(',')]
    print(f"単一カテゴリ: {len(single_cat)} 件")
    print(f"複合カテゴリ: {len(multi_cat)} 件")
    
    # 8. 次条項による追加マッチのサンプル表示
    print("\n--- 次条項取得による追加分析例 ---")
    next_para_samples = df[df['next_paragraph_text'].notna()][['municipality_name', 'text', 'next_paragraph_text', 'matched_condition']].head(5)
    for _, row in next_para_samples.iterrows():
        print(f"\n【{row['municipality_name']}】")
        print(f"  元テキスト: {row['text'][:80]}...")
        print(f"  次条項: {row['next_paragraph_text'][:80]}...")
        print(f"  分類結果: {row['matched_condition']}")

# 関数を実行
main()
