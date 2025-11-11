import sqlite3
import json
import pandas as pd
from pathlib import Path
from datetime import datetime
from tqdm import tqdm
import os

# --- 設定 ---
BASE_DIR = Path('/home/ubuntu/cur/isep')
DB_PATH = BASE_DIR / 'clause-viewer/clause_data.db'
OUTPUT_DIR = BASE_DIR / 'clause-viewer/data'
MUNICS_DIR = OUTPUT_DIR / 'municipalities'

def setup_directories():
    """出力用ディレクトリを作成"""
    OUTPUT_DIR.mkdir(exist_ok=True)
    MUNICS_DIR.mkdir(exist_ok=True)

def query_db(conn, sql, params=()):
    """汎用的なデータベースクエリ実行関数"""
    return conn.execute(sql, params).fetchall()

def get_all_municipalities(conn):
    """自治体リストを取得"""
    print("[1/4] 自治体リスト取得...")
    rows = query_db(conn, "SELECT name FROM municipalities ORDER BY name")
    names = [row[0] for row in rows]
    print(f"  ✓ {len(names)}自治体")
    return names

def get_all_coding_types(conn):
    """コーディング種別リストを取得"""
    print("\n[2/4] コーディング種別取得...")
    rows = query_db(conn, "SELECT code FROM coding_types ORDER BY id")
    codes = [row[0] for row in rows]
    print(f"  ✓ {len(codes)}種類")
    return codes

def get_municipality_info(conn):
    """自治体ごとの詳細情報を取得"""
    print("\n[3/4] 自治体情報取得...")
    df = pd.read_sql_query("SELECT * FROM municipalities", conn)
    
    for col in df.select_dtypes(include=['object']).columns:
        df[col] = df[col].apply(lambda x: x.decode('utf-8') if isinstance(x, bytes) else x)

    df = df.set_index('name')
    info_dict = df.where(pd.notnull(df), None).to_dict('index')
    
    for name in info_dict:
        del info_dict[name]['id']
        del info_dict[name]['name_eng']

    print(f"  ✓ {len(df[df['cases_count'].notna()])}自治体 (分析済み)")
    return info_dict, df

def get_paragraphs_by_municipality(conn, municipality_name):
    """指定された自治体の段落データを取得"""
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
        WHERE m.name = ?
        ORDER BY p.h5, p.dan_number
    """
    
    cursor = conn.cursor()
    cursor.execute(sql, (municipality_name,))
    
    paragraphs_list = []
    for row in cursor:
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
        
    return paragraphs_list

def calculate_statistics(df_analysis):
    """統計情報を計算"""
    df = df_analysis.dropna(subset=['cases_count']).copy()
    
    stats = {
        '規制タイプ分布': df['regulation_type'].value_counts().to_dict(),
        '区域類型分布': df['area_type'].value_counts().to_dict(),
        '厳格度_絶対分布': df['strictness_absolute'].value_counts().to_dict(),
        '厳格度_相対分布': df['strictness_relative'].value_counts().to_dict(),
        'プロセス重視度分布': df['process_emphasis'].value_counts().to_dict(),
    }
    
    score_columns = ['strictness_score', 'participation_score', 'procedure_score']
    for col in score_columns:
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
        return obj.decode('utf-8', 'ignore')
    else:
        return obj

def main():
    """メイン処理"""
    print("=" * 60)
    print("JSON分割生成開始")
    print("=" * 60)

    setup_directories()

    conn = None
    try:
        conn = sqlite3.connect(f'file:{DB_PATH}?mode=ro', uri=True)
        
        municipalities_list = get_all_municipalities(conn)
        coding_types_list = get_all_coding_types(conn)
        municipality_info_dict, df_analysis = get_municipality_info(conn)
        statistics_dict = calculate_statistics(df_analysis)

        # 1. index.json の生成
        print("\n[4/4] JSONファイル分割出力中...")
        index_data = {
            "municipalities": municipalities_list,
            "coding_types": coding_types_list,
            "municipality_info": municipality_info_dict,
            "statistics": statistics_dict,
            "metadata": {
                "version": "2.1-split",
                "created_at": datetime.now().isoformat(),
                "source": f"SQLite ({DB_PATH.name})",
                "total_municipalities": len(municipalities_list),
            }
        }
        index_data = decode_bytes_recursively(index_data)
        index_path = OUTPUT_DIR / 'index.json'
        with open(index_path, 'w', encoding='utf-8') as f:
            json.dump(index_data, f, ensure_ascii=False, indent=2)
        print(f"  ✓ index.json を生成しました。")

        # 2. 自治体ごとのJSONを生成
        total_paragraphs = 0
        for munic_name in tqdm(municipalities_list, desc="自治体別JSON生成"):
            paragraphs_list = get_paragraphs_by_municipality(conn, munic_name)
            if not paragraphs_list:
                continue
            
            total_paragraphs += len(paragraphs_list)
            munic_data = decode_bytes_recursively(paragraphs_list)
            
            # ファイル名として無効な文字を置換
            safe_filename = munic_name.replace('/', '_') + '.json'
            munic_path = MUNICS_DIR / safe_filename
            
            with open(munic_path, 'w', encoding='utf-8') as f:
                json.dump(munic_data, f, ensure_ascii=False, indent=2)
        
        print(f"  ✓ {len(municipalities_list)}自治体分のJSONファイルを生成しました。")
        print(f"  - 総段落数: {total_paragraphs}")


    except sqlite3.Error as e:
        print(f"データベースエラー: {e}")
    finally:
        if conn:
            conn.close()

    print("\n" + "=" * 60)
    print(f"完了! 分割JSONを {OUTPUT_DIR} に出力しました。")
    print("=" * 60)

if __name__ == '__main__':
    main()
