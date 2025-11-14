#!/usr/bin/env python3
import argparse
import csv
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
    ap.add_argument("--input", required=False, default="clause-viewer/stakeholder_confirmation_paragraphs.csv", help="Input CSV path")
    ap.add_argument("--output", required=False, default="out_stakeholder_consent.csv", help="Output CSV path")
    ap.add_argument("--config", required=False, default="config.yml", help="Config file (YAML or JSON)")
    ap.add_argument("--use-sudachi", dest="use_sudachi", action="store_true", help="Enable Sudachi proximity logic")
    ap.add_argument("--no-sudachi", dest="use_sudachi", action="store_false", help="Disable Sudachi even if config enabled")
    ap.set_defaults(use_sudachi=None)
    ap.add_argument("--sudachi-mode", default=None, help="Sudachi mode A/B/C")
    ap.add_argument("--window", type=int, default=None, help="Proximity window size")
    ap.add_argument("--dump-pos", default=None, help="Optional CSV path to dump POS rows")
    ap.add_argument("--dump-amb", default=None, help="Optional CSV path to dump AMB rows")
    return ap.parse_args()


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

    fieldnames = ["text", "class", "reason"] + flag_cols + ["sudachi_tokens", "version"]

    total = 0
    try:
        with open(in_path, "r", encoding="utf-8", newline="") as fin, \
                open(out_path, "w", encoding="utf-8", newline="") as fout:
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

            for row in reader:
                total += 1
                raw_text = row.get(text_col, "")
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

