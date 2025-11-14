#!/usr/bin/env python3
import argparse
import csv
from typing import Dict, Tuple


def load_labels(path: str, text_col: str, label_col: str) -> Dict[str, str]:
    labels: Dict[str, str] = {}
    with open(path, "r", encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            t = row.get(text_col, "").strip()
            if not t:
                continue
            labels[t] = row.get(label_col, "").strip()
    return labels


def prf1(tp: int, fp: int, fn: int) -> Tuple[float, float, float]:
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    return prec, rec, f1


def main() -> int:
    ap = argparse.ArgumentParser(description="Evaluate POS precision/recall/F1 using a small gold CSV")
    ap.add_argument("--pred", required=True, help="Predictions CSV (from extract_consent.py)")
    ap.add_argument("--gold", required=True, help="Gold CSV")
    ap.add_argument("--pred-text-col", default="text")
    ap.add_argument("--pred-label-col", default="class")
    ap.add_argument("--gold-text-col", default="text")
    ap.add_argument("--gold-label-col", default="gold")
    args = ap.parse_args()

    pred = load_labels(args.pred, args.pred_text_col, args.pred_label_col)
    gold = load_labels(args.gold, args.gold_text_col, args.gold_label_col)

    # Evaluate for POS class
    tp = fp = fn = 0
    for t, g in gold.items():
        p = pred.get(t)
        if p == "POS" and g == "POS":
            tp += 1
        elif p == "POS" and g != "POS":
            fp += 1
        elif (p != "POS" or p is None) and g == "POS":
            fn += 1

    prec, rec, f1 = prf1(tp, fp, fn)
    print(f"POS Precision: {prec:.4f}")
    print(f"POS Recall   : {rec:.4f}")
    print(f"POS F1       : {f1:.4f}")
    print(f"TP={tp} FP={fp} FN={fn}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

