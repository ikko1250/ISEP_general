import sqlite3
from pathlib import Path
import os

def setup_database():
    """
    データベースファイルとテーブルを作成します。
    """
    db_dir = Path('/home/ubuntu/cur/isep/clause-viewer')
    db_path = db_dir / 'clause_data.db'
    
    # ディレクトリが存在しない場合は作成
    db_dir.mkdir(exist_ok=True)

    # データベースが既に存在する場合は削除して再作成
    if db_path.exists():
        os.remove(db_path)
        print(f"既存のデータベースを削除しました: {db_path}")

    print(f"データベースを新規作成します: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 自治体マスタ
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS municipalities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        name_eng TEXT,
        cases_count INTEGER,
        regulation_type TEXT,
        area_type TEXT,
        prohibited_area_ratio REAL,
        strictness_absolute TEXT,
        strictness_relative TEXT,
        process_emphasis TEXT,
        strictness_score REAL,
        participation_score REAL,
        procedure_score REAL
    )
    """)
    print("  - テーブル 'municipalities' を作成しました。")

    # コーディング種別マスタ
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS coding_types (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT NOT NULL UNIQUE,
        description TEXT
    )
    """)
    print("  - テーブル 'coding_types' を作成しました。")

    # 段落データ
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS paragraphs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        h5 INTEGER,
        municipality_id INTEGER,
        year TEXT,
        category TEXT,
        dan_number INTEGER,
        text TEXT,
        FOREIGN KEY (municipality_id) REFERENCES municipalities(id)
    )
    """)
    print("  - テーブル 'paragraphs' を作成しました。")

    # コーディング詳細
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS paragraph_codings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        paragraph_id INTEGER,
        coding_type_id INTEGER,
        FOREIGN KEY (paragraph_id) REFERENCES paragraphs(id),
        FOREIGN KEY (coding_type_id) REFERENCES coding_types(id),
        UNIQUE(paragraph_id, coding_type_id)
    )
    """)
    print("  - テーブル 'paragraph_codings' を作成しました。")

    # インデックス作成
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_paragraphs_municipality ON paragraphs(municipality_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_paragraph_codings_paragraph ON paragraph_codings(paragraph_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_paragraph_codings_coding ON paragraph_codings(coding_type_id)")
    print("  - インデックスを作成しました。")

    conn.commit()
    conn.close()
    print(f"\nデータベースのセットアップが完了しました。")

if __name__ == '__main__':
    setup_database()
