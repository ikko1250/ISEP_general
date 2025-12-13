#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Administrative_Disposition.csv のテキストをクラスター分析するスクリプト
Janomeで形態素解析を行い、TF-IDFベクトル化、K-meansクラスタリング、
そしてSeabornで可視化を行う。

使用方法:
  通常モード（文書単位）: python cluster_analysis.py
  文単位モード:          python cluster_analysis.py --sentence-mode
"""

import pandas as pd
import numpy as np
from janome.tokenizer import Tokenizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
import matplotlib.pyplot as plt
import seaborn as sns
from collections import Counter
import warnings
import os
import argparse
import re

warnings.filterwarnings('ignore')

# 日本語フォント設定
plt.rcParams['font.family'] = ['M+ 1C']

# --- 設定 ---
# スクリプトの場所を基準にパスを設定
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_CSV = os.path.join(SCRIPT_DIR, '..', 'csv_by_coding', 'Administrative_Disposition.csv')
OUTPUT_DIR = SCRIPT_DIR  # 出力は現在のフォルダ（cluster_results）に保存
NUM_CLUSTERS = 5  # クラスター数（後でシルエット分析で調整可能）


def parse_args():
    """コマンドライン引数をパース"""
    parser = argparse.ArgumentParser(description='行政処分条文のクラスター分析')
    parser.add_argument('--sentence-mode', action='store_true',
                        help='文単位で分析を行う（デフォルトは文書単位）')
    return parser.parse_args()


def split_into_sentences(text: str) -> list:
    """テキストを文単位に分割"""
    if pd.isna(text):
        return []
    # 「。」で分割し、空文字を除外
    sentences = re.split(r'。', str(text))
    return [s.strip() for s in sentences if s.strip()]


def load_data(filepath: str) -> pd.DataFrame:
    """CSVファイルを読み込む"""
    print(f"Loading data from: {filepath}")
    df = pd.read_csv(filepath)
    print(f"  Loaded {len(df)} rows")
    return df


def tokenize_text(text: str, tokenizer: Tokenizer) -> str:
    """
    Janomeを使用してテキストを形態素解析し、
    名詞・動詞・形容詞のみを抽出して空白区切りで返す
    """
    tokens = []
    for token in tokenizer.tokenize(text):
        # 品詞を取得
        pos = token.part_of_speech.split(',')[0]
        # 名詞、動詞、形容詞のみを抽出
        if pos in ['名詞', '動詞', '形容詞']:
            # 基本形があれば基本形を使用、なければ表層形
            base_form = token.base_form if token.base_form != '*' else token.surface
            # 1文字の単語は除外（ノイズ軽減）
            if len(base_form) > 1:
                tokens.append(base_form)
    return ' '.join(tokens)


def preprocess_texts(df: pd.DataFrame) -> list:
    """テキストカラムを前処理してトークン化"""
    print("Tokenizing texts with Janome...")
    tokenizer = Tokenizer()
    
    processed_texts = []
    for i, text in enumerate(df['text']):
        if pd.isna(text):
            processed_texts.append('')
        else:
            processed_texts.append(tokenize_text(str(text), tokenizer))
        
        # 進捗表示
        if (i + 1) % 50 == 0:
            print(f"  Processed {i + 1}/{len(df)} texts...")
    
    print(f"  Tokenization complete!")
    return processed_texts


def vectorize_texts(processed_texts: list) -> tuple:
    """TF-IDFでテキストをベクトル化"""
    print("Vectorizing texts with TF-IDF...")
    
    vectorizer = TfidfVectorizer(
        max_features=500,  # 特徴量の最大数
        min_df=2,          # 最小文書頻度
        max_df=0.95        # 最大文書頻度
    )
    
    tfidf_matrix = vectorizer.fit_transform(processed_texts)
    feature_names = vectorizer.get_feature_names_out()
    
    print(f"  TF-IDF matrix shape: {tfidf_matrix.shape}")
    return tfidf_matrix, feature_names, vectorizer


def find_optimal_clusters(tfidf_matrix, max_clusters: int = 10) -> dict:
    """シルエットスコアで最適なクラスター数を探索"""
    print("Finding optimal number of clusters...")
    
    silhouette_scores = {}
    inertias = []
    
    for k in range(2, max_clusters + 1):
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = kmeans.fit_predict(tfidf_matrix)
        score = silhouette_score(tfidf_matrix, labels)
        silhouette_scores[k] = score
        inertias.append(kmeans.inertia_)
        print(f"  k={k}: silhouette score = {score:.4f}")
    
    optimal_k = max(silhouette_scores, key=silhouette_scores.get)
    print(f"  Optimal number of clusters: {optimal_k}")
    
    return {
        'silhouette_scores': silhouette_scores,
        'inertias': inertias,
        'optimal_k': optimal_k
    }


def perform_clustering(tfidf_matrix, n_clusters: int) -> tuple:
    """K-meansクラスタリングを実行"""
    print(f"Performing K-means clustering with {n_clusters} clusters...")
    
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    cluster_labels = kmeans.fit_predict(tfidf_matrix)
    
    print(f"  Clustering complete!")
    return cluster_labels, kmeans


def reduce_dimensions(tfidf_matrix) -> np.ndarray:
    """PCAで次元削減（可視化用）"""
    print("Reducing dimensions with PCA...")
    
    pca = PCA(n_components=2, random_state=42)
    coords = pca.fit_transform(tfidf_matrix.toarray())
    
    print(f"  Explained variance ratio: {pca.explained_variance_ratio_}")
    return coords


def get_cluster_keywords(tfidf_matrix, cluster_labels, feature_names, n_keywords: int = 10) -> dict:
    """各クラスターの特徴的なキーワードを抽出"""
    print("Extracting cluster keywords...")
    
    cluster_keywords = {}
    unique_clusters = sorted(set(cluster_labels))
    
    for cluster_id in unique_clusters:
        # このクラスターに属する文書のインデックス
        cluster_indices = np.where(cluster_labels == cluster_id)[0]
        
        # このクラスターの平均TF-IDF値
        cluster_tfidf = tfidf_matrix[cluster_indices].mean(axis=0).A1
        
        # TF-IDF値が高い順にソート
        top_indices = cluster_tfidf.argsort()[-n_keywords:][::-1]
        keywords = [(feature_names[i], cluster_tfidf[i]) for i in top_indices]
        
        cluster_keywords[cluster_id] = keywords
        print(f"  Cluster {cluster_id}: {[kw[0] for kw in keywords[:5]]}...")
    
    return cluster_keywords


def visualize_clusters(coords: np.ndarray, cluster_labels: np.ndarray, 
                       df: pd.DataFrame, output_dir: str) -> None:
    """クラスター分布を可視化"""
    print("Creating visualizations...")
    
    os.makedirs(output_dir, exist_ok=True)
    
    # --- 1. クラスター散布図 ---
    plt.figure(figsize=(12, 8))
    
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
    plt.title('行政処分条文のクラスター分析結果', fontsize=14)
    plt.legend(loc='best', fontsize=10)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'cluster_scatter.png'), dpi=150)
    plt.close()
    print(f"  Saved: cluster_scatter.png")
    
    # --- 2. クラスターサイズの棒グラフ ---
    plt.figure(figsize=(10, 6))
    
    cluster_counts = pd.Series(cluster_labels).value_counts().sort_index()
    colors = sns.color_palette("husl", len(cluster_counts))
    
    ax = sns.barplot(x=cluster_counts.index, y=cluster_counts.values, palette=colors)
    
    # 各バーの上に数値を表示
    for i, v in enumerate(cluster_counts.values):
        ax.text(i, v + 2, str(v), ha='center', fontsize=11)
    
    plt.xlabel('クラスター番号', fontsize=12)
    plt.ylabel('文書数', fontsize=12)
    plt.title('各クラスターの文書数', fontsize=14)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'cluster_sizes.png'), dpi=150)
    plt.close()
    print(f"  Saved: cluster_sizes.png")
    
    # --- 3. 年度別クラスター分布のヒートマップ ---
    if 'year' in df.columns:
        plt.figure(figsize=(12, 8))
        
        cross_tab = pd.crosstab(df['year'], cluster_labels)
        cross_tab.columns = [f'クラスター {c}' for c in cross_tab.columns]
        
        sns.heatmap(cross_tab, annot=True, fmt='d', cmap='YlOrRd')
        
        plt.xlabel('クラスター', fontsize=12)
        plt.ylabel('年度', fontsize=12)
        plt.title('年度別クラスター分布', fontsize=14)
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'cluster_by_year_heatmap.png'), dpi=150)
        plt.close()
        print(f"  Saved: cluster_by_year_heatmap.png")
    
    # --- 4. カテゴリ別クラスター分布 ---
    if 'category' in df.columns:
        plt.figure(figsize=(12, 8))
        
        cross_tab = pd.crosstab(df['category'], cluster_labels)
        cross_tab.columns = [f'クラスター {c}' for c in cross_tab.columns]
        
        sns.heatmap(cross_tab, annot=True, fmt='d', cmap='Blues')
        
        plt.xlabel('クラスター', fontsize=12)
        plt.ylabel('カテゴリ', fontsize=12)
        plt.title('カテゴリ別クラスター分布', fontsize=14)
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'cluster_by_category_heatmap.png'), dpi=150)
        plt.close()
        print(f"  Saved: cluster_by_category_heatmap.png")


def visualize_silhouette_analysis(cluster_analysis: dict, output_dir: str) -> None:
    """シルエット分析の可視化"""
    plt.figure(figsize=(10, 6))
    
    scores = cluster_analysis['silhouette_scores']
    k_values = list(scores.keys())
    s_values = list(scores.values())
    
    sns.lineplot(x=k_values, y=s_values, marker='o', markersize=10)
    
    # 最適なkに目印
    optimal_k = cluster_analysis['optimal_k']
    plt.axvline(x=optimal_k, color='red', linestyle='--', label=f'最適k={optimal_k}')
    
    plt.xlabel('クラスター数 (k)', fontsize=12)
    plt.ylabel('シルエットスコア', fontsize=12)
    plt.title('クラスター数とシルエットスコアの関係', fontsize=14)
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'silhouette_analysis.png'), dpi=150)
    plt.close()
    print(f"  Saved: silhouette_analysis.png")


def save_results(df: pd.DataFrame, cluster_labels: np.ndarray, 
                 cluster_keywords: dict, output_dir: str) -> None:
    """結果をCSVとテキストファイルに保存"""
    print("Saving results...")
    
    os.makedirs(output_dir, exist_ok=True)
    
    # クラスターラベルを追加
    df_result = df.copy()
    df_result['cluster'] = cluster_labels
    
    # クラスター別にソートして保存
    df_result = df_result.sort_values('cluster')
    df_result.to_csv(os.path.join(output_dir, 'clustered_data.csv'), index=False, encoding='utf-8-sig')
    print(f"  Saved: clustered_data.csv")
    
    # キーワード情報をテキストファイルに保存
    with open(os.path.join(output_dir, 'cluster_keywords.txt'), 'w', encoding='utf-8') as f:
        f.write("=" * 60 + "\n")
        f.write("クラスター分析結果 - 各クラスターの特徴的なキーワード\n")
        f.write("=" * 60 + "\n\n")
        
        for cluster_id, keywords in cluster_keywords.items():
            f.write(f"\n【クラスター {cluster_id}】\n")
            f.write(f"文書数: {(cluster_labels == cluster_id).sum()}\n")
            f.write("特徴的なキーワード:\n")
            for word, score in keywords:
                f.write(f"  - {word}: {score:.4f}\n")
            f.write("\n" + "-" * 40 + "\n")
    
    print(f"  Saved: cluster_keywords.txt")
    
    # クラスター別の代表的な条文サンプルを保存
    with open(os.path.join(output_dir, 'cluster_samples.txt'), 'w', encoding='utf-8') as f:
        f.write("=" * 60 + "\n")
        f.write("クラスター分析結果 - 各クラスターの代表的な条文\n")
        f.write("=" * 60 + "\n\n")
        
        for cluster_id in sorted(set(cluster_labels)):
            f.write(f"\n{'='*60}\n")
            f.write(f"【クラスター {cluster_id}】\n")
            f.write(f"{'='*60}\n\n")
            
            cluster_df = df_result[df_result['cluster'] == cluster_id]
            # 最大5つのサンプルを表示
            for idx, row in cluster_df.head(5).iterrows():
                f.write(f"--- {row['municipality_name']} ({row['year']}) ---\n")
                f.write(f"{row['text'][:300]}...\n\n" if len(str(row['text'])) > 300 else f"{row['text']}\n\n")
    
    print(f"  Saved: cluster_samples.txt")


def main():
    """メイン処理"""
    args = parse_args()
    sentence_mode = args.sentence_mode
    
    mode_name = "文単位" if sentence_mode else "文書単位"
    print("=" * 60)
    print(f"行政処分条文のクラスター分析 【{mode_name}モード】")
    print("=" * 60)
    
    # 1. データ読み込み
    df = load_data(INPUT_CSV)
    
    # 文モードの場合、テキストを文単位に分割
    if sentence_mode:
        print("Splitting texts into sentences...")
        sentence_data = []
        for idx, row in df.iterrows():
            sentences = split_into_sentences(row['text'])
            for sent in sentences:
                new_row = row.copy()
                new_row['text'] = sent
                new_row['original_doc_id'] = idx  # 元の文書IDを保持
                sentence_data.append(new_row)
        
        df = pd.DataFrame(sentence_data)
        print(f"  Split into {len(df)} sentences")
    
    # 2. テキスト前処理（Janomeで形態素解析）
    processed_texts = preprocess_texts(df)
    
    # 3. TF-IDFベクトル化
    tfidf_matrix, feature_names, vectorizer = vectorize_texts(processed_texts)
    
    # 4. 最適なクラスター数を探索
    cluster_analysis = find_optimal_clusters(tfidf_matrix, max_clusters=10)
    optimal_k = cluster_analysis['optimal_k']
    
    # 5. クラスタリング実行
    cluster_labels, kmeans = perform_clustering(tfidf_matrix, optimal_k)
    
    # 6. 次元削減（可視化用）
    coords = reduce_dimensions(tfidf_matrix)
    
    # 7. クラスターのキーワード抽出
    cluster_keywords = get_cluster_keywords(tfidf_matrix, cluster_labels, feature_names)
    
    # 出力ディレクトリ（文モードの場合はサブフォルダに）
    output_dir = os.path.join(OUTPUT_DIR, 'sentence_mode') if sentence_mode else OUTPUT_DIR
    os.makedirs(output_dir, exist_ok=True)
    
    # 8. 可視化
    visualize_clusters(coords, cluster_labels, df, output_dir)
    visualize_silhouette_analysis(cluster_analysis, output_dir)
    
    # 9. 結果保存
    save_results(df, cluster_labels, cluster_keywords, output_dir)
    
    print("\n" + "=" * 60)
    print("分析完了！")
    print(f"結果は {output_dir} に保存されました。")
    print("=" * 60)
    
    # 簡易的な結果サマリーを表示
    unit = "文" if sentence_mode else "文書"
    print(f"\n【クラスター分析サマリー】（{mode_name}モード）")
    print(f"  総{unit}数: {len(df)}")
    print(f"  最適クラスター数: {optimal_k}")
    print(f"  シルエットスコア: {cluster_analysis['silhouette_scores'][optimal_k]:.4f}")
    print(f"\n各クラスターのサイズ:")
    for cluster_id in sorted(set(cluster_labels)):
        count = (cluster_labels == cluster_id).sum()
        print(f"  クラスター {cluster_id}: {count} {unit}")


if __name__ == '__main__':
    main()

