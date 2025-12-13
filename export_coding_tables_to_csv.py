#!/usr/bin/env python3
"""
paragraphs_by_coding.dbの各テーブルをCSVファイルとして出力するスクリプト

使用方法:
  python export_coding_tables_to_csv.py              # 全テーブルを出力
  python export_coding_tables_to_csv.py TABLE_NAME   # 特定テーブルのみ出力
  python export_coding_tables_to_csv.py --list       # テーブル一覧を表示
"""

import sqlite3
import csv
import sys
from pathlib import Path

# パス設定
DB_PATH = Path("/home/ubuntu/cur/isep/clause-viewer/paragraphs_by_coding.db")
OUTPUT_DIR = Path("/home/ubuntu/cur/isep/clause-viewer/csv_by_coding")


def get_all_tables(conn: sqlite3.Connection) -> list:
    """
    全テーブル名を取得（_summaryと内部テーブルを除く）
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' 
        AND name NOT LIKE 'sqlite_%'
        ORDER BY name
    """)
    return [row[0] for row in cursor.fetchall()]


def get_table_info(conn: sqlite3.Connection, table_name: str) -> list:
    """
    テーブルのカラム情報を取得
    """
    cursor = conn.cursor()
    cursor.execute(f'PRAGMA table_info("{table_name}")')
    return cursor.fetchall()


def export_table_to_csv(conn: sqlite3.Connection, table_name: str, output_dir: Path) -> int:
    """
    テーブルをCSVファイルとして出力
    
    Returns:
        出力された行数
    """
    cursor = conn.cursor()
    
    # カラム名を取得
    columns = get_table_info(conn, table_name)
    column_names = [col[1] for col in columns]
    
    # データを取得
    cursor.execute(f'SELECT * FROM "{table_name}"')
    rows = cursor.fetchall()
    
    # CSVファイルに出力
    output_path = output_dir / f"{table_name}.csv"
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(column_names)
        writer.writerows(rows)
    
    return len(rows)


def print_table_list(conn: sqlite3.Connection):
    """
    テーブル一覧を表示
    """
    cursor = conn.cursor()
    cursor.execute("SELECT coding_code, table_name, paragraph_count FROM _summary ORDER BY coding_type_id")
    rows = cursor.fetchall()
    
    print("=" * 70)
    print(f"{'コーディング':<40} {'テーブル名':<25} {'件数':>8}")
    print("=" * 70)
    for code, table_name, count in rows:
        print(f"{code:<40} {table_name:<25} {count:>8}")
    print("=" * 70)
    print(f"合計テーブル数: {len(rows)}")


def main():
    # データベース存在確認
    if not DB_PATH.exists():
        print(f"エラー: データベースが見つかりません: {DB_PATH}")
        print("先に extract_paragraphs_by_coding.py を実行してください。")
        sys.exit(1)
    
    conn = sqlite3.connect(DB_PATH)
    
    try:
        # コマンドライン引数の処理
        if len(sys.argv) > 1:
            arg = sys.argv[1]
            
            if arg == '--list' or arg == '-l':
                print_table_list(conn)
                return
            
            # 特定テーブルのみ出力
            tables = get_all_tables(conn)
            if arg not in tables:
                print(f"エラー: テーブル '{arg}' が見つかりません。")
                print("使用可能なテーブル:")
                for t in tables:
                    print(f"  - {t}")
                sys.exit(1)
            
            target_tables = [arg]
        else:
            # 全テーブルを出力（_summaryも含む）
            target_tables = get_all_tables(conn)
        
        # 出力ディレクトリ作成
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        print(f"出力先: {OUTPUT_DIR}")
        print("-" * 60)
        
        total_rows = 0
        for table_name in target_tables:
            row_count = export_table_to_csv(conn, table_name, OUTPUT_DIR)
            total_rows += row_count
            print(f"  {table_name}.csv - {row_count:,} 行")
        
        print("-" * 60)
        print(f"完了: {len(target_tables)} ファイル, 合計 {total_rows:,} 行")
        
    finally:
        conn.close()


if __name__ == "__main__":
    main()
