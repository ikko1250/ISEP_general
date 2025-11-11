import sqlite3
import json
import pandas as pd
from pathlib import Path
from datetime import datetime
from tqdm import tqdm

# --- 設定 ---
BASE_DIR = Path('/home/ubuntu/cur/isep')
DB_PATH = BASE_DIR / 'clause-viewer/clause_data.db'
OUTPUT_JSON_PATH = BASE_DIR / 'clause-viewer/data-integrated.json'

def query_db(conn, sql, params=()):
    """汎用的なデータベースクエリ実行関数"""
    return conn.execute(sql, params).fetchall()

def get_all_municipalities(conn):
    """自治体リストを取得"""
    print("[1/5] 自治体リスト取得...")
    rows = query_db(conn, "SELECT name FROM municipalities ORDER BY name")
    names = [row[0] for row in rows]
    print(f"  ✓ {len(names)}自治体")
    return names

def get_all_coding_types(conn):
    """コーディング種別リストを取得"""
    print("\n[2/5] コーディング種別取得...")
    rows = query_db(conn, "SELECT code FROM coding_types ORDER BY id")
    codes = [row[0] for row in rows]
    print(f"  ✓ {len(codes)}種類")
    return codes

def get_municipality_info(conn):
    """自治体ごとの詳細情報を取得"""
    print("\n[3/5] 自治体情報取得...")
    df = pd.read_sql_query("SELECT * FROM municipalities", conn)
    
    # bytes型をstr型に変換
    for col in df.select_dtypes(include=['object']).columns:
        df[col] = df[col].apply(lambda x: x.decode('utf-8') if isinstance(x, bytes) else x)

    df = df.set_index('name')
    info_dict = df.where(pd.notnull(df), None).to_dict('index')
    
    for name in info_dict:
        del info_dict[name]['id']
        del info_dict[name]['name_eng']

    print(f"  ✓ {len(df[df['cases_count'].notna()])}自治体 (分析済み)")
    return info_dict, df

def get_paragraphs(conn):
    """段落データを取得"""
    print("\n[4/5] 段落データ取得...")
    sql = """
        SELECT 
            p.id,
            p.h5,
            m.name as municipality,
            p.year,
            p.category,
            p.dan_number,
            p.text,
            (SELECT GROUP_CONCAT(ct.code, '|') 
             FROM paragraph_codings pc
             JOIN coding_types ct ON pc.coding_type_id = ct.id
             WHERE pc.paragraph_id = p.id) as codes
        FROM paragraphs p
        JOIN municipalities m ON p.municipality_id = m.id
        ORDER BY p.h5, p.dan_number
    """
    
    # tqdmを使って進捗を表示
    cursor = conn.cursor()
    cursor.execute(sql)
    
    paragraphs_list = []
    # fetchall()はメモリを大量に消費する可能性があるため、イテレータとして扱う
    for row in tqdm(cursor, desc="段落データ処理"):
        codes_str = row[7]
        paragraphs_list.append({
            "id": row[0],
            "h5": row[1],
            "municipality": row[2],
            "year": row[3],
            "category": row[4],
            "dan": row[5],
            "text": row[6],
            "codes": codes_str.split('|') if codes_str else []
        })
        
    print(f"  ✓ {len(paragraphs_list)}段落")
    return paragraphs_list

def calculate_statistics(df_analysis):
    """統計情報を計算"""
    # 分析データが存在する自治体のみを対象
    df = df_analysis.dropna(subset=['cases_count']).copy()
    
    stats = {
        '規制タイプ分布': df['regulation_type'].value_counts().to_dict(),
        '区域類型分布': df['area_type'].value_counts().to_dict(),
        '厳格度_絶対分布': df['strictness_absolute'].value_counts().to_dict(),
        '厳格度_相対分布': df['strictness_relative'].value_counts().to_dict(),
        'プロセス重視度分布': df['process_emphasis'].value_counts().to_dict(),
    }
    
    # スコア系の統計情報
    score_columns = ['strictness_score', 'participation_score', 'procedure_score']
    for col in score_columns:
        # カラム名を日本語に寄せる
        stat_name = col.replace('_score', 'スコア').replace('strictness', '厳格度').replace('participation', '住民参加').replace('procedure', '手続き') + '統計'
        stats[stat_name] = {
            '平均': float(df[col].mean()),
            '中央値': float(df[col].median()),
            '最小値': float(df[col].min()),
            '最大値': float(df[col].max()),
            '標準偏差': float(df[col].std())
        }
        
    return stats

def decode_bytes_recursively(obj):
    """
    Recursively traverses a dictionary or list and decodes bytes to UTF-8 strings.
    """
    if isinstance(obj, dict):
        return {k: decode_bytes_recursively(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [decode_bytes_recursively(elem) for elem in obj]
    elif isinstance(obj, bytes):
        return obj.decode('utf-8', 'ignore') # ignore errors for robustness
    else:
        return obj

def main():
    """メイン処理"""
    print("=" * 60)
    print("JSON生成開始")
    print("=" * 60)

    try:
        conn = sqlite3.connect(f'file:{DB_PATH}?mode=ro', uri=True) # 読み取り専用で開く
        
        municipalities_list = get_all_municipalities(conn)
        coding_types_list = get_all_coding_types(conn)
        municipality_info_dict, df_analysis = get_municipality_info(conn)
        paragraphs_list = get_paragraphs(conn)
        
        statistics_dict = calculate_statistics(df_analysis)

        # 最終的なJSON構造を構築
        integrated_data = {
            "municipalities": municipalities_list,
            "coding_types": coding_types_list,
            "municipality_info": municipality_info_dict,
            "paragraphs": paragraphs_list,
            "statistics": statistics_dict,
            "metadata": {
                "version": "2.0",
                "created_at": datetime.now().isoformat(),
                "source": f"SQLite ({DB_PATH.name})",
                "total_municipalities": len(municipalities_list),
                "total_paragraphs": len(paragraphs_list)
            }
        }

        # 再帰的にbytesをstrに変換
        integrated_data = decode_bytes_recursively(integrated_data)

        # JSONファイル出力
        print("\n[5/5] JSON出力...")
        with open(OUTPUT_JSON_PATH, 'w', encoding='utf-8') as f:
            json.dump(integrated_data, f, ensure_ascii=False, indent=2)
        
        file_size = OUTPUT_JSON_PATH.stat().st_size / 1024 / 1024
        print(f"  ✓ ファイルサイズ: {file_size:.2f} MB")

    except sqlite3.Error as e:
        print(f"データベースエラー: {e}")
    finally:
        if conn:
            conn.close()

    print("\n" + "=" * 60)
    print(f"完了! {OUTPUT_JSON_PATH.name}")
    print("=" * 60)

if __name__ == '__main__':
    main()
