import sqlite3
from pathlib import Path
from typing import Optional
import pandas as pd

# 設定
BASE_DIR = Path('/home/ubuntu/cur/isep')
DB_PATH = BASE_DIR / 'clause-viewer/clause_data4.db'
BUN_CSV_PATH = BASE_DIR / 'bun_vs_coding_v.7.csv'

TARGET_COL = '*CLAUSE_STAKEHOLDER_CONFIRMATION'
AGG_CODE = '*CSC_bun'


def ensure_coding_type(conn, code: str, description: Optional[str] = None) -> int:
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO coding_types (code, description) VALUES (?, ?)",
        (code, description),
    )
    conn.commit()
    cur.execute("SELECT id FROM coding_types WHERE code = ?", (code,))
    row = cur.fetchone()
    if not row:
        raise RuntimeError(f"coding_types にコードが見つかりませんでした: {code}")
    return row[0]


def load_bun_flags(path: Path) -> pd.DataFrame:
    """bun単位CSVから (h5, dan) ごとにフラグを集計して返す。"""
    df = pd.read_csv(path)

    # 必須列の存在確認
    for col in ['h5', 'dan', TARGET_COL]:
        if col not in df.columns:
            raise ValueError(f"列が見つかりません: {col}")

    # 型をそろえる
    df['h5'] = pd.to_numeric(df['h5'], errors='coerce').astype('Int64')
    df['dan'] = pd.to_numeric(df['dan'], errors='coerce').astype('Int64')

    # 真理値化: 1/True/"1" 相当を True とみなす
    def as_flag(v):
        if pd.isna(v):
            return False
        if isinstance(v, (int, float)):
            return int(v) == 1
        s = str(v).strip()
        return s == '1' or s.lower() == 'true'

    flags = df[['h5', 'dan', TARGET_COL]].copy()
    flags['flag'] = flags[TARGET_COL].map(as_flag)

    # (h5, dan) 単位で1つでも出現があれば True
    agg = (
        flags.groupby(['h5', 'dan'], dropna=False)['flag']
        .any()
        .reset_index()
    )
    # Intへ戻す（1/0）
    agg['flag'] = agg['flag'].astype(int)
    return agg


def apply_csc_bun():
    print("=" * 60)
    print("[bun→paragraph] *CSC_bun の集計と反映を開始")
    print("=" * 60)

    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()

        # コード種別を確保
        csc_bun_id = ensure_coding_type(
            conn,
            AGG_CODE,
            description="Sentence-level CLAUSE_STAKEHOLDER_CONFIRMATION aggregated to paragraph",
        )

        # bunレベルのフラグ集計
        agg = load_bun_flags(BUN_CSV_PATH)
        print(f"  - bun集計行数: {len(agg)}")

        # paragraphs から (h5, dan_number)→id の索引を作成
        cur.execute("SELECT id, h5, dan_number FROM paragraphs")
        para_index = {}
        for pid, h5, dan in cur.fetchall():
            para_index[(int(h5) if h5 is not None else None, int(dan) if dan is not None else None)] = pid

        # 反映する (paragraph_id, coding_type_id) を作成
        pairs = []
        missing = 0
        count_true = 0
        for _, row in agg.iterrows():
            if int(row['flag']) != 1:
                continue
            key = (int(row['h5']) if pd.notna(row['h5']) else None, int(row['dan']) if pd.notna(row['dan']) else None)
            pid = para_index.get(key)
            if pid is None:
                missing += 1
                continue
            pairs.append((pid, csc_bun_id))
            count_true += 1

        # 一括挿入（重複は無視）
        if pairs:
            cur.executemany(
                "INSERT OR IGNORE INTO paragraph_codings (paragraph_id, coding_type_id) VALUES (?, ?)",
                pairs,
            )
            conn.commit()

        print(f"  ✓ *CSC_bun 付与段落数: {count_true}")
        if missing:
            print(f"  ! 対応する段落が見つからない集計キー数: {missing}")

    finally:
        conn.close()
        size_mb = DB_PATH.stat().st_size / 1024 / 1024
        print("\n完了: データベース更新済み ({:.2f} MB)".format(size_mb))


if __name__ == '__main__':
    apply_csc_bun()
