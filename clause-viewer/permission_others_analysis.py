"""
許可条文分類スクリプト - 「その他」分析版
janomeを使ってクラスタリング分析を行い、分類パターンを発見する
"""

import pandas as pd
from janome.tokenizer import Tokenizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
import re
import os

# 設定
INPUT_FILE = '/home/ubuntu/cur/isep/clause-viewer/permission_classification_result.csv'
OUTPUT_DIR = '/home/ubuntu/cur/isep/clause-viewer/'
OUTPUT_FILE = os.path.join(OUTPUT_DIR, 'permission_others_analysis.csv')


def main():
    # 1. データ読み込み
    print(f"Loading data from {INPUT_FILE}...")
    try:
        df = pd.read_csv(INPUT_FILE, encoding='utf-8')
    except UnicodeDecodeError:
        df = pd.read_csv(INPUT_FILE, encoding='cp932')
    
    print(f"Data loaded. Total records: {len(df)}")
    
    # 2. 「その他」が多いカテゴリを分析
    # permission_type で「その他」のデータを抽出
    df_others_type = df[df['permission_type'] == 'その他'].copy()
    print(f"\n許可の種類が「その他」: {len(df_others_type)} 件")
    
    # permission_condition で「その他」のデータを抽出
    df_others_cond = df[df['permission_condition'] == 'その他'].copy()
    print(f"許可の条件が「その他」: {len(df_others_cond)} 件")
    
    # permission_procedure で「その他」のデータを抽出
    df_others_proc = df[df['permission_procedure'] == 'その他'].copy()
    print(f"許可に伴う手続きが「その他」: {len(df_others_proc)} 件")
    
    # 3. 形態素解析とクラスタリング
    print("\n形態素解析を実行中...")
    t = Tokenizer()
    
    def tokenize(text):
        """テキストを名詞と動詞の原型のみに分割"""
        if not isinstance(text, str):
            return ''
        tokens = []
        clean_text = re.sub(r'[!-/:-@[-`{-~]', '', text)
        clean_text = re.sub(r'\d+', '', clean_text)
        
        for token in t.tokenize(clean_text):
            if token.part_of_speech.split(',')[0] in ['名詞', '動詞']:
                tokens.append(token.base_form)
        return ' '.join(tokens)
    
    # 各カテゴリで分析
    for category_name, df_others in [
        ('permission_type', df_others_type),
        ('permission_condition', df_others_cond),
        ('permission_procedure', df_others_proc)
    ]:
        if len(df_others) < 10:
            print(f"\n{category_name}: データが少なすぎるためスキップ")
            continue
            
        print(f"\n{'='*50}")
        print(f"分析対象: {category_name} の「その他」({len(df_others)}件)")
        print('='*50)
        
        # トークン化
        df_others.loc[:, 'tokenized_text'] = df_others['text'].apply(tokenize)
        
        # TF-IDF ベクトル化
        vectorizer = TfidfVectorizer(
            max_df=0.9,
            min_df=2,
            max_features=500
        )
        
        try:
            X = vectorizer.fit_transform(df_others['tokenized_text'])
        except ValueError as e:
            print(f"ベクトル化エラー: {e}")
            continue
        
        # クラスタリング
        num_clusters = min(5, len(df_others) // 10 + 1)
        kmeans = KMeans(n_clusters=num_clusters, random_state=42, n_init=10)
        kmeans.fit(X)
        
        df_others.loc[:, 'cluster_id'] = kmeans.labels_
        
        # 結果表示
        order_centroids = kmeans.cluster_centers_.argsort()[:, ::-1]
        terms = vectorizer.get_feature_names_out()
        
        for i in range(num_clusters):
            count = len(df_others[df_others['cluster_id'] == i])
            print(f"\nCluster {i}: {count}件")
            
            # 上位キーワード
            top_terms = [terms[ind] for ind in order_centroids[i, :10]]
            print(f"  Keywords: {', '.join(top_terms)}")
            
            # サンプルテキスト表示
            samples = df_others[df_others['cluster_id'] == i]['text'].head(2).tolist()
            for j, sample in enumerate(samples):
                print(f"  Sample {j+1}: {sample[:100]}...")
    
    # 4. 結果の保存（permission_typeのその他を分析した結果）
    if len(df_others_type) > 0:
        df_others_type.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')
        print(f"\n分析結果を保存: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
