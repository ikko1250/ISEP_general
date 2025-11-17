#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import argparse
from pathlib import Path
from typing import Iterable, List, Tuple, Set

from bs4 import BeautifulSoup
from bs4 import NavigableString
from datetime import date

# 共通の日付+連番命名ユーティリティ
try:
    from versioning.filename import make_dated_versioned_path
except Exception:
    make_dated_versioned_path = None  # 後方互換: モジュール未作成時は従来の.vNを使用


# 「第1条」「第23条」などを検出
ARTICLE_PATTERN = re.compile(r"第\d+条")


def _clean_text(text: str) -> str:
    """余分な改行・連続空白を1つの空白にまとめる。"""
    return re.sub(r"\s+", " ", text).strip()


def extract_articles(html: str) -> List[str]:
    """
    条文テキストを条ごとにまとめて返す。

    戻り値の各要素は 1 条分で、
    その中で「各項ごとに改行」され、
    号（(1), (2), ア, イ など）は直前の項の行に続けて出力される。
    """
    soup = BeautifulSoup(html, "lxml")

    # 本文エリア（なければ全体）
    primary = soup.find("div", id="primary") or soup

    # 余計なノイズの除去（本文抽出前に実施）
    for tag in primary.find_all(["script", "style", "noscript"]):
        tag.decompose()

    # ルビ: 読み仮名(rt)を除去し、ruby容器は外す
    for rt in primary.find_all("rt"):
        rt.decompose()
    for ruby in primary.find_all("ruby"):
        ruby.unwrap()

    # 表: <table> を削除。captionがあれば直前に生テキストとして残す
    for tbl in primary.find_all("table"):
        caption_text = None
        cap = tbl.find("caption")
        if cap:
            caption_text = cap.get_text(" ", strip=True)
        if caption_text:
            tbl.insert_before(NavigableString(caption_text))
        tbl.decompose()

    elines = primary.select("div.eline")

    articles: List[str] = []
    current_paragraphs: List[str] = []  # 1条の中の各項のテキスト
    inside_article = False              # 「第○条」以降かどうかのフラグ

    for el in elines:
        # 各 eline の直下の div（article / clause / item など）だけ見る
        container = el.find("div", recursive=False)
        if container is None:
            continue

        classes = container.get("class", [])

        # --- 新しい「第○条」の行 ---
        if "article" in classes:
            article_text = container.get_text(separator="", strip=True)

            # 「第○条」を含まない article はスキップ（見出し等）
            if not ARTICLE_PATTERN.search(article_text):
                continue

            # 直前の条を flush
            if current_paragraphs:
                articles.append("\n".join(current_paragraphs))
                current_paragraphs = []

            inside_article = True

            # 第1項（実質）を1つ目の「項」として扱う
            first_para = _clean_text(article_text)
            current_paragraphs.append(first_para)
            continue

        # まだ条に入っていない部分は無視
        if not inside_article:
            continue

        # --- 各項（第2項・第3項…） ---
        if "clause" in classes:
            clause_text = container.get_text(separator="", strip=True)
            clause_text = _clean_text(clause_text)
            if clause_text:
                # 各項ごとに改行 → 新しい要素として追加
                current_paragraphs.append(clause_text)
            continue

        # --- 各号（(1), (2), ア, イ…） ---
        # 一部自治体では "subitem" 等のクラスを用いる可能性があるため併せて扱う
        if ("item" in classes) or ("subitem" in classes):
            item_text = container.get_text(separator="", strip=True)
            item_text = _clean_text(item_text)
            if item_text:
                # 号は改行せず直前の項に続けるが、号番号の直前に句点「。」を補う
                if current_paragraphs:
                    # 直前が句点で終わっていない場合に限り句点を挿入
                    if not current_paragraphs[-1].endswith("。"):
                        current_paragraphs[-1] += "。"
                    current_paragraphs[-1] += item_text
                else:
                    # 念のため、項がまだない場合は新規項として扱う（先頭には句点を置かない）
                    current_paragraphs.append(item_text)
            continue

        # --- その他の要素（念のため） ---
        other_text = container.get_text(separator="", strip=True)
        other_text = _clean_text(other_text)
        if other_text:
            if current_paragraphs:
                current_paragraphs[-1] += other_text
            else:
                current_paragraphs.append(other_text)

    # 最後の条を flush
    if current_paragraphs:
        articles.append("\n".join(current_paragraphs))

    return articles


def _extract_full_text(html: str) -> str:
    """条文抽出ロジックを用いて本文を生成する。

    - 各要素は「1条分」。
    - 各条の中では「各項ごとに改行」。
    - 号(1)(2)…は直前の項の行に続けて付与。
    """
    articles = extract_articles(html)
    return "\r\n".join(articles)


def _parse_meta_from_filename(p: Path) -> Tuple[str, str, str]:
    """ファイル名から (自治体, 自治体_eng, 区分) を推定する。

    - ファイル名例:
      - みやこ町__Miyako__Ordinance_HTML.html
      - 由布市_Ordinance_HTML.html
    - 区分は Ordinance/Regulation を日本語にマッピングする。
    """
    stem = p.stem  # 拡張子なし

    # 区分（条例/施行規則）
    if "Ordinance" in stem:
        kubun = "条例"
    elif "Regulation" in stem:
        kubun = "施行規則"
    else:
        kubun = ""

    # 自治体名と英名
    muni_jp = ""
    muni_en = ""

    if "__" in stem:
        parts = stem.split("__")
        if parts:
            muni_jp = parts[0]
        if len(parts) >= 2:
            muni_en = parts[1]
    else:
        parts = stem.split("_")
        if parts:
            muni_jp = parts[0]
        # 英名は省略されている場合があるので空にしておく

    return muni_jp, muni_en, kubun


def _iter_html_files(root: Path) -> Iterable[Tuple[Path, str]]:
    """out_html_* ディレクトリ直下の HTML を(パス, 制定年)で列挙する。"""
    for d in sorted(root.glob("out_html_*")):
        if not d.is_dir():
            continue
        # ディレクトリ名末尾の数字を制定年とみなす
        m = re.search(r"out_html_(\d{4})$", d.name)
        if not m:
            continue
        year = m.group(1)
        for fp in sorted(d.glob("*.html")):
            if fp.is_file():
                yield fp, year


def _normalize_municipality(name: str) -> str:
    """比較用に先頭の都道府県名を除去して正規化する。

    例: "静岡県東伊豆町" → "東伊豆町", "東京都八王子市" → "八王子市"
    """
    m = re.match(r"^(?:.+?[都道府県])(.*)$", name)
    if m:
        return m.group(1)
    return name


def _next_versioned_path(base: Path) -> Path:
    """既存ファイルを上書きせず、.vN 付きのパスを返す。"""
    if not base.exists():
        return base
    n = 1
    while True:
        candidate = base.with_name(f"{base.stem}.v{n}{base.suffix}")
        if not candidate.exists():
            return candidate
        n += 1


def main():
    parser = argparse.ArgumentParser(
        description=(
            "out_html_* のHTMLを全件処理し、"
            "オリジナル(main4.3.csv)も取り込んで重複は新HTMLを優先で統合出力"
        )
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="検索ルートディレクトリ（デフォルト: カレントディレクトリ）",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("main4.3.csv"),
        help="出力CSVのベースファイル名（既存時は .vN を付けて保存）",
    )
    parser.add_argument(
        "--original",
        type=Path,
        default=Path("main4.3.csv"),
        help="統合対象とする既存CSV(オリジナル)へのパス。存在しなければ無視",
    )
    args = parser.parse_args()

    root: Path = args.root

    rows: List[dict] = []
    valid_new_keys: Set[Tuple[str, str, str]] = set()
    fallback_keys: List[Tuple[str, str, str]] = []
    new_total = 0
    new_valid = 0
    for fp, year in _iter_html_files(root):
        new_total += 1
        muni_jp, muni_en, kubun = _parse_meta_from_filename(fp)
        k = (year, muni_jp, kubun)
        k_norm = (year, _normalize_municipality(muni_jp), kubun)
        try:
            html = fp.read_text(encoding="utf-8", errors="ignore")
            text = _extract_full_text(html)
            # 空や極端に短い場合は不正とみなす → オリジナルへフォールバック
            if not text or not text.strip():
                fallback_keys.append(k)
                continue
            rows.append(
                {
                    "本文": text,
                    "制定年": year,
                    "自治体": muni_jp,
                    "自治体_eng": muni_en,
                    "区分": kubun,
                }
            )
            # 重複判定は正規化した自治体名で行う
            valid_new_keys.add(k_norm)
            new_valid += 1
        except Exception:
            # 解析エラー時もオリジナルへフォールバック
            fallback_keys.append(k)

    # 新HTMLからのキー集合（新を優先）
    def _key(d: dict) -> Tuple[str, str, str]:
        return (d.get("制定年", ""), _normalize_municipality(d.get("自治体", "")), d.get("区分", ""))

    # オリジナル(main4.3.csv)の取り込み（新HTMLと重複するキーはスキップ）
    if args.original.exists():
        import csv
        with args.original.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            # ヘッダが想定通りでない場合でも、必要列があれば処理を続行
            for o in reader:
                k = (o.get("制定年", ""), _normalize_municipality(o.get("自治体", "")), o.get("区分", ""))
                # 新HTMLで有効データがある場合はスキップ（新優先）
                if k in valid_new_keys:
                    continue  # 新HTML由来を優先
                # 欠損キーを埋める（存在しない列は空文字）
                rows.append(
                    {
                        "本文": o.get("本文", ""),
                        "制定年": o.get("制定年", ""),
                        "自治体": o.get("自治体", ""),
                        "自治体_eng": o.get("自治体_eng", ""),
                        "区分": o.get("区分", ""),
                    }
                )

    # 出力先（デフォルトは「当日付+連番」方式の別名保存）
    # args.output がファイルパス指定の場合: そのディレクトリ/拡張子を利用し、
    # ベース名(stem)を prefix として日付+連番を付与した新名称を採用する。
    out_dir = args.output.parent if args.output.suffix else Path.cwd()
    base_stem = args.output.stem if args.output.suffix else (args.output.name or "output")
    suffix = args.output.suffix if args.output.suffix else ".csv"

    if make_dated_versioned_path is not None:
        out_path = make_dated_versioned_path(out_dir, base_stem + "_", suffix)
    else:
        # フォールバック: 旧式 .vN 連番
        desired = out_dir / f"{base_stem}{suffix}"
        out_path = _next_versioned_path(desired)

    # CSV 書き出し
    import csv

    fieldnames = ["本文", "制定年", "自治体", "自治体_eng", "区分"]
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"処理件数(新HTML+オリジナル統合): {len(rows)} 件")
    print(f"新HTML: {new_total} 件 中 有効 {new_valid} 件 / フォールバック {len(fallback_keys)} 件")
    print(f"CSVを書き出しました: {out_path}")


if __name__ == "__main__":
    main()
