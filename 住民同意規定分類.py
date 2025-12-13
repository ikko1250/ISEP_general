import pandas as pd
import io

def main():
    # データの読み込み
    try:
        df = pd.read_csv("/home/ubuntu/cur/isep/clause-viewer/csv_by_coding/CSC_bun.csv")
    except FileNotFoundError:
        print("エラー: 'CSC_bun.csv' が見つかりません。")
        return

    # ---------------------------------------------------------
    # 1. 条文単位の分類ロジック (Row-level Classification)
    # ---------------------------------------------------------
    def classify_unified(text):
        text = str(text)
        
        # 4. 例外・緩和規定
        if "ただし" in text and "同意" in text and ("この限りではない" in text or "例外" in text or "認める" in text):
            return "4. 例外・緩和規定（同意による例外許可）"

        # 1. 義務規定（優先的にチェック）
        if "同意" in text or "協定" in text or "承諾" in text:
            if "得なければならない" in text or "締結しなければならない" in text or "徴さなければならない" in text:
                return "1. 義務規定（同意・協定の必須化）"
            if "してはならない" in text:
                return "1. 義務規定（同意・協定の必須化）"
            if "許可" in text and ("要件" in text or "基準" in text or "適合" in text or "認めるとき" in text):
                return "1. 義務規定（同意・協定の必須化）"

        # 2. 努力義務規定
        if "努めなければならない" in text or "努めるものとする" in text or "努力義務" in text:
            if "同意" in text or "理解" in text or "協定" in text:
                return "2. 努力義務規定（同意・理解の努力）"
        if "理解を得るとともに" in text:
             return "2. 努力義務規定（同意・理解の努力）"

        # 3. 手続き規定
        if "同意書" in text or "承諾書" in text or "協定書" in text:
            if "添付" in text or "提出" in text or "届出" in text or "添えて" in text:
                return "3. 手続き規定（同意書等の提出・添付）"
        if "同意" in text and ("状況" in text or "結果" in text) and ("報告" in text or "届出" in text):
            return "3. 手続き規定（同意書等の提出・添付）"

        return "5. その他/分類不能"

    # 条文ごとの分類適用
    print("条文ごとの分類を実行中...")
    df["unified_classification"] = df.apply(lambda row: classify_unified(row["text"]), axis=1)

    # 手動補正（条文単位）
    def refine_classification(row):
        cls = row["unified_classification"]
        text = str(row["text"])
        if cls == "3. 手続き規定（同意書等の提出・添付）":
            if "全員" in text or "3分の2" in text or "過半数" in text:
                return "1. 義務規定（同意・協定の必須化）"
        return cls

    df["clause_classification"] = df.apply(refine_classification, axis=1)

    # ---------------------------------------------------------
    # 2. 自治体単位の集約ロジック (Municipality-level Aggregation)
    # ---------------------------------------------------------
    print("自治体ごとの集約（名寄せ）を実行中...")

    # 優先順位の定義（数字が小さいほど強い規制＝優先される）
    rank_map = {
        "1. 義務規定（同意・協定の必須化）": 1,
        "2. 努力義務規定（同意・理解の努力）": 2,
        "3. 手続き規定（同意書等の提出・添付）": 3,
        "4. 例外・緩和規定（同意による例外許可）": 4,
        "5. その他/分類不能": 5
    }

    # 集約関数
    def get_municipality_class(series):
        current_rank = 99
        current_class = "5. その他/分類不能"
        
        for cls in series:
            rank = rank_map.get(cls, 99)
            if rank < current_rank:
                current_rank = rank
                current_class = cls
        return current_class

    # 自治体ごとにグループ化して、最も強い規制を抽出
    municipality_df = df.groupby("municipality_name")["clause_classification"].apply(get_municipality_class).reset_index()
    municipality_df.columns = ["municipality_name", "municipality_classification"]

    # ---------------------------------------------------------
    # 3. レポート出力
    # ---------------------------------------------------------
    output = io.StringIO()
    output.write("# 条例同意規定の統廃合・再分類レポート\n\n")
    output.write("条文ごとの判定に加え、自治体ごとに「最も強い規制」を代表値とする集約を行いました。\n\n")

    # --- 集計テーブル ---
    m_counts = municipality_df["municipality_classification"].value_counts().sort_index()
    
    output.write("## 1. 自治体単位の分類集計（ユニークカウント）\n")
    output.write("各自治体が保有する条文の中で、最も規制強度が強いものをその自治体の分類としています。\n")
    output.write(f"**分析対象自治体数（総計）:** {len(municipality_df)}\n\n")
    
    output.write("| 最終分類（自治体ベース） | 自治体数 | 構成比 |\n")
    output.write("| :--- | :---: | :---: |\n")
    for idx, count in m_counts.items():
        ratio = (count / len(municipality_df)) * 100
        output.write(f"| {idx} | {count} | {ratio:.1f}% |\n")

    # --- 詳細リスト ---
    output.write("\n## 2. 分類別 自治体一覧\n")
    
    # 分類順にソートするためのリスト
    sorted_classes = sorted(m_counts.index.tolist())

    for cls_name in sorted_classes:
        # その分類に該当する自治体リストを取得
        m_list = sorted(municipality_df[municipality_df["municipality_classification"] == cls_name]["municipality_name"].tolist())
        
        output.write(f"### {cls_name}\n")
        output.write(f"**該当数:** {len(m_list)}\n\n")
        output.write(f"> {', '.join(m_list)}\n\n")
        
        # 参考: その分類に該当した代表的な条文を元データから引いてくる
        output.write("**この分類の代表的な条文例:**\n")
        # 元データから、この分類の自治体の条文で、かつその分類に合致する条文を抽出
        matching_texts = df[
            (df["municipality_name"].isin(m_list)) & 
            (df["clause_classification"] == cls_name)
        ]["text"]
        sample_size = min(3, len(matching_texts))
        sample_texts = matching_texts.sample(sample_size, random_state=42).values if sample_size > 0 else []
        
        for text in sample_texts:
            display_text = text[:150] + "..." if len(text) > 150 else text
            output.write(f"- {display_text}\n")
        output.write("\n---\n\n")

    # ファイル保存
    output_filename = "unified_classification_report.md"
    with open(output_filename, "w", encoding="utf-8") as f:
        f.write(output.getvalue())

    print(f"分析完了: '{output_filename}' に自治体単位の集計結果を保存しました。")

    # ---------------------------------------------------------
    # 4. CSV出力（自治体名, 分類, 制定年, 条文1, 条文2, ...）
    # ---------------------------------------------------------
    print("CSV出力を作成中...")

    # 自治体ごとに条文と制定年をまとめる
    csv_rows = []
    
    for municipality in municipality_df["municipality_name"].unique():
        # その自治体の分類を取得
        m_class = municipality_df[municipality_df["municipality_name"] == municipality]["municipality_classification"].values[0]
        
        # その自治体の条文データを取得
        m_data = df[df["municipality_name"] == municipality]
        
        # 制定年（最も古い年を使用、または複数年がある場合は最も代表的なもの）
        year = m_data["year"].min() if "year" in m_data.columns else ""
        
        # 条文をリストで取得（dan_number順にソート）
        texts = m_data.sort_values("dan_number")["text"].tolist()
        
        # 行データを作成
        row = {
            "自治体名": municipality,
            "分類": m_class,
            "制定年": year
        }
        
        # 条文を動的に追加
        for i, text in enumerate(texts, 1):
            row[f"条文{i}"] = text
        
        csv_rows.append(row)
    
    # DataFrameに変換
    csv_df = pd.DataFrame(csv_rows)
    
    # 列の順序を整理（自治体名、分類、制定年を先頭に）
    base_cols = ["自治体名", "分類", "制定年"]
    text_cols = [col for col in csv_df.columns if col.startswith("条文")]
    text_cols_sorted = sorted(text_cols, key=lambda x: int(x.replace("条文", "")))
    csv_df = csv_df[base_cols + text_cols_sorted]
    
    # CSV保存
    csv_output_filename = "unified_classification_result.csv"
    csv_df.to_csv(csv_output_filename, index=False, encoding="utf-8-sig")
    
    print(f"CSV出力完了: '{csv_output_filename}' に保存しました。（{len(csv_df)}自治体）")

if __name__ == "__main__":
    main()