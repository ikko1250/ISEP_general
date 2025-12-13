# 規制単位分析 (Regulation Unit Analysis)

自治体条例データベース（`clause_data4.db`）を用いて、規制単位（Lv1/Lv2/手続など）ごとのコーディング分布を分析するスクリプト群です。

## 実行環境

```bash
/home/ubuntu/cur/isep/.venv/bin/python
```

---

## スクリプト一覧

### 1. `regulation_unit_coding_analysis.py`

**メイン分析スクリプト**

規制単位ごとに行政指導・行政処分・罰則（狭義/その他）の条文分布を集計し、帯グラフで可視化します。

**実行方法:**
```bash
/home/ubuntu/cur/isep/.venv/bin/python regulation_unit_coding_analysis.py
```

**出力ファイル:**
| ファイル名 | 説明 |
|-----------|------|
| `regulation_unit_coding_analysis.csv` | 規制単位ごとのコーディング集計（生データ） |
| `regulation_unit_coding_analysis_categorized.csv` | カテゴリ別にグルー化した集計 |
| `regulation_unit_coding_analysis_6level.csv` | 6段階分類での集計 |
| `regulation_unit_coding_chart.png` | 規制単位ごと帯グラフ |
| `regulation_unit_coding_chart_categorized.png` | カテゴリ別帯グラフ |
| `regulation_unit_coding_chart_6level.png` | 6段階分類帯グラフ |
| `municipality_distribution_6level.png` | 6段階カテゴリ別自治体数分布 |
| `municipality_coding_presence.csv` | 自治体レベルでのコーディング有無 |
| `municipality_coding_proportion_chart.png` | コーディング条文を持つ自治体の割合グラフ |

**6段階分類:**
1. `1_Lv2(区域規制)` - 禁止区域での絶対禁止・条件付き禁止・許可制
2. `2_Lv1不同意(禁止)` - 抑制区域での不同意・禁止
3. `3_Lv1許可or同意` - 抑制区域での許可制・同意制
4. `4_抑制区域+届出` - 区域設定あり＋届出・協議手続
5. `5_区域なし+許可制` - 区域設定なし＋許可制
6. `6_届出・協議のみ` - 届出・協議のみ（区域なし）

---

### 2. `cluster_analysis_by_category.py`

**テキストクラスター分析スクリプト**

5段階カテゴリ×3種類コーディング（行政指導・行政処分・罰則）の組み合わせごとにテキストをクラスタリングし、条文内容の傾向を分析します。

**実行方法:**
```bash
/home/ubuntu/cur/isep/.venv/bin/python cluster_analysis_by_category.py
```

**出力先:** `cluster_analysis_results/`

**出力ファイル（各カテゴリ×コーディングごと）:**
- `{category}_{coding}_scatter.png` - クラスター散布図
- `{category}_{coding}_texts.csv` - クラスター分類済みテキスト一覧
- `{category}_{coding}_keywords.txt` - 各クラスターのキーワード

**全体サマリー:**
- `summary_heatmap.png` - テキスト数のヒートマップ
- `cluster_summary_chart.png` - クラスター数サマリー

---

## 注意事項

### 分析対象外の自治体

現在、`regulation_unit_coding_analysis.py`の`get_regulation_unit_stats()`関数では、`規制単位`カラムが空の自治体が一部の分析から除外されています。

**除外されている自治体:**
- 高山村、菊池市、内子町、鹿島市、鹿嶋市、さくら市、和歌山市、袋井市

これらの自治体は6段階分類（`get_6level_stats`）や自治体レベル統計（`get_municipality_level_stats`）には含まれますが、規制単位別の詳細分析からは除外されています。

---

## データベース

**パス:** `/home/ubuntu/cur/isep/clause-viewer/clause_data4.db`

**主要テーブル:**
- `municipalities` - 自治体情報（規制単位、area_type、regulation_type等）
- `paragraphs` - 条文データ
- `paragraph_codings` - 条文へのコーディング付与
- `coding_types` - コーディング種別マスタ
