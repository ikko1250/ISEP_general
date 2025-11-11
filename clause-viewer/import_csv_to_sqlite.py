import sqlite3
import pandas as pd
from pathlib import Path
from tqdm import tqdm

# --- 設定 ---
BASE_DIR = Path('/home/ubuntu/cur/isep')
DB_PATH = BASE_DIR / 'clause-viewer/clause_data.db'
MAIN_CSV_PATH = BASE_DIR / 'main4.3.csv'
CODING_CSV_PATH = BASE_DIR / 'munic._coding.v.4.csv'
ANALYSIS_CSV_PATH = BASE_DIR / 'result_solar_rule_v1.1.csv'

def import_municipalities(conn):
    """自治体データをインポート"""
    cursor = conn.cursor()
    print("\n[1/4] 自治体マスタをインポート中...")

    # --- main4.3.csvから全ての自治体名を先に登録 ---
    df_main = pd.read_csv(MAIN_CSV_PATH)
    all_municipalities = df_main['自治体'].unique()
    
    cursor.executemany("INSERT OR IGNORE INTO municipalities (name) VALUES (?)", [(name,) for name in all_municipalities])
    conn.commit()
    print(f"  - {len(all_municipalities)}自治体の基礎情報を登録しました。")

    # --- result_solar_rule_v1.1.csvから分析結果を読み込み、UPDATE ---
    df_analysis = pd.read_csv(ANALYSIS_CSV_PATH)
    
    update_data = []
    for _, row in df_analysis.iterrows():
        update_data.append((
            row['ケース数'],
            row['規制タイプ'],
            row['区域類型'],
            row['禁止区域比率'],
            row['厳格度(絶対)'],
            row['厳格度(相対)'],
            row['プロセス重視度'],
            row['厳格度スコア(正規化)'],
            row['住民参加(正規化)'],
            row['手続き(正規化)'],
            row['自治体']
        ))

    cursor.executemany("""
        UPDATE municipalities SET
            cases_count = ?,
            regulation_type = ?,
            area_type = ?,
            prohibited_area_ratio = ?,
            strictness_absolute = ?,
            strictness_relative = ?,
            process_emphasis = ?,
            strictness_score = ?,
            participation_score = ?,
            procedure_score = ?
        WHERE name = ?
    """, update_data)
    conn.commit()
    print(f"  ✓ {len(df_analysis)}自治体の分析情報を更新しました。")

def import_coding_types(conn):
    """コーディング種別をインポート"""
    cursor = conn.cursor()
    print("\n[2/4] コーディング種別をインポート中...")
    
    # ヘッダーからコーディング種別を取得 (先頭6列は除く)
    coding_columns = pd.read_csv(CODING_CSV_PATH, nrows=0).columns[6:]
    
    cursor.executemany("INSERT OR IGNORE INTO coding_types (code) VALUES (?)", [(code,) for code in coding_columns])
    conn.commit()
    print(f"  ✓ {len(coding_columns)}種類のコーディング種別を登録しました。")

def import_paragraphs_and_codings(conn):
    """段落データとコーディング詳細をインポート"""
    cursor = conn.cursor()
    print("\n[3/4] 段落データとコーディング詳細をインポート中...")

    # --- 事前にマスタデータをメモリにロード ---
    municipality_map = {name: id for id, name in cursor.execute("SELECT id, name FROM municipalities")}
    coding_type_map = {code: id for id, code in cursor.execute("SELECT id, code FROM coding_types")}
    
    # --- CSVファイルを読み込み ---
    df_main = pd.read_csv(MAIN_CSV_PATH)
    df_coding = pd.read_csv(CODING_CSV_PATH)
    # 型を明示して検索時の不一致を防ぐ
    if 'h5' in df_coding.columns:
        df_coding['h5'] = pd.to_numeric(df_coding['h5'], errors='coerce').astype('Int64')
    if 'dan' in df_coding.columns:
        df_coding['dan'] = pd.to_numeric(df_coding['dan'], errors='coerce').astype('Int64')

    paragraph_codings_data = []
    total_paragraphs = 0
    total_codings = 0

    # --- データを行ごとに処理 ---
    # h5は 1-indexed, pandasのindexは 0-indexed なので調整
    for index, main_row in tqdm(df_main.iterrows(), total=len(df_main), desc="段落・コーディング処理"):
        h5 = index + 1
        municipality_name = main_row['自治体']
        municipality_id = municipality_map.get(municipality_name)
        
        if municipality_id is None:
            continue

        # '本文'列のテキストを改行で分割して段落リストを作成
        # 文字列でない場合を考慮し、str()でキャストし、splitlines()で改行分割
        paragraphs_text = str(main_row['本文']).splitlines()

        for dan_number, text in enumerate(paragraphs_text, 1):
            text = text.strip()
            if not text:
                continue

            # paragraphsテーブルに1段落ずつ挿入
            cursor.execute("""
                INSERT INTO paragraphs (h5, municipality_id, year, category, dan_number, text)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (h5, municipality_id, main_row['制定年'], main_row['区分'], dan_number, text))
            
            paragraph_id = cursor.lastrowid
            total_paragraphs += 1

            # --- 対応するコーディングデータを検索して紐付け ---
            # coding.csvのh5は1-indexed
            # h5 と 段落番号(dan) で一致する行のみ抽出
            coding_row = df_coding[(df_coding['h5'] == h5) & (df_coding['dan'] == dan_number)]
            if not coding_row.empty:
                row = coding_row.iloc[0]
                # coding_type_mapに含まれる列のみを対象にする
                for code, coding_id in coding_type_map.items():
                    if code in df_coding.columns:
                        val = row[code]
                        # 1/True/"1" 相当をコード有りとして扱う
                        if pd.notna(val) and (val == 1 or val is True or str(val).strip() == '1'):
                            paragraph_codings_data.append((paragraph_id, coding_id))
                            total_codings += 1

    # --- コーディングデータをまとめて挿入 ---
    if paragraph_codings_data:
        cursor.executemany(
            "INSERT OR IGNORE INTO paragraph_codings (paragraph_id, coding_type_id) VALUES (?, ?)",
            paragraph_codings_data
        )

    conn.commit()
    print(f"  ✓ {total_paragraphs}件の段落データを登録しました。")
    print(f"  ✓ {total_codings}件のコーディング情報を紐付けました。")
    
def main():
    """メイン処理"""
    print("=" * 60)
    print("CSVデータインポート開始")
    print("=" * 60)

    try:
        conn = sqlite3.connect(DB_PATH)
        
        import_municipalities(conn)
        import_coding_types(conn)
        import_paragraphs_and_codings(conn)

    except sqlite3.Error as e:
        print(f"データベースエラー: {e}")
    finally:
        if conn:
            conn.close()

    db_size = DB_PATH.stat().st_size / 1024 / 1024
    print("\n" + "=" * 60)
    print(f"完了! データベース: {DB_PATH.name} ({db_size:.2f} MB)")
    print("=" * 60)

if __name__ == '__main__':
    main()
