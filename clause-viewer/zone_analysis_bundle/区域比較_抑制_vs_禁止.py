import argparse
import importlib.util
import os
from typing import Tuple, Dict

import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np


# ------------- 基本ユーティリティ -------------
def _load_module(module_path: str, alias: str):
    """指定パスのPythonモジュールを任意の別名でロードする。"""
    spec = importlib.util.spec_from_file_location(alias, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"モジュールをロードできませんでした: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _set_japanese_font() -> str:
    """利用可能な日本語フォントを設定し、設定したフォント名を返す。"""
    jp_fonts = [
        "Meiryo",
        "Yu Gothic",
        "Hiragino Sans",
        "Hiragino Kaku Gothic ProN",
        "MS Gothic",
        "TakaoGothic",
        "IPAGothic",
        "Noto Sans CJK JP",
        "Noto Sans JP",
    ]
    available = {f.name for f in fm.fontManager.ttflist}
    for font in jp_fonts:
        if font in available:
            plt.rcParams["font.family"] = font
            return font
    plt.rcParams["font.family"] = "sans-serif"
    return ""


def _summarize_categories(segment_df) -> Tuple[Dict[str, int], Dict[str, float], int]:
    """除外カテゴリを除き、カテゴリ別件数・割合を算出する。"""
    if segment_df is None or segment_df.empty:
        return {}, {}, 0
    valid = segment_df[~segment_df["category"].astype(str).str.startswith("除外")]
    counts = valid["category"].value_counts()
    total = int(counts.sum())
    pct = (counts / total * 100).to_dict() if total > 0 else {}
    return counts.to_dict(), pct, total


def _plot_comparison(categories, sup_pct, ban_pct, sup_counts, ban_counts, sup_total, ban_total, output_path):
    """抑制区域と禁止区域の割合を2本の帯グラフで描画する。"""
    font_used = _set_japanese_font()

    y_pos = np.arange(len(categories))
    bar_h = 0.35
    offset = bar_h / 2

    sup_values = [sup_pct.get(cat, 0.0) for cat in categories]
    ban_values = [ban_pct.get(cat, 0.0) for cat in categories]
    sup_text_counts = [sup_counts.get(cat, 0) for cat in categories]
    ban_text_counts = [ban_counts.get(cat, 0) for cat in categories]

    fig_width_px = 1881
    fig_height_px = 2907
    fig_dpi = 150
    fig_width_in = fig_width_px / fig_dpi
    fig_height_in = fig_height_px / fig_dpi
    fig, ax = plt.subplots(figsize=(fig_width_in, fig_height_in), dpi=fig_dpi)

    bars_sup = ax.barh(y_pos - offset, sup_values, height=bar_h, color="#4c78a8", label="抑制区域 (%)")
    bars_ban = ax.barh(y_pos + offset, ban_values, height=bar_h, color="#f58518", label="禁止区域 (%)")

    # バー横に割合と件数を併記
    for bar, pct, cnt in zip(bars_sup, sup_values, sup_text_counts):
        if pct > 0:
            ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height() / 2,
                    f"{pct:.1f}% ({cnt}件)", va="center", ha="left", fontsize=10, color="black")
    for bar, pct, cnt in zip(bars_ban, ban_values, ban_text_counts):
        if pct > 0:
            ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height() / 2,
                    f"{pct:.1f}% ({cnt}件)", va="center", ha="left", fontsize=10, color="black")

    ax.set_xlabel("割合 (%)", fontsize=13)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(categories, fontsize=12)
    ax.set_title(
        f"太陽光発電規制条例 区域指定理由の比較\n"
        f"抑制区域 (総数: {sup_total}件) vs 禁止区域 (総数: {ban_total}件)",
        fontsize=17, fontweight="bold",
    )

    max_val = max(sup_values + ban_values + [0])
    ax.set_xlim(0, max_val * 1.25 if max_val > 0 else 1)
    ax.grid(axis="x", linestyle="--", alpha=0.3)
    ax.legend(loc="upper right")

    for spine in ax.spines.values():
        spine.set_alpha(0.3)

    plt.tight_layout()
    plt.savefig(output_path, dpi=fig_dpi)
    print(f"[完了] 比較グラフを保存しました: {output_path} (フォント: {font_used or '未検出'})")


# ------------- メイン処理 -------------
def main(suppression_csv: str, prohibition_csv: str, output_path: str):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    sup_module_path = os.path.join(base_dir, "抑制区域_区域設定カテゴリーわけ.py")
    ban_module_path = os.path.join(base_dir, "禁止区域_区域設定カテゴリーわけ.py")

    # 出力先が相対指定ならバンドルフォルダに保存する
    if not os.path.isabs(output_path):
        output_path = os.path.join(base_dir, output_path)

    suppression_module = _load_module(sup_module_path, "suppression_module")
    prohibition_module = _load_module(ban_module_path, "prohibition_module")

    print("=== 抑制区域の分析を実行します ===")
    sup_df = suppression_module.analyze_solar_zones(suppression_csv)
    print("=== 禁止区域の分析を実行します ===")
    ban_df = prohibition_module.analyze_solar_zones(prohibition_csv)

    sup_counts, sup_pct, sup_total = _summarize_categories(sup_df)
    ban_counts, ban_pct, ban_total = _summarize_categories(ban_df)

    if sup_total == 0 and ban_total == 0:
        print("有効なデータがありません。グラフを作成せずに終了します。")
        return

    # 並び順: 両者の合計件数の多い順
    categories = sorted(set(sup_counts.keys()) | set(ban_counts.keys()),
                        key=lambda c: -(sup_counts.get(c, 0) + ban_counts.get(c, 0)))

    _plot_comparison(categories, sup_pct, ban_pct, sup_counts, ban_counts, sup_total, ban_total, output_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="抑制区域と禁止区域の分類結果を比較するグラフを生成します。")
    parser.add_argument("--suppression_csv", default="/home/ubuntu/cur/isep/CLAUSE_ZONE_Lv1_direct_designation.csv",
                        help="抑制区域のCSV (デフォルト: CLAUSE_ZONE_Lv1_direct_designation.csv)")
    parser.add_argument("--prohibition_csv", default="/home/ubuntu/cur/isep/clause-viewer/csv_by_coding/CLAUSE_ZONE_Lv2_filtered.csv",
                        help="禁止区域のCSV (デフォルト: clause-viewer/csv_by_coding/CLAUSE_ZONE_Lv2_filtered.csv)")
    parser.add_argument("--output", default="zone_comparison_bar_chart.png",
                        help="比較グラフの出力ファイル名")

    args = parser.parse_args()
    main(args.suppression_csv, args.prohibition_csv, args.output)
