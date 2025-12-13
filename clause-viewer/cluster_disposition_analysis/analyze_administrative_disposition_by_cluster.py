import pandas as pd
import re
import os

# Paths
CLUSTER_KEYWORDS_PATH = '/home/ubuntu/cur/isep/clause-viewer/cluster_results/cluster_keywords.txt'
INPUT_CSV_PATH = '/home/ubuntu/cur/isep/clause-viewer/csv_by_coding/Administrative_Disposition.csv'
OUTPUT_CSV_PATH = 'administrative_disposition_cluster_analysis.csv'

# Stopwords to filter out from keywords (too common words)
STOPWORDS = {'する', 'ない', 'ある', 'こと', 'もの', 'とき', 'ため', '規定', '条例', '前項', '前条'}

def parse_cluster_keywords(filepath):
    """
    Parses the cluster_keywords.txt file to extract keywords for each cluster.
    Returns a dictionary {cluster_id: [keywords]}
    """
    cluster_keywords = {}
    current_cluster = None
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                # Detect Cluster Header e.g. 【クラスター 0】
                match_cluster = re.match(r'【クラスター\s+(\d+)】', line)
                if match_cluster:
                    current_cluster = int(match_cluster.group(1))
                    cluster_keywords[current_cluster] = []
                    continue
                
                # Detect Keyword e.g. - 検査: 0.3261
                match_keyword = re.match(r'-\s+([^:]+):', line)
                if match_keyword and current_cluster is not None:
                    keyword = match_keyword.group(1).strip()
                    if keyword not in STOPWORDS:
                        cluster_keywords[current_cluster].append(keyword)
    except FileNotFoundError:
        print(f"Error: File not found at {filepath}")
        return {}
        
    return cluster_keywords

def analyze_text(text, keywords):
    """
    Checks if any of the keywords key exist in the text.
    Returns 1 if found, 0 otherwise.
    """
    if not isinstance(text, str):
        return 0
    
    for keyword in keywords:
        if keyword in text:
            return 1
    return 0

def main():
    print("Starting analysis...")
    
    # 1. Parse Cluster Keywords
    print(f"Reading keywords from: {CLUSTER_KEYWORDS_PATH}")
    cluster_keywords = parse_cluster_keywords(CLUSTER_KEYWORDS_PATH)
    
    if not cluster_keywords:
        print("No keywords found or failed to read file.")
        return

    print("Keywords per cluster (filtered):")
    for cid, kws in cluster_keywords.items():
        print(f"  Cluster {cid}: {kws}")

    # 2. Read Input CSV
    print(f"Reading input CSV from: {INPUT_CSV_PATH}")
    try:
        df = pd.read_csv(INPUT_CSV_PATH)
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return
    
    # Ensure 'text' column exists (based on sample rows, the column 8 (0-indexed 7) seems to be text, 
    # but the header row of Administrative_Disposition.csv needs to be checked.
    # The sample output showed:
    # 4,22099,454,さくら市,2023,条例,39,第12条..., ...
    # Let's assume the column name for text is likely 'paragraph_text' or similar based on previous interactions, 
    # BUT wait, the csv_by_coding usually has no header or specific header.
    # Let's check the header of Administrative_Disposition.csv again in the next step if this fails, 
    # but based on `cat` output earlier:
    # 19,7653,209,三郷町,2022,条例,37,(命令)第23条...
    # It seems to have standard columns. 
    # Standard header for these files usually: id, municipality_id, ... text is often column index 7.
    # Actually, let's inspect the columns.
    
    # To be safe, I will use column index 7 for text if 'text' column logic is ambiguous 
    # but try to find a column that looks like text.
    
    target_text_col = None
    # Heuristic to find the text column
    # Usually it's the one with the longest average string length or named 'text'
    if 'text' in df.columns:
        target_text_col = 'text'
    elif 'paragraph_text' in df.columns:
        target_text_col = 'paragraph_text'
    else:
        # Fallback to 8th column (index 7) as seen in previous `head` output
        # 1: id, 2: munic_id, 3: ?, 4: munic_name, 5: year, 6: type, 7: article_num, 8: text
        # Let's try column index 7.
        if len(df.columns) > 7:
             target_text_col = df.columns[7] # 0-indexed
    
    if target_text_col is None:
        print("Could not identify text column.")
        return
        
    print(f"Using column '{target_text_col}' for text analysis.")

    # 3. Analyze Text
    # For each cluster, create a new column
    for cid, keywords in cluster_keywords.items():
        col_name = f'Cluster_{cid}'
        df[col_name] = df[target_text_col].apply(lambda x: analyze_text(x, keywords))

    # 4. Save Result
    print(f"Saving results to: {OUTPUT_CSV_PATH}")
    df.to_csv(OUTPUT_CSV_PATH, index=False, encoding='utf-8-sig')
    
    # 5. Summary
    print("\n--- Match Counts per Cluster ---")
    for cid in cluster_keywords.keys():
        col_name = f'Cluster_{cid}'
        count = df[col_name].sum()
        print(f"  Cluster {cid}: {count} matches")

if __name__ == "__main__":
    main()
