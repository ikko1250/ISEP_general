#!/usr/bin/env python3
import argparse
import csv
import sqlite3
import json
import os
import re
import sys
import unicodedata
from typing import Dict, List, Optional, Tuple


VERSION = "v0.1.0"


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def load_config(path: Optional[str]) -> Dict:
    """Load YAML or JSON config. Fallback to default if unavailable."""
    default = {
        "normalize": {
            "nfkc": True,
            "collapse_spaces": True,
            "strip_brackets_notes": True,
        },
        "sudachi": {
            "enabled": True,
            "mode": "A",
            "window": 10,
        },
        "regex": {
            "include": {
                "consent_verb": [
                    "同意.?得",
                    "承諾.?得",
                    "同意書",
                    "承諾書",
                    "書面.{0,4}同意",
                    "同意.?受け",
                ],
                "residents": [
                    r"(近隣|周辺|隣接|近接|近傍|周囲)\s*(住民|居住者|世帯|区民|町民|村民)",
                ],
                "adjacent_landowner": [
                    r"(隣接|周辺|近隣|近接).*(土地|地).*(所有者|占有者|管理者)",
                ],
                "interested_party": [
                    r"利害関係(者|人)",
                ],
                "community": [
                    "自治会",
                    "町内会",
                    "自治組織",
                    "自治会長",
                ],
                "consent_docs": [
                    "同意書",
                    "承諾書",
                    "書面.{0,4}同意",
                ],
            },
            "exclude": {
                "mayor_consent": [
                    r"(市長|区長|町長|村長|知事).{0,8}(同意|承認|許可)",
                ],
                "definition": [
                    "この条例において",
                    "の定義",
                    "とは、",
                    "をいう。",
                ],
                "owner_consent": [
                    r"(土地|建物|施設|発電設備).*(所有者).*(同意|承諾)",
                ],
                "information_only": [
                    r"意見.?聴",
                    "意見聴取",
                    "意見提出",
                    "意見を求め",
                ],
                "procedural_only": [
                    "届出",
                    "通知",
                    "申請",
                    "協議",
                    "認定",
                    "許可申請",
                ],
            },
        },
        "decision": {
            "neg_overrides": ["mayor_consent", "definition", "owner_consent"],
            "require_consent_for_pos": True,
            "prefer_pos_when_weak_neg": False,
        },
    }

    if not path:
        return default

    # Support JSON directly
    _, ext = os.path.splitext(path)
    try:
        with open(path, "r", encoding="utf-8") as f:
            if ext.lower() in (".json",):
                return json.load(f)
            # Try YAML
            try:
                import yaml  # type: ignore

                return yaml.safe_load(f)
            except Exception:
                eprint("Warning: Failed to parse YAML; falling back to defaults.")
                return default
    except FileNotFoundError:
        eprint(f"Warning: config not found at {path}; using defaults.")
        return default


def compile_patterns(cfg: Dict) -> Dict:
    rx = cfg.get("regex", {})
    compiled = {"include": {}, "exclude": {}}
    for k, arr in rx.get("include", {}).items():
        compiled["include"][k] = [re.compile(p) for p in arr]
    for k, arr in rx.get("exclude", {}).items():
        compiled["exclude"][k] = [re.compile(p) for p in arr]
    return compiled


def normalize_text(s: str, cfg_norm: Dict) -> str:
    if s is None:
        return ""
    t = s
    if cfg_norm.get("nfkc", True):
        t = unicodedata.normalize("NFKC", t)
    if cfg_norm.get("strip_brackets_notes", True):
        # Remove simple notes like ※1, ※２, （注）, （注1）
        t = re.sub(r"※\s*\d+", "", t)
        t = re.sub(r"\(注\d*\)|（注\d*）", "", t)
    if cfg_norm.get("collapse_spaces", True):
        # Replace any whitespace runs with single space
        t = re.sub(r"\s+", " ", t).strip()
    return t


def any_match(patterns: List[re.Pattern], text: str) -> Tuple[bool, Optional[re.Match]]:
    for p in patterns:
        m = p.search(text)
        if m:
            return True, m
    return False, None


def try_import_sudachi():
    try:
        from sudachipy import tokenizer, dictionary
        return tokenizer, dictionary
    except Exception:
        return None, None


def sudachi_lemmas(text: str, mode: str = "A") -> List[str]:
    tokenizer, dictionary = try_import_sudachi()
    if tokenizer is None:
        return []
    obj = dictionary.Dictionary().create()
    m = {
        "A": tokenizer.Tokenizer.SplitMode.A,
        "B": tokenizer.Tokenizer.SplitMode.B,
        "C": tokenizer.Tokenizer.SplitMode.C,
    }.get(mode.upper(), tokenizer.Tokenizer.SplitMode.A)
    toks = obj.tokenize(text, m)
    lemmas = [t.dictionary_form() for t in toks]
    return lemmas


def near_window(lemmas: List[str], group_a: List[str], group_b: List[str], window: int) -> bool:
    if not lemmas:
        return False
    a_idx = [i for i, w in enumerate(lemmas) if w in group_a]
    b_idx = [i for i, w in enumerate(lemmas) if w in group_b]
    if not a_idx or not b_idx:
        return False
    for i in a_idx:
        for j in b_idx:
            if abs(i - j) <= window:
                return True
    return False


CONSENT_LEMMAS = ["同意", "承諾", "同意書", "承諾書"]
RESIDENT_LEMMAS = ["近隣", "周辺", "隣接", "近接", "近傍", "周囲", "住民", "居住者", "世帯", "区民", "町民", "村民"]
ADJ_OWNER_LEMMAS = ["隣接", "周辺", "近隣", "近接", "土地", "地", "所有者", "占有者", "管理者"]


def classify_text(
    raw_text: str,
    compiled_rx: Dict,
    cfg: Dict,
    sudachi_cache: Optional[Dict] = None,
) -> Tuple[str, Dict[str, bool], str, str]:
    t = normalize_text(raw_text, cfg.get("normalize", {}))
    flags: Dict[str, bool] = {}
    snippets: Dict[str, str] = {}

    # include
    hit, m = any_match(compiled_rx["include"].get("consent_verb", []), t)
    flags["hit_consent_verb"] = hit
    if m:
        snippets["hit_consent_verb"] = m.group(0)

    for key in [
        "residents",
        "adjacent_landowner",
        "interested_party",
        "community",
        "consent_docs",
    ]:
        hit, m = any_match(compiled_rx["include"].get(key, []), t)
        flags[f"hit_{key if key != 'residents' else 'residents'}"] = hit
        if m:
            snippets[f"hit_{key if key != 'residents' else 'residents'}"] = m.group(0)

    # exclude
    for key in [
        "mayor_consent",
        "definition",
        "owner_consent",
    ]:
        hit, m = any_match(compiled_rx["exclude"].get(key, []), t)
        flags[f"hit_{key}"] = hit
        if m:
            snippets[f"hit_{key}"] = m.group(0)

    no_consent = not flags.get("hit_consent_verb", False)
    for key in ["information_only", "procedural_only"]:
        hit = False
        match_obj = None
        if no_consent:
            hit, match_obj = any_match(compiled_rx["exclude"].get(key, []), t)
        flags[f"hit_{key}"] = hit
        if match_obj:
            snippets[f"hit_{key}"] = match_obj.group(0)

    # Sudachi proximity (optional)
    tokens_joined = ""
    if cfg.get("sudachi", {}).get("enabled", False):
        lemmas = sudachi_lemmas(t, mode=cfg.get("sudachi", {}).get("mode", "A"))
        if lemmas:
            tokens_joined = " ".join(lemmas[:200])
            win = int(cfg.get("sudachi", {}).get("window", 10))
            if near_window(lemmas, CONSENT_LEMMAS, RESIDENT_LEMMAS, win):
                flags["hit_residents"] = True
            if near_window(lemmas, CONSENT_LEMMAS, ADJ_OWNER_LEMMAS, win):
                flags["hit_adjacent_landowner"] = True

    # Decision
    dec = cfg.get("decision", {})
    neg_overrides = set(dec.get("neg_overrides", ["mayor_consent", "definition", "owner_consent"]))
    has_neg_override = any(flags.get(f"hit_{k}", False) for k in neg_overrides)
    has_neg_weak = flags.get("hit_information_only", False) or flags.get("hit_procedural_only", False)
    require_consent = bool(dec.get("require_consent_for_pos", True))

    label = "NEG"
    if has_neg_override or (has_neg_weak and not dec.get("prefer_pos_when_weak_neg", False)):
        label = "NEG"
    else:
        pos_condition = (
            (not require_consent or flags.get("hit_consent_verb", False))
            and (
                flags.get("hit_residents", False)
                or flags.get("hit_adjacent_landowner", False)
                or flags.get("hit_interested_party", False)
                or flags.get("hit_community", False)
                or flags.get("hit_consent_docs", False)
            )
        )
        if pos_condition:
            label = "POS"
        else:
            # AMB if general ambiguous terms
            if re.search(r"(合意形成|同意率|説明会)", t):
                label = "AMB"
            else:
                label = "NEG"

    reason_parts: List[str] = [label]
    pos_keys = [
        "hit_consent_verb",
        "hit_residents",
        "hit_adjacent_landowner",
        "hit_interested_party",
        "hit_community",
        "hit_consent_docs",
    ]
    neg_keys = [
        "hit_mayor_consent",
        "hit_definition",
        "hit_owner_consent",
        "hit_information_only",
        "hit_procedural_only",
    ]
    pos_hits = [k for k in pos_keys if flags.get(k, False)]
    neg_hits = [k for k in neg_keys if flags.get(k, False)]
    if pos_hits:
        reason_parts.append("POS:" + ",".join(f"{k}:{snippets.get(k, '')}" for k in pos_hits))
    if neg_hits:
        reason_parts.append("NEG:" + ",".join(f"{k}:{snippets.get(k, '')}" for k in neg_hits))
    reason = " | ".join(reason_parts)

    return label, flags, reason, tokens_joined


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Extract stakeholder consent mentions from ordinance text lines")
    ap.add_argument("--input", required=False, default="clause-viewer/stakeholder_confirmation_paragraphs.csv", help="Input CSV path (ignored if --db is set)")
    ap.add_argument("--db", required=False, default=None, help="SQLite DB path (e.g., clause-viewer/clause_data2.db)")
    ap.add_argument("--db-code", required=False, default="*CLAUSE_STAKEHOLDER_CONFIRMATION", help="Limit paragraphs to those tagged with this coding_types.code")
    ap.add_argument("--output", required=False, default="out_stakeholder_consent.csv", help="Output CSV path")
    ap.add_argument("--config", required=False, default="config.yml", help="Config file (YAML or JSON)")
    ap.add_argument("--use-sudachi", dest="use_sudachi", action="store_true", help="Enable Sudachi proximity logic")
    ap.add_argument("--no-sudachi", dest="use_sudachi", action="store_false", help="Disable Sudachi even if config enabled")
    ap.set_defaults(use_sudachi=None)
    ap.add_argument("--sudachi-mode", default=None, help="Sudachi mode A/B/C")
    ap.add_argument("--window", type=int, default=None, help="Proximity window size")
    ap.add_argument("--dump-pos", default=None, help="Optional CSV path to dump POS rows")
    ap.add_argument("--dump-amb", default=None, help="Optional CSV path to dump AMB rows")
    # Sentence/enum splitting options
    ap.add_argument("--sentence-split", action="store_true", help="Split paragraph into sentence-like units (handles digits+space and (1) enum)")
    ap.add_argument("--sentence-detailed", action="store_true", help="When splitting, output per-sentence rows instead of aggregated per paragraph")
    ap.add_argument("--include-meta", action="store_true", help="Include paragraph metadata (if available from DB/CSV) in output")
    return ap.parse_args()


def iter_texts_from_db(db_path: str, code: str):
    """Yield raw paragraph texts from SQLite filtered by coding_types.code.

    Uses the same target selection as clause-viewer/sqlite_to_html_stakeholder_confirmation.py
    but only returns paragraph text strings.
    """
    con = sqlite3.connect(db_path)
    try:
        con.row_factory = sqlite3.Row
        sql = (
            "WITH target AS (\n"
            "  SELECT p.id AS paragraph_id, p.text AS text\n"
            "  FROM paragraphs p\n"
            "  JOIN paragraph_codings pc ON pc.paragraph_id = p.id\n"
            "  JOIN coding_types ct ON ct.id = pc.coding_type_id\n"
            "  WHERE ct.code = ?\n"
            ")\n"
            "SELECT text FROM target ORDER BY paragraph_id"
        )
        cur = con.execute(sql, (code,))
        for r in cur.fetchall():
            yield r["text"] or ""
    finally:
        con.close()


def iter_rows_from_db(db_path: str, code: str):
    """Yield dict rows including text and paragraph meta from SQLite.

    Keys: paragraph_id, municipality, year, category, dan_number, text
    """
    con = sqlite3.connect(db_path)
    try:
        con.row_factory = sqlite3.Row
        sql = (
            "WITH target AS (\n"
            "  SELECT p.id AS paragraph_id, m.name AS municipality, p.year AS year,\n"
            "         p.category AS category, p.dan_number AS dan_number, p.text AS text\n"
            "  FROM paragraphs p\n"
            "  JOIN paragraph_codings pc ON pc.paragraph_id = p.id\n"
            "  JOIN coding_types ct ON ct.id = pc.coding_type_id\n"
            "  JOIN municipalities m ON m.id = p.municipality_id\n"
            "  WHERE ct.code = ?\n"
            ")\n"
            "SELECT paragraph_id, municipality, year, category, dan_number, text\n"
            "FROM target ORDER BY paragraph_id"
        )
        cur = con.execute(sql, (code,))
        for r in cur.fetchall():
            yield {
                "paragraph_id": r["paragraph_id"],
                "municipality": r["municipality"],
                "year": r["year"],
                "category": r["category"],
                "dan_number": r["dan_number"],
                "text": r["text"] or "",
            }
    finally:
        con.close()


_RX_PUNCT = re.compile(r"[。．]")
_RX_NUMERIC_PAREN = re.compile(r"(?:\(|（)\s*\d{1,3}\s*(?:\)|）)")
_RX_DIGIT_SPACE = re.compile(r"(?<=\D)\d{1,3}[\s　]")


def split_sentences_like_bullets(text: str) -> List[str]:
    """句点・数値のみ括弧・数字+空白で安定分割する。

    - 句点（。/．）の直後で分割
    - (1)/(10)/（1）など「括弧内が数字のみ」の直前で分割（括弧内は保護して内部で再分割しない）
    - 「数字+空白」（前が数字以外）の直前で分割（ただし保護括弧内は除外）
    """
    if not text:
        return []

    n = len(text)
    boundaries: set[int] = set()
    protected: list[tuple[int, int]] = []

    # 1) 句点の後（ただし直後の非空白が閉じ括弧なら分割しない）
    WS = set(" \t\r\n\u3000")
    for m in _RX_PUNCT.finditer(text):
        end = m.end()
        j = end
        while j < n and text[j] in WS:
            j += 1
        if j < n and text[j] in ")）":
            # 括弧内の句点は文末扱いにしない
            continue
        boundaries.add(end)

    # 2) 数値のみ括弧の直前 + 括弧範囲を保護
    for m in _RX_NUMERIC_PAREN.finditer(text):
        boundaries.add(m.start())
        protected.append((m.start(), m.end()))

    def _in_protected(i: int) -> bool:
        for a, b in protected:
            if a <= i < b:
                return True
        return False

    # 3) 数字+空白（非数字の後）: 保護範囲外のみ採用
    for m in _RX_DIGIT_SPACE.finditer(text):
        idx = m.start()
        if not _in_protected(idx):
            boundaries.add(idx)

    # 累積分割
    parts: List[str] = []
    last = 0
    for idx in sorted(b for b in boundaries if 0 < b < n):
        if idx <= last:
            continue
        chunk = text[last:idx].strip()
        if chunk:
            parts.append(chunk)
        last = idx
    tail = text[last:].strip()
    if tail:
        parts.append(tail)
    return parts


def main() -> int:
    args = parse_args()
    cfg = load_config(args.config)
    # Override sudachi flags from CLI if specified
    if args.use_sudachi is not None:
        cfg.setdefault("sudachi", {})["enabled"] = bool(args.use_sudachi)
    if args.sudachi_mode:
        cfg.setdefault("sudachi", {})["mode"] = args.sudachi_mode
    if args.window is not None:
        cfg.setdefault("sudachi", {})["window"] = int(args.window)

    compiled_rx = compile_patterns(cfg)

    in_path = args.input
    out_path = args.output
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

    # Prepare optional dumps
    pos_writer = None
    amb_writer = None
    pos_fp = None
    amb_fp = None

    # Columns per spec
    flag_cols = [
        "hit_consent_verb",
        "hit_residents",
        "hit_adjacent_landowner",
        "hit_interested_party",
        "hit_community",
        "hit_consent_docs",
        "hit_information_only",
        "hit_mayor_consent",
        "hit_definition",
        "hit_owner_consent",
        "hit_procedural_only",
    ]

    # 動的な列構成
    base_fields = ["text", "class", "reason"] + flag_cols + ["sudachi_tokens", "version"]
    fieldnames = list(base_fields)
    if args.sentence_split and args.sentence_detailed:
        fieldnames = ["sentence_index"] + fieldnames
    if args.include_meta:
        # 可能なら paragraph メタ情報を前に付ける
        meta_cols = ["paragraph_id", "municipality", "year", "category", "dan_number"]
        fieldnames = meta_cols + fieldnames

    total = 0
    try:
        # Open output writers
        with open(out_path, "w", encoding="utf-8", newline="") as fout:
            writer = csv.DictWriter(fout, fieldnames=fieldnames)
            writer.writeheader()

            if args.dump_pos:
                pos_fp = open(args.dump_pos, "w", encoding="utf-8", newline="")
                pos_writer = csv.DictWriter(pos_fp, fieldnames=fieldnames)
                pos_writer.writeheader()
            if args.dump_amb:
                amb_fp = open(args.dump_amb, "w", encoding="utf-8", newline="")
                amb_writer = csv.DictWriter(amb_fp, fieldnames=fieldnames)
                amb_writer.writeheader()

            # Choose input source: DB or CSV
            if args.db:
                # DBからパラグラフ列挙（メタあり）
                rows_iter = iter_rows_from_db(args.db, args.db_code)
                for row_meta in rows_iter:
                    total += 1
                    raw_text = row_meta.get("text", "")
                    metas = {k: row_meta.get(k) for k in ("paragraph_id","municipality","year","category","dan_number")}

                    if args.sentence_split:
                        sents = split_sentences_like_bullets(raw_text)
                        if not sents:
                            sents = [raw_text]
                        per_sent_rows = []
                        for si, sent in enumerate(sents):
                            label, flags, reason, tokens = classify_text(sent, compiled_rx, cfg)
                            row = {
                                "text": sent,
                                "class": label,
                                "reason": reason,
                                "sudachi_tokens": tokens,
                                "version": VERSION,
                            }
                            for k in flag_cols:
                                row[k] = bool(flags.get(k, False))
                            if args.sentence_detailed:
                                if args.include_meta:
                                    row = {**metas, "sentence_index": si, **row}
                                else:
                                    row = {"sentence_index": si, **row}
                                writer.writerow(row)
                                if label == "POS" and pos_writer is not None:
                                    pos_writer.writerow(row)
                                if label == "AMB" and amb_writer is not None:
                                    amb_writer.writerow(row)
                            per_sent_rows.append((label, row))
                        if not args.sentence_detailed:
                            # 集約: POS > AMB > NEG（flags は OR）
                            agg_label = "NEG"
                            if any(l == "POS" for l, _ in per_sent_rows):
                                agg_label = "POS"
                            elif any(l == "AMB" for l, _ in per_sent_rows):
                                agg_label = "AMB"
                            # flags OR & reason連結（先頭のtokens採用）
                            agg_flags = {k: False for k in flag_cols}
                            reasons = []
                            tokens = ""
                            for _, r in per_sent_rows:
                                reasons.append(r.get("reason", ""))
                                if not tokens:
                                    tokens = r.get("sudachi_tokens", "")
                                for k in flag_cols:
                                    agg_flags[k] = agg_flags[k] or bool(r.get(k, False))
                            out_row = {"text": raw_text, "class": agg_label, "reason": " || ".join(reasons), "sudachi_tokens": tokens, "version": VERSION}
                            for k in flag_cols:
                                out_row[k] = agg_flags[k]
                            if args.include_meta:
                                out_row = {**metas, **out_row}
                            writer.writerow(out_row)
                            if agg_label == "POS" and pos_writer is not None:
                                pos_writer.writerow(out_row)
                            if agg_label == "AMB" and amb_writer is not None:
                                amb_writer.writerow(out_row)
                    else:
                        # 段落単位（従来どおり）
                        label, flags, reason, tokens = classify_text(raw_text, compiled_rx, cfg)
                        out_row = {
                            "text": raw_text,
                            "class": label,
                            "reason": reason,
                            "sudachi_tokens": tokens,
                            "version": VERSION,
                        }
                        for k in flag_cols:
                            out_row[k] = bool(flags.get(k, False))
                        if args.include_meta:
                            out_row = {**metas, **out_row}
                        writer.writerow(out_row)
                        if label == "POS" and pos_writer is not None:
                            pos_writer.writerow(out_row)
                        if label == "AMB" and amb_writer is not None:
                            amb_writer.writerow(out_row)
            else:
                with open(in_path, "r", encoding="utf-8", newline="") as fin:
                    reader = csv.DictReader(fin)

                    # Try to detect text column
                    text_col = "text" if "text" in reader.fieldnames else None
                    if text_col is None:
                        # Heuristic fallback: last column named 'text' in Japanese dataset
                        for cand in ["本文", "sentence", "paragraph", "content"]:
                            if cand in reader.fieldnames:
                                text_col = cand
                                break
                    if text_col is None:
                        # As a final fallback, use the last column
                        text_col = reader.fieldnames[-1]
                        eprint(f"Warning: 'text' column not found; using '{text_col}'")

                    for row in reader:
                        total += 1
                        raw_text = row.get(text_col, "")
                        metas = {}
                        if args.include_meta:
                            # CSVにある場合のみ拾う
                            for k in ("paragraph_id","municipality","year","category","dan_number"):
                                if k in reader.fieldnames:
                                    metas[k] = row.get(k)
                        if args.sentence_split:
                            sents = split_sentences_like_bullets(raw_text)
                            if not sents:
                                sents = [raw_text]
                            per_sent_rows = []
                            for si, sent in enumerate(sents):
                                label, flags, reason, tokens = classify_text(sent, compiled_rx, cfg)
                                r = {
                                    "text": sent,
                                    "class": label,
                                    "reason": reason,
                                    "sudachi_tokens": tokens,
                                    "version": VERSION,
                                }
                                for k in flag_cols:
                                    r[k] = bool(flags.get(k, False))
                                if args.sentence_detailed:
                                    if args.include_meta:
                                        r = {**metas, "sentence_index": si, **r}
                                    else:
                                        r = {"sentence_index": si, **r}
                                    writer.writerow(r)
                                    if label == "POS" and pos_writer is not None:
                                        pos_writer.writerow(r)
                                    if label == "AMB" and amb_writer is not None:
                                        amb_writer.writerow(r)
                                per_sent_rows.append((label, r))
                            if not args.sentence_detailed:
                                agg_label = "NEG"
                                if any(l == "POS" for l, _ in per_sent_rows):
                                    agg_label = "POS"
                                elif any(l == "AMB" for l, _ in per_sent_rows):
                                    agg_label = "AMB"
                                agg_flags = {k: False for k in flag_cols}
                                reasons = []
                                tokens = ""
                                for _, r in per_sent_rows:
                                    reasons.append(r.get("reason", ""))
                                    if not tokens:
                                        tokens = r.get("sudachi_tokens", "")
                                    for k in flag_cols:
                                        agg_flags[k] = agg_flags[k] or bool(r.get(k, False))
                                out_row = {"text": raw_text, "class": agg_label, "reason": " || ".join(reasons), "sudachi_tokens": tokens, "version": VERSION}
                                for k in flag_cols:
                                    out_row[k] = agg_flags[k]
                                if args.include_meta:
                                    out_row = {**metas, **out_row}
                                writer.writerow(out_row)
                                if agg_label == "POS" and pos_writer is not None:
                                    pos_writer.writerow(out_row)
                                if agg_label == "AMB" and amb_writer is not None:
                                    amb_writer.writerow(out_row)
                        else:
                            label, flags, reason, tokens = classify_text(raw_text, compiled_rx, cfg)
                            out_row = {
                                "text": raw_text,
                                "class": label,
                                "reason": reason,
                                "sudachi_tokens": tokens,
                                "version": VERSION,
                            }
                            for k in flag_cols:
                                out_row[k] = bool(flags.get(k, False))
                            if args.include_meta:
                                out_row = {**metas, **out_row}
                            writer.writerow(out_row)
                            if label == "POS" and pos_writer is not None:
                                pos_writer.writerow(out_row)
                            if label == "AMB" and amb_writer is not None:
                                amb_writer.writerow(out_row)
    finally:
        if pos_fp:
            pos_fp.close()
        if amb_fp:
            amb_fp.close()

    eprint(f"Processed {total} rows -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
