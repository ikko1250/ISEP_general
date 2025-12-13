#!/usr/bin/env python3
"""
元のデータベース(clause_data4.db)からコーディングタイプ別に条文を抽出し、
新しいデータベースに格納するスクリプト

操作内容:
- 元dbのtable'paragraphs'から条文を抽出
- 抽出条件: table'coding_types'に入っているコーディングごとに、
  それを含む条文(段落)を抽出
- コーディングごとに新dbにtableを作成
- 当該段落に付与されているすべてのコーディングも表示
"""

import sqlite3
import re
from pathlib import Path

# パス設定
SOURCE_DB_PATH = Path("/home/ubuntu/cur/isep/clause-viewer/clause_data4.db")
OUTPUT_DB_PATH = Path("/home/ubuntu/cur/isep/clause-viewer/paragraphs_by_coding.db")


def sanitize_table_name(code: str) -> str:
    """
    コーディング名をSQLiteのテーブル名として有効な形式に変換
    """
    # 先頭の*や＊を除去
    name = re.sub(r'^[*＊]+', '', code)
    # 英数字とアンダースコア以外を除去
    name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    # 先頭が数字の場合はプレフィックスを追加
    if name and name[0].isdigit():
        name = 'T_' + name
    # 空の場合はデフォルト名
    if not name:
        name = 'unknown_coding'
    return name


def get_all_coding_types(conn: sqlite3.Connection) -> list:
    """
    全てのコーディングタイプを取得
    """
    cursor = conn.cursor()
    cursor.execute("SELECT id, code, description FROM coding_types ORDER BY id")
    return cursor.fetchall()


def get_paragraphs_with_coding(conn: sqlite3.Connection, coding_type_id: int) -> list:
    """
    特定のコーディングを持つ段落を取得
    """
    cursor = conn.cursor()
    query = """
    SELECT DISTINCT
        p.id,
        p.h5,
        m.name AS municipality_name,
        p.year,
        p.category,
        p.dan_number,
        p.text
    FROM paragraphs p
    JOIN municipalities m ON p.municipality_id = m.id
    JOIN paragraph_codings pc ON p.id = pc.paragraph_id
    WHERE pc.coding_type_id = ?
    ORDER BY m.name, p.dan_number
    """
    cursor.execute(query, (coding_type_id,))
    return cursor.fetchall()


def get_all_codings_for_paragraph(conn: sqlite3.Connection, paragraph_id: int) -> str:
    """
    特定の段落に付与されている全てのコーディングを取得
    """
    cursor = conn.cursor()
    query = """
    SELECT ct.code
    FROM paragraph_codings pc
    JOIN coding_types ct ON pc.coding_type_id = ct.id
    WHERE pc.paragraph_id = ?
    ORDER BY ct.code
    """
    cursor.execute(query, (paragraph_id,))
    codings = [row[0] for row in cursor.fetchall()]
    return ', '.join(codings)


def create_coding_table(output_conn: sqlite3.Connection, table_name: str):
    """
    コーディング用のテーブルを作成
    """
    cursor = output_conn.cursor()
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS "{table_name}" (
        id INTEGER PRIMARY KEY,
        original_paragraph_id INTEGER,
        h5 INTEGER,
        municipality_name TEXT,
        year TEXT,
        category TEXT,
        dan_number INTEGER,
        text TEXT,
        all_codings TEXT
    )
    """)
    output_conn.commit()


def insert_paragraphs(output_conn: sqlite3.Connection, table_name: str, 
                      paragraphs: list, source_conn: sqlite3.Connection):
    """
    段落データをテーブルに挿入
    """
    cursor = output_conn.cursor()
    for para in paragraphs:
        para_id, h5, municipality_name, year, category, dan_number, text = para
        all_codings = get_all_codings_for_paragraph(source_conn, para_id)
        
        cursor.execute(f"""
        INSERT INTO "{table_name}" 
        (original_paragraph_id, h5, municipality_name, year, category, dan_number, text, all_codings)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (para_id, h5, municipality_name, year, category, dan_number, text, all_codings))
    
    output_conn.commit()


def create_summary_table(output_conn: sqlite3.Connection, summary_data: list):
    """
    サマリーテーブルを作成
    """
    cursor = output_conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS _summary (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        coding_type_id INTEGER,
        coding_code TEXT,
        coding_description TEXT,
        table_name TEXT,
        paragraph_count INTEGER
    )
    """)
    
    for item in summary_data:
        cursor.execute("""
        INSERT INTO _summary (coding_type_id, coding_code, coding_description, table_name, paragraph_count)
        VALUES (?, ?, ?, ?, ?)
        """, item)
    
    output_conn.commit()


def main():
    print(f"元データベース: {SOURCE_DB_PATH}")
    print(f"出力データベース: {OUTPUT_DB_PATH}")
    print("-" * 60)
    
    # 出力DBが存在する場合は削除
    if OUTPUT_DB_PATH.exists():
        OUTPUT_DB_PATH.unlink()
        print("既存の出力データベースを削除しました。")
    
    # データベース接続
    source_conn = sqlite3.connect(SOURCE_DB_PATH)
    output_conn = sqlite3.connect(OUTPUT_DB_PATH)
    
    try:
        # 全コーディングタイプを取得
        coding_types = get_all_coding_types(source_conn)
        print(f"コーディングタイプ数: {len(coding_types)}")
        print("-" * 60)
        
        summary_data = []
        
        for coding_id, code, description in coding_types:
            # テーブル名を生成
            table_name = sanitize_table_name(code)
            
            # 該当する段落を取得
            paragraphs = get_paragraphs_with_coding(source_conn, coding_id)
            paragraph_count = len(paragraphs)
            
            if paragraph_count > 0:
                # テーブル作成
                create_coding_table(output_conn, table_name)
                
                # データ挿入
                insert_paragraphs(output_conn, table_name, paragraphs, source_conn)
                
                print(f"[{coding_id:2d}] {code}")
                print(f"     テーブル名: {table_name}")
                print(f"     段落数: {paragraph_count}")
            else:
                print(f"[{coding_id:2d}] {code} - 該当段落なし")
            
            # サマリーデータに追加
            summary_data.append((coding_id, code, description, table_name, paragraph_count))
        
        # サマリーテーブル作成
        create_summary_table(output_conn, summary_data)
        print("-" * 60)
        print("サマリーテーブル '_summary' を作成しました。")
        
        print("-" * 60)
        print(f"処理完了: {OUTPUT_DB_PATH}")
        
    finally:
        source_conn.close()
        output_conn.close()


if __name__ == "__main__":
    main()
