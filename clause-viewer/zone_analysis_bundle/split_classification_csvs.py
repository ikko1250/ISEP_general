from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd


def sanitize_filename(name: str) -> str:
    # Avoid path separators and empty filenames.
    safe = re.sub(r"[\\\\/]+", "／", name)
    safe = safe.replace(":", "_").strip()
    return safe or "unknown"


def split_csv(input_path: Path, output_dir: Path, prefix: str) -> None:
    df = pd.read_csv(input_path)
    if "category" not in df.columns:
        raise ValueError(f"'category' column not found in {input_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    for category, group in df.groupby("category", dropna=False):
        category_str = "nan" if pd.isna(category) else str(category)
        filename = f"{prefix}{sanitize_filename(category_str)}.csv"
        group.to_csv(output_dir / filename, index=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Split Lv1/Lv2 classification CSVs into per-category files."
    )
    parser.add_argument(
        "--lv1",
        default="clause-viewer/zone_analysis_bundle/各分類調査/Lv1_zone_classification_results.csv",
        help="Path to Lv1 CSV.",
    )
    parser.add_argument(
        "--lv2",
        default="clause-viewer/zone_analysis_bundle/各分類調査/Lv2_zone_classification_results.csv",
        help="Path to Lv2 CSV.",
    )
    parser.add_argument(
        "--output-dir",
        default="clause-viewer/zone_analysis_bundle/各分類調査/split_by_category",
        help="Directory for output CSVs.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)

    split_csv(Path(args.lv1), output_dir, "Lv1_")
    split_csv(Path(args.lv2), output_dir, "Lv2_")


if __name__ == "__main__":
    main()
