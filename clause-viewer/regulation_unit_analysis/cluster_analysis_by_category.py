#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
5段階カテゴリ×3種類コーディング テキストクラスター分析スクリプト

5段階カテゴリ:
1. Lv2 (区域規制)
2. Lv1不同意 (禁止)
3. Lv1許可or同意
4. 抑制区域+届出
5. 協議or届出のみ (区域なし)

対象コーディング:
- *Administrative_Guidance (行政指導)
- *Administrative_Disposition (行政処分)
- *CLAUSE_PENALTY (罰則)

各組み合わせでJanome形態素解析→TF-IDF→K-meansクラスタリングを実行
"""

import sqlite3
import pandas as pd
import numpy as np
from janome.tokenizer import Tokenizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
import matplotlib.pyplot as plt
import seaborn as sns
import warnings
import os

warnings.filterwarnings('ignore')

# 日本語フォント設定
plt.rcParams['font.family'] = ['M+ 1C']

# --- 設定 ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = '/home/ubuntu/cur/isep/clause-viewer/clause_data4.db'
OUTPUT_DIR = os.path.join(SCRIPT_DIR, 'cluster_analysis_results')

# 分析対象コーディング
TARGET_CODINGS = [
    '*Administrative_Guidance',
    '*Administrative_Disposition',
    '*CLAUSE_PENALTY'
]

CODING_NAMES = {
    '*Administrative_Guidance': '行政指導',
    '*Administrative_Disposition': '行政処分',
    '*CLAUSE_PENALTY': '罰則'
}

CATEGORY_NAMES = {
    '1_Lv2(区域規制)': 'Lv2(区域規制)',
    '2_Lv1不同意(禁止)': 'Lv1不同意(禁止)',
    '3_Lv1許可or同意': 'Lv1許可or同意',
    '4_抑制区域+届出': '抑制区域+届出',
    '5_協議or届出のみ': '協議or届出(区域なし)'
}


def categorize_5level(reg_unit, area_type):
    """規制単位とarea_typeを考慮して5段階に分類"""
    reg_unit = reg_unit or ''
    area_type = area_type or ''
    
    if not reg_unit:
        if area_type in ['抑制地区制', '禁止地区制', '2層構造(抑制+禁止)']:
            return '4_抑制区域+届出'
        return '5_協議or届出のみ'
    
    has_lv1 = 'Lv1:' in reg_unit
    has_lv2 = 'Lv2:' in reg_unit
    has_procedure = '手続:' in reg_unit
    
    if has_lv2:
        return '1_Lv2(区域規制)'
    
    if has_lv1:
        if has_procedure:
            return '4_抑制区域+届出'
        if '禁止' in reg_unit:
            return '2_Lv1不同意(禁止)'
        if '許可' in reg_unit or '同意' in reg_unit:
            return '3_Lv1許可or同意'
        return '3_Lv1許可or同意'
    
    if has_procedure:
        if area_type in ['抑制地区制', '禁止地区制', '2層構造(抑制+禁止)']:
            return '4_抑制区域+届出'
    
    return '5_協議or届出のみ'


def get_texts_by_category_and_coding(conn, category, coding_type):
    """指定されたカテゴリとコーディングに該当するテキストを取得"""
    
    # コーディングIDを取得
    cursor = conn.execute(
        "SELECT id FROM coding_types WHERE code = ?", (coding_type,)
    )
    result = cursor.fetchone()
    if not result:
        return pd.DataFrame()
    coding_id = result[0]
    
    # 該当する条文を取得
    cursor = conn.execute("""
        SELECT p.id, p.text, m.name as municipality_name, m.規制単位, m.area_type
        FROM paragraphs p
        JOIN municipalities m ON p.municipality_id = m.id
        JOIN paragraph_codings pc ON p.id = pc.paragraph_id
        WHERE pc.coding_type_id = ?
    """, (coding_id,))
    
    rows = cursor.fetchall()
    
    # DataFrameに変換
    df = pd.DataFrame(rows, columns=['paragraph_id', 'text', 'municipality_name', '規制単位', 'area_type'])
    
    # 5段階カテゴリを追加
    df['5段階'] = df.apply(lambda row: categorize_5level(row['規制単位'], row['area_type']), axis=1)
    
    # 指定カテゴリのみフィルタ
    df_filtered = df[df['5段階'] == category].copy()
    
    return df_filtered


def tokenize_text(text, tokenizer):
    """Janomeを使用してテキストを形態素解析"""
    if pd.isna(text) or not text:
        return ''
    
    tokens = []
    for token in tokenizer.tokenize(str(text)):
        pos = token.part_of_speech.split(',')[0]
        if pos in ['名詞', '動詞', '形容詞']:
            base_form = token.base_form if token.base_form != '*' else token.surface
            if len(base_form) > 1:
                tokens.append(base_form)
    return ' '.join(tokens)


def preprocess_texts(df, tokenizer):
    """テキストを前処理してトークン化"""
    processed_texts = []
    for text in df['text']:
        processed_texts.append(tokenize_text(text, tokenizer))
    return processed_texts


def perform_cluster_analysis(df, processed_texts, min_samples=10, max_clusters=8):
    """クラスター分析を実行"""
    if len(df) < min_samples:
        return None, None, None, None, None
    
    # TF-IDFベクトル化
    vectorizer = TfidfVectorizer(
        max_features=300,
        min_df=2,
        max_df=0.95
    )
    
    try:
        tfidf_matrix = vectorizer.fit_transform(processed_texts)
    except ValueError:
        return None, None, None, None, None
    
    if tfidf_matrix.shape[1] < 5:
        return None, None, None, None, None
    
    feature_names = vectorizer.get_feature_names_out()
    
    # 最適なクラスター数を探索
    max_k = min(max_clusters, len(df) // 3)
    if max_k < 2:
        max_k = 2
    
    best_k = 2
    best_score = -1
    
    for k in range(2, max_k + 1):
        try:
            kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
            labels = kmeans.fit_predict(tfidf_matrix)
            score = silhouette_score(tfidf_matrix, labels)
            if score > best_score:
                best_score = score
                best_k = k
        except:
            continue
    
    # クラスタリング実行
    kmeans = KMeans(n_clusters=best_k, random_state=42, n_init=10)
    cluster_labels = kmeans.fit_predict(tfidf_matrix)
    
    # 次元削減
    pca = PCA(n_components=2, random_state=42)
    coords = pca.fit_transform(tfidf_matrix.toarray())
    
    # クラスターキーワード抽出
    cluster_keywords = {}
    for cluster_id in range(best_k):
        cluster_indices = np.where(cluster_labels == cluster_id)[0]
        if len(cluster_indices) == 0:
            continue
        cluster_tfidf = tfidf_matrix[cluster_indices].mean(axis=0).A1
        top_indices = cluster_tfidf.argsort()[-10:][::-1]
        keywords = [(feature_names[i], cluster_tfidf[i]) for i in top_indices]
        cluster_keywords[cluster_id] = keywords
    
    return cluster_labels, coords, cluster_keywords, best_k, best_score


def create_cluster_scatter(coords, cluster_labels, category_name, coding_name, output_path):
    """クラスター散布図を作成"""
    plt.figure(figsize=(10, 8))
    
    unique_clusters = sorted(set(cluster_labels))
    palette = sns.color_palette("husl", len(unique_clusters))
    
    for cluster_id, color in zip(unique_clusters, palette):
        mask = cluster_labels == cluster_id
        plt.scatter(
            coords[mask, 0], 
            coords[mask, 1],
            c=[color],
            label=f'クラスター {cluster_id} (n={mask.sum()})',
            alpha=0.6,
            s=50
        )
    
    plt.xlabel('第1主成分', fontsize=12)
    plt.ylabel('第2主成分', fontsize=12)
    plt.title(f'{category_name} - {coding_name}条文のクラスター分析', fontsize=14)
    plt.legend(loc='best', fontsize=10)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def save_cluster_results(df, cluster_labels, cluster_keywords, category_name, coding_name, output_dir):
    """クラスター分析結果を保存"""
    prefix = f"{category_name}_{coding_name}"
    
    # クラスターラベルを追加
    df_result = df.copy()
    df_result['cluster'] = cluster_labels
    
    # CSV保存
    csv_path = os.path.join(output_dir, f'{prefix}_clustered.csv')
    df_result.to_csv(csv_path, index=False, encoding='utf-8-sig')
    
    # キーワード保存
    keywords_path = os.path.join(output_dir, f'{prefix}_keywords.txt')
    with open(keywords_path, 'w', encoding='utf-8') as f:
        f.write(f"{'='*60}\n")
        f.write(f"{category_name} - {coding_name}条文のクラスター分析結果\n")
        f.write(f"{'='*60}\n\n")
        f.write(f"総条文数: {len(df)}\n\n")
        
        for cluster_id, keywords in cluster_keywords.items():
            count = (cluster_labels == cluster_id).sum()
            f.write(f"\n【クラスター {cluster_id}】 ({count}件)\n")
            f.write("特徴的なキーワード:\n")
            for word, score in keywords[:10]:
                f.write(f"  - {word}: {score:.4f}\n")
            f.write("-" * 40 + "\n")
    
    return csv_path, keywords_path


def create_summary_heatmap(summary_data, output_path):
    """全体サマリーのヒートマップを作成"""
    # データを整形
    categories = ['1_Lv2(区域規制)', '2_Lv1不同意(禁止)', '3_Lv1許可or同意', 
                  '4_抑制区域+届出', '5_協議or届出のみ']
    codings = ['*Administrative_Guidance', '*Administrative_Disposition', '*CLAUSE_PENALTY']
    
    # 条文数のマトリックスを作成
    count_matrix = []
    for cat in categories:
        row = []
        for coding in codings:
            key = (cat, coding)
            if key in summary_data:
                row.append(summary_data[key]['count'])
            else:
                row.append(0)
        count_matrix.append(row)
    
    df_matrix = pd.DataFrame(
        count_matrix,
        index=[CATEGORY_NAMES.get(c, c) for c in categories],
        columns=[CODING_NAMES.get(c, c) for c in codings]
    )
    
    # ヒートマップ作成
    fig, ax = plt.subplots(figsize=(10, 8))
    
    sns.heatmap(df_matrix, annot=True, fmt='d', cmap='YlOrRd', 
                linewidths=0.5, ax=ax, cbar_kws={'label': '条文数'})
    
    ax.set_title('5段階カテゴリ×コーディング種類 - 条文数分布', fontsize=14, fontweight='bold')
    ax.set_xlabel('コーディング種類', fontsize=12)
    ax.set_ylabel('5段階カテゴリ', fontsize=12)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def create_cluster_summary_chart(summary_data, output_path):
    """クラスター数のサマリーチャートを作成"""
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    
    categories = ['1_Lv2(区域規制)', '2_Lv1不同意(禁止)', '3_Lv1許可or同意', 
                  '4_抑制区域+届出', '5_協議or届出のみ']
    codings = ['*Administrative_Guidance', '*Administrative_Disposition', '*CLAUSE_PENALTY']
    
    for idx, coding in enumerate(codings):
        ax = axes[idx]
        
        counts = []
        n_clusters = []
        cat_labels = []
        
        for cat in categories:
            key = (cat, coding)
            if key in summary_data and summary_data[key]['n_clusters']:
                counts.append(summary_data[key]['count'])
                n_clusters.append(summary_data[key]['n_clusters'])
                cat_labels.append(CATEGORY_NAMES.get(cat, cat))
            else:
                counts.append(0)
                n_clusters.append(0)
                cat_labels.append(CATEGORY_NAMES.get(cat, cat))
        
        x = range(len(cat_labels))
        
        bars = ax.bar(x, counts, color=sns.color_palette("husl", 5), alpha=0.8)
        
        # クラスター数をバーの上に表示
        for i, (count, n_clust) in enumerate(zip(counts, n_clusters)):
            if n_clust > 0:
                ax.text(i, count + 5, f'{n_clust}クラスター', 
                       ha='center', fontsize=9, fontweight='bold')
        
        ax.set_xticks(x)
        ax.set_xticklabels(cat_labels, rotation=45, ha='right', fontsize=9)
        ax.set_ylabel('条文数', fontsize=10)
        ax.set_title(f'{CODING_NAMES[coding]}', fontsize=12, fontweight='bold')
        ax.grid(axis='y', alpha=0.3)
    
    plt.suptitle('5段階カテゴリ別 - 各コーディングの条文数とクラスター数', 
                 fontsize=14, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()


def main():
    """メイン処理"""
    print("=" * 60)
    print("5段階カテゴリ×3種類コーディング テキストクラスター分析")
    print("=" * 60)
    
    # 出力ディレクトリ作成
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Tokenizerを初期化（再利用）
    print("\nJanome Tokenizerを初期化中...")
    tokenizer = Tokenizer()
    
    # データベース接続
    conn = sqlite3.connect(DB_PATH)
    
    # 分析結果のサマリー
    summary_data = {}
    all_results = []
    
    categories = ['1_Lv2(区域規制)', '2_Lv1不同意(禁止)', '3_Lv1許可or同意', 
                  '4_抑制区域+届出', '5_協議or届出のみ']
    
    try:
        for category in categories:
            cat_name = CATEGORY_NAMES.get(category, category)
            print(f"\n{'='*40}")
            print(f"カテゴリ: {cat_name}")
            print('='*40)
            
            for coding in TARGET_CODINGS:
                coding_name = CODING_NAMES[coding]
                print(f"\n  処理中: {coding_name}...")
                
                # テキスト取得
                df = get_texts_by_category_and_coding(conn, category, coding)
                
                if df.empty or len(df) < 10:
                    print(f"    スキップ: データ不足 ({len(df)}件)")
                    summary_data[(category, coding)] = {
                        'count': len(df),
                        'n_clusters': None,
                        'silhouette': None
                    }
                    continue
                
                print(f"    条文数: {len(df)}")
                
                # テキスト前処理
                processed_texts = preprocess_texts(df, tokenizer)
                
                # クラスター分析
                result = perform_cluster_analysis(df, processed_texts)
                cluster_labels, coords, cluster_keywords, n_clusters, silhouette = result
                
                if cluster_labels is None:
                    print(f"    スキップ: クラスター分析失敗")
                    summary_data[(category, coding)] = {
                        'count': len(df),
                        'n_clusters': None,
                        'silhouette': None
                    }
                    continue
                
                print(f"    クラスター数: {n_clusters}, シルエットスコア: {silhouette:.4f}")
                
                # 結果保存
                cat_safe_name = category.replace('/', '_').replace('(', '').replace(')', '')
                coding_safe_name = coding.replace('*', '').replace('_', '')
                
                # 散布図作成
                scatter_path = os.path.join(OUTPUT_DIR, f'{cat_safe_name}_{coding_safe_name}_scatter.png')
                create_cluster_scatter(coords, cluster_labels, cat_name, coding_name, scatter_path)
                
                # 結果ファイル保存
                save_cluster_results(df, cluster_labels, cluster_keywords, 
                                    cat_safe_name, coding_safe_name, OUTPUT_DIR)
                
                # サマリーに追加
                summary_data[(category, coding)] = {
                    'count': len(df),
                    'n_clusters': n_clusters,
                    'silhouette': silhouette
                }
                
                all_results.append({
                    'category': category,
                    'coding': coding,
                    'count': len(df),
                    'n_clusters': n_clusters,
                    'silhouette': silhouette
                })
        
        # サマリーヒートマップ作成
        print("\n\nサマリーチャートを作成中...")
        heatmap_path = os.path.join(OUTPUT_DIR, 'summary_heatmap.png')
        create_summary_heatmap(summary_data, heatmap_path)
        
        chart_path = os.path.join(OUTPUT_DIR, 'summary_cluster_chart.png')
        create_cluster_summary_chart(summary_data, chart_path)
        
        # サマリーCSV保存
        df_summary = pd.DataFrame(all_results)
        df_summary.to_csv(os.path.join(OUTPUT_DIR, 'analysis_summary.csv'), 
                         index=False, encoding='utf-8-sig')
        
        print("\n" + "=" * 60)
        print("分析完了！")
        print(f"結果は {OUTPUT_DIR} に保存されました。")
        print("=" * 60)
        
        # 結果サマリー表示
        print("\n【分析結果サマリー】")
        for (cat, coding), data in summary_data.items():
            cat_name = CATEGORY_NAMES.get(cat, cat)
            coding_name = CODING_NAMES.get(coding, coding)
            if data['n_clusters']:
                print(f"  {cat_name} × {coding_name}: {data['count']}件 → {data['n_clusters']}クラスター")
            else:
                print(f"  {cat_name} × {coding_name}: {data['count']}件 (分析スキップ)")
    
    finally:
        conn.close()


if __name__ == '__main__':
    main()
