from __future__ import annotations

from datetime import date
from pathlib import Path
import re

__all__ = ["make_dated_versioned_path"]


def make_dated_versioned_path(directory: Path, prefix: str, suffix: str) -> Path:
    """
    ディレクトリ内の既存ファイルを見て、
    今日の日付 + 連番で一意なファイルパスを返す。

    出力名の形: "{prefix}{YYYY-MM-DD}.v.{N}{suffix}"

    - directory: 出力ディレクトリ
    - prefix:    先頭に付ける接頭語（例: "main4.3_" や "regulation_text_"）
    - suffix:    拡張子（例: ".csv"）

    例:
        make_dated_versioned_path(Path("out"), "regulation_text_", ".csv")
        -> out/regulation_text_2025-11-15.v.1.csv  （存在すれば .v.2 へ）
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)

    today_str = date.today().strftime("%Y-%m-%d")

    # 既存ファイルの最大連番を探索
    pattern = re.compile(
        r"^" + re.escape(prefix) + re.escape(today_str) + r"\.v\.(\d+)" + re.escape(suffix) + r"$"
    )

    max_n = 0
    for p in directory.iterdir():

        m = pattern.match(p.name)
        if m:
            try:
                n = int(m.group(1))
                if n > max_n:
                    max_n = n
            except ValueError:
                continue

    next_n = max_n + 1 if max_n > 0 else 1
    return directory / f"{prefix}{today_str}.v.{next_n}{suffix}"

