import pandas as pd
from sudachipy import tokenizer
from sudachipy import dictionary
import os
import csv
import json
import re
import sys
import traceback

import sqlite3

# --- 設定 ---
# 実行環境に合わせてパスを確認してください
BASE_DIR = '/home/ubuntu/cur/isep'
INPUT_DB_PATH = os.path.join(BASE_DIR, 'clause-viewer/clause_data3.db')
MECAB_USER_DICT_PATH = os.path.join(BASE_DIR, 'solar_ordinance_userdic_mecab_safe_refined.csv')
FORCED_EXTRACTION_PATH = os.path.join(BASE_DIR, '強制抽出_v3.txt')
CODING_RULES_PATH = os.path.join(BASE_DIR, 'khcoder_coding_rules_PV_v4.txt')
SUDACHI_USER_DICT_CSV_PATH = os.path.join(BASE_DIR, 'sudachi_user.csv')
SUDACHI_USER_DICT_PATH = os.path.join(BASE_DIR, 'sudachi_user.dic')
SUDACHI_CONFIG_PATH = os.path.join(BASE_DIR, 'sudachi_config.json')
OUTPUT_CSV_PATH = os.path.join(BASE_DIR, 'analysis_results_sudachi_paragraphs.csv')

# --- コーディングルールの読み込み ---
def load_coding_rules():
    """KH Coderのコーディングルールファイルを読み込む"""
    rules = {}
    current_code = None
    
    if not os.path.exists(CODING_RULES_PATH):
        print(f"警告: コーディングルールファイルが見つかりません: {CODING_RULES_PATH}")
        return {}

    try:
        with open(CODING_RULES_PATH, 'r', encoding='utf-8-sig') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                # コメント行のスキップ (#で始まる場合など)
                if line.startswith('#'):
                    continue
                    
                if line.startswith('*'):
                    current_code = line
                    rules[current_code] = ''
                elif current_code:
                    rules[current_code] += ' ' + line
        
        # 各ルールをクリーンアップ
        cleaned_rules = {}
        for code, rule in rules.items():
            cleaned_rules[code] = rule.strip()
        
        print(f"コーディングルール {len(cleaned_rules)} 件を読み込みました")
        return cleaned_rules
    except Exception as e:
        print(f"コーディングルール読み込みエラー: {e}")
        return {}

# --- ルール判定ロジック ---
def check_coding_rules(text, morphemes, rules):
    matched_codes = []
    if not rules:
        return matched_codes

    # 検索対象として、表層形、辞書形、正規化形の3つを用意
    surfaces = [m.surface() for m in morphemes]
    dict_forms = [m.dictionary_form() for m in morphemes]
    normalized_forms = [m.normalized_form() for m in morphemes]
    
    # Token boundaries for phrase matching
    token_starts = set(m.begin() for m in morphemes)
    token_ends = set(m.end() for m in morphemes)
    
    for code, rule in rules.items():
        if evaluate_rule(text, surfaces, dict_forms, normalized_forms, token_starts, token_ends, rule):
            matched_codes.append(code)
    
    return matched_codes

def evaluate_rule(text, surfaces, dict_forms, normalized_forms, token_starts, token_ends, rule):
    try:
        return parse_and_evaluate(rule, text, surfaces, dict_forms, normalized_forms, token_starts, token_ends)
    except Exception:
        # ルール解析エラーは無視してFalseを返す
        return False

def parse_and_evaluate(expr, text, surfaces, dict_forms, normalized_forms, token_starts, token_ends):
    expr = expr.strip()
    
    # 括弧の処理
    if expr.startswith('(') and expr.endswith(')'):
        inner = expr[1:-1].strip()
        if split_by_operator(inner, 'or') == [inner] and split_by_operator(inner, 'and') == [inner]:
             pass 
        else:
             return parse_and_evaluate(inner, text, surfaces, dict_forms, normalized_forms, token_starts, token_ends)

    # or演算子
    parts = split_by_operator(expr, 'or')
    if len(parts) > 1:
        return any(parse_and_evaluate(p, text, surfaces, dict_forms, normalized_forms, token_starts, token_ends) for p in parts)
    
    # and演算子
    parts = split_by_operator(expr, 'and')
    if len(parts) > 1:
        return all(parse_and_evaluate(p, text, surfaces, dict_forms, normalized_forms, token_starts, token_ends) for p in parts)
    
    # not演算子
    if expr.lower().startswith('not '):
        return not parse_and_evaluate(expr[4:].strip(), text, surfaces, dict_forms, normalized_forms, token_starts, token_ends)
    
    # near構文
    near_match = re.match(r'near\s*\(([^)]+)\)\s*\[([b\d]+)\]', expr, re.IGNORECASE)
    if near_match:
        content = near_match.group(1)
        words = [w.strip() for w in content.split('-')]
        distance_str = near_match.group(2)
        backward = distance_str.startswith('b')
        distance = int(distance_str.replace('b', ''))
        return check_distance_logic(words, text, surfaces, dict_forms, normalized_forms, token_starts, token_ends, distance, backward, mode='near')
    
    # seq構文
    seq_match = re.match(r'seq\s*\(([^)]+)\)\s*\[([b\d]+)\]', expr, re.IGNORECASE)
    if seq_match:
        content = seq_match.group(1)
        words = [w.strip() for w in content.split('-')]
        distance_str = seq_match.group(2)
        backward = distance_str.startswith('b')
        distance = int(distance_str.replace('b', ''))
        return check_distance_logic(words, text, surfaces, dict_forms, normalized_forms, token_starts, token_ends, distance, backward, mode='seq')
    
    # 単純キーワード (修正: テキスト検索ではなく単語検索へ)
    return check_keyword(expr, text, surfaces, dict_forms, normalized_forms, token_starts, token_ends)

def split_by_operator(expr, operator):
    """括弧のネストを考慮して演算子で分割"""
    parts = []
    current = []
    depth = 0
    i = 0
    op_len = len(operator)
    padded_expr = expr
    
    while i < len(padded_expr):
        char = padded_expr[i]
        if char == '(':
            depth += 1
            current.append(char)
        elif char == ')':
            depth -= 1
            current.append(char)
        elif depth == 0:
            is_op = False
            if padded_expr[i:].startswith(operator):
                prev_char = padded_expr[i-1] if i > 0 else ' '
                next_char = padded_expr[i+op_len] if i+op_len < len(padded_expr) else ' '
                if prev_char.isspace() and next_char.isspace():
                    is_op = True
            
            if is_op:
                parts.append(''.join(current).strip())
                current = []
                i += op_len - 1
            else:
                current.append(char)
        else:
            current.append(char)
        i += 1
    
    if current:
        parts.append(''.join(current).strip())
    return parts if len(parts) > 1 else [expr]

def find_token_intervals(keyword, text, surfaces, dict_forms, normalized_forms, token_starts, token_ends):
    """
    キーワードに一致するトークン区間(start_idx, end_idx)のリストを返す
    """
    intervals = []
    
    # 1. Single token match
    for i, (surf, dic, norm) in enumerate(zip(surfaces, dict_forms, normalized_forms)):
        if keyword == surf or keyword == dic or keyword == norm:
            intervals.append((i, i+1))
            
    # 2. Phrase match
    if keyword in text:
        start_indices = []
        pos = text.find(keyword)
        while pos != -1:
            start_indices.append(pos)
            pos = text.find(keyword, pos + 1)
            
        keyword_len = len(keyword)
        
        # Map char position to token index
        # token_starts is a set of char indices. We need char -> token_idx map.
        # Constructing it here might be slow if done repeatedly.
        # Optimization: Construct it once outside? For now, let's iterate.
        # Or better: We know token_starts contains the char indices.
        # We need to find WHICH token starts at 'start' and WHICH token ends at 'end'.
        
        # Create a map for fast lookup
        char_to_token_start = {}
        char_to_token_end = {}
        
        # This mapping construction is O(N) per call. 
        # Since we are inside a rule loop, maybe we should pass this map?
        # For simplicity and correctness first:
        current_char = 0
        token_start_map = {} # char_idx -> token_idx
        token_end_map = {}   # char_idx -> token_idx (exclusive)
        
        # Reconstruct token positions from surfaces (assuming contiguous)
        # Wait, we already have token_starts/ends sets, but not the index map.
        # Let's rebuild it from surfaces.
        # NOTE: This assumes surfaces concatenate to text exactly. Sudachi usually does.
        # But we passed `text` which is the original text.
        
        # Let's use the token_starts/ends sets to validate, but we need indices.
        # Let's iterate through tokens to find the match.
        
        for start in start_indices:
            end = start + keyword_len
            
            if start in token_starts and end in token_ends:
                # Valid phrase boundary. Now find token indices.
                # Find token index where token.begin() == start
                # Find token index where token.end() == end
                
                # We can iterate tokens to find this.
                # Since we don't have the token objects here, we have to rely on 
                # reconstructing positions or passing more info.
                # `token_starts` passed in is just a set.
                
                # Let's assume we can scan.
                # Optimization: We can just scan once for all occurrences?
                pass

    # Re-implementation with better efficiency:
    # We need token start/end char positions associated with their token index.
    # Let's build a list of (start, end) for each token.
    token_spans = []
    current_pos = 0
    # We don't have the original tokens here, only surfaces.
    # We need to rely on the fact that we have `text` and `surfaces`.
    # BUT, Sudachi normalization might change lengths? No, surface() should match text.
    # Let's verify: text == "".join(surfaces)? Usually yes.
    
    # Let's assume text is contiguous surfaces.
    # Build token char spans.
    token_char_spans = []
    char_idx = 0
    for surf in surfaces:
        token_char_spans.append((char_idx, char_idx + len(surf)))
        char_idx += len(surf)
        
    # Now check phrases
    if keyword in text:
        pos = text.find(keyword)
        while pos != -1:
            end_pos = pos + len(keyword)
            
            # Find start token index
            start_token_idx = -1
            end_token_idx = -1
            
            for i, (ts, te) in enumerate(token_char_spans):
                if ts == pos:
                    start_token_idx = i
                if te == end_pos:
                    end_token_idx = i + 1 # exclusive
                    
            if start_token_idx != -1 and end_token_idx != -1:
                intervals.append((start_token_idx, end_token_idx))
                
            pos = text.find(keyword, pos + 1)
            
    return list(set(intervals)) # Unique intervals

def check_distance_logic(words, text, surfaces, dict_forms, normalized_forms, token_starts, token_ends, distance, backward, mode='near'):
    """nearとseqのロジック統合版 (区間対応)"""
    
    # 各単語の出現区間リストを取得
    # intervals: List of List of tuples [(start, end), ...]
    all_intervals = []
    for word in words:
        intervals = find_token_intervals(word, text, surfaces, dict_forms, normalized_forms, token_starts, token_ends)
        if not intervals:
            return False
        all_intervals.append(intervals)
    
    import itertools
    if mode == 'near':
        for combo in itertools.product(*all_intervals):
            # combo is a tuple of intervals: ((s1, e1), (s2, e2), ...)
            
            # Calculate span
            min_start = min(c[0] for c in combo)
            max_end = max(c[1] for c in combo)
            
            # Distance definition:
            # If "A B", A=[0,1), B=[1,2). Span is [0,2). Length 2.
            # If near(A-B)[1], does it match?
            # Usually near[N] means within N tokens.
            # KH Coder: "near(A-B)[N]" means distance between A and B is <= N.
            # If A and B are adjacent, distance is 0? Or 1?
            # In original logic: max_idx - min_idx. 
            # If adjacent (0, 1), max=1, min=0. Dist=1.
            # So adjacent is 1.
            
            # New logic: max_end - min_start.
            # If adjacent A=[0,1), B=[1,2). min_start=0, max_end=2. Dist=2.
            # So new logic adds 1 compared to old logic for single tokens?
            # Old: indices 0, 1. 1-0 = 1.
            # New: [0,1), [1,2). 2-0 = 2.
            
            # We should probably subtract the length of the words themselves to match "distance between"?
            # Or just adjust N?
            # Let's stick to "span length" for now, but we might need to adjust N.
            # Wait, if I use max(starts) - min(ends)? No.
            
            # Let's try to match the old logic for single tokens.
            # Old: max_idx - min_idx.
            # Single tokens: A at i, B at j. Dist = |i - j|.
            # Intervals: A=[i, i+1), B=[j, j+1).
            # We want |i - j|.
            # If i < j: j - i.
            # Interval calc: max_end - min_start = (j+1) - i = j - i + 1.
            # So (max_end - min_start) - 1 = j - i.
            # But what if words have length > 1?
            # A=[0,2) (len 2), B=[5,6) (len 1).
            # Span: 0 to 6. Dist = 6.
            # "Distance" usually implies gap.
            # Gap = 5 - 2 = 3.
            # KH Coder "near" usually counts total span including words?
            # "near(A-B)[6]" -> A and B are within 6 words of each other?
            # If I use (max_end - min_start) - 1, for adjacent [0,1), [1,2), dist = 2-0-1 = 1. Matches old logic.
            
            # Let's use: span_len = max_end - min_start.
            # check: span_len - 1 <= distance?
            # Or just span_len <= distance?
            # If old logic was max_idx - min_idx <= distance.
            # For adjacent: 1 <= distance.
            # My span_len is 2. So span_len <= distance + 1?
            
            # Let's try to be consistent with "span".
            # If I have "A ... B", and A is 1 token, B is 1 token.
            # If they are adjacent, distance is 1.
            # If "A x B", distance is 2.
            # If "A x x B", distance is 3.
            
            # With intervals:
            # "A x B" -> [0,1), [2,3). min_start=0, max_end=3. Span=3.
            # Old logic: 0, 2. Dist=2.
            # So span = Dist + 1.
            
            # So condition: max_end - min_start <= distance + 1
            # But wait, if words are long?
            # "AA x BB" -> [0,2), [3,5).
            # min_start=0, max_end=5. Span=5.
            # Old logic (if we took first char?): 0, 3. Dist=3.
            # Old logic (if we took last char?): 1, 4. Dist=3.
            # Old logic used ANY matching index.
            # If "AA" matched at 0 and 1. "BB" matched at 3 and 4.
            # It took min(all) and max(all)?
            # Old logic: `sorted_idx = sorted(combo)`. `min_idx = sorted_idx[0]`, `max_idx = sorted_idx[-1]`.
            # If "AA" matches at 0,1. "BB" matches at 3,4.
            # Combo could be (0, 3), (0, 4), (1, 3), (1, 4).
            # It checks ALL combos.
            # If (0, 3) is checked: dist 3.
            # If (1, 4) is checked: dist 3.
            # If (0, 4) is checked: dist 4.
            # It returns True if ANY combo satisfies condition.
            # So it effectively checks the "closest" pair of constituent tokens?
            # No, it checks if there EXISTS a combination.
            
            # For phrases, we want the phrase to be treated as a UNIT.
            # So we should use the phrase boundaries.
            # "AA" is [0,2). "BB" is [3,5).
            # We want distance between these units.
            # If we define distance as "max_end - min_start", that's the covering span.
            # For [0,2) and [3,5), span is 5.
            # If we treat them as single points (centers? starts?), it's ambiguous.
            # Let's stick to "covering span".
            # And to match old logic for single tokens, we use `span <= distance + 1`.
            
            span = max_end - min_start
            dist_check = span <= (distance + 1)
            
            if dist_check:
                if not backward:
                    return True
                else:
                    # Check order: intervals should appear in order of words list
                    # combo is ((s1,e1), (s2,e2), ...) corresponding to words[0], words[1]...
                    # We need s1 < s2 < ...
                    # And we need to ensure no overlap? Or just start order?
                    # Usually just start order.
                    starts = [c[0] for c in combo]
                    if starts == sorted(starts):
                        return True
        return False

    elif mode == 'seq':
        for combo in itertools.product(*all_intervals):
            isValid = True
            for k in range(len(combo) - 1):
                # IntA = combo[k], IntB = combo[k+1]
                # A must be before B
                # A.end <= B.start
                
                startA, endA = combo[k]
                startB, endB = combo[k+1]
                
                if not (endA <= startB):
                    isValid = False
                    break
                
                # Distance check
                # Gap = startB - endA
                # Gap <= distance
                # Old logic: p2 - p1 <= distance. (p2 > p1)
                # p1=0, p2=1 (adjacent). 1-0=1 <= 1.
                # Gap: 1-1 = 0.
                # So Gap <= distance - 1?
                # If distance=1 (adjacent), Gap should be 0.
                # So Gap <= distance - 1.
                
                gap = startB - endA
                if not (gap <= distance - 1): # Wait, if distance is 1, gap<=0. Correct.
                    isValid = False
                    break
                    
            if isValid:
                return True
        return False

def check_keyword(keyword, text, surfaces, dict_forms, normalized_forms, token_starts, token_ends):
    """
    キーワード検索
    修正: テキスト内のキーワード出現位置が、形態素の境界と一致するかを確認する
    """
    # 1. Single token match (covers normalized/dict forms)
    for surf, dic, norm in zip(surfaces, dict_forms, normalized_forms):
        if keyword == surf or keyword == dic or keyword == norm:
            return True
            
    # 2. Phrase match (Surface form only)
    if keyword not in text:
        return False
        
    start_indices = []
    pos = text.find(keyword)
    while pos != -1:
        start_indices.append(pos)
        pos = text.find(keyword, pos + 1)
        
    keyword_len = len(keyword)
    
    for start in start_indices:
        end = start + keyword_len
        if start in token_starts and end in token_ends:
            return True
            
    return False

# --- 辞書と解析の準備 ---
def prepare_user_dictionary():
    print("ユーザー辞書を準備しています...")
    custom_words = set()

    # MeCab辞書読み込み
    if os.path.exists(MECAB_USER_DICT_PATH):
        try:
            with open(MECAB_USER_DICT_PATH, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                for row in reader:
                    if row: custom_words.add(row[0])
        except Exception as e:
            print(f"MeCab辞書エラー: {e}")

    # 強制抽出読み込み
    if os.path.exists(FORCED_EXTRACTION_PATH):
        try:
            with open(FORCED_EXTRACTION_PATH, 'r', encoding='utf-8') as f:
                for line in f:
                    w = line.strip()
                    if w: custom_words.add(w)
        except Exception as e:
            print(f"強制抽出エラー: {e}")

    if not custom_words:
        print("追加するユーザー辞書単語がありません。")
        return False

    # Sudachi CSV作成
    try:
        with open(SUDACHI_USER_DICT_CSV_PATH, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            for word in sorted(list(custom_words)):
                writer.writerow([
                    word, '4786', '4786', '5000', word,
                    '名詞', '固有名詞', '一般', '*', '*', '*',
                    word, word, '*', '*', '*', '*', '*'
                ])
        print(f"CSV生成完了: {len(custom_words)}語")
    except Exception as e:
        print(f"CSV作成エラー: {e}")
        return False

    # コンパイル
    print("ユーザー辞書をコンパイル中...")
    import subprocess
    sudachipy_path = os.path.join(os.path.dirname(sys.executable), 'sudachipy')
    import sudachidict_core
    system_dic_path = os.path.join(os.path.dirname(sudachidict_core.__file__), 'resources/system.dic')
    cmd = [sudachipy_path, "ubuild", "-s", system_dic_path, "-o", SUDACHI_USER_DICT_PATH, SUDACHI_USER_DICT_CSV_PATH]
    
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        print("コンパイル成功")
        return True
    except subprocess.CalledProcessError as e:
        print(f"コンパイル失敗: {e.stderr.decode('utf-8', errors='ignore')}")
        return False

def analyze_text():
    # 辞書作成トライ
    # has_user_dict = prepare_user_dictionary()
    has_user_dict = False
    
    # トークナイザー初期化
    try:
        if has_user_dict and os.path.exists(SUDACHI_USER_DICT_PATH):
            config_data = {"userDict": [SUDACHI_USER_DICT_PATH]}
            with open(SUDACHI_CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(config_data, f)
            print("ユーザー辞書ありモードで起動します")
            tokenizer_obj = dictionary.Dictionary(config_path=SUDACHI_CONFIG_PATH).create()
        else:
            print("標準辞書モードで起動します")
            tokenizer_obj = dictionary.Dictionary(dict="core").create()
        
        mode = tokenizer.Tokenizer.SplitMode.A # C(複合語) -> A(短単位)に変更
        print("Sudachi Tokenizer initialized (SplitMode.A)")
    except Exception as e:
        print(f"トークナイザー初期化失敗: {e}")
        return
    coding_rules = load_coding_rules()

    # DB読み込み
    if not os.path.exists(INPUT_DB_PATH):
        print(f"入力ファイルなし: {INPUT_DB_PATH}")
        return

    print(f"データ読み込み中: {INPUT_DB_PATH}")
    try:
        conn = sqlite3.connect(INPUT_DB_PATH)
        cursor = conn.cursor()
        
        query = """
            SELECT 
                p.text, 
                p.id, 
                m.name as municipality, 
                p.h5, 
                p.dan_number as dan 
            FROM paragraphs p 
            JOIN municipalities m ON p.municipality_id = m.id
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        
        paragraphs = []
        for row in rows:
            paragraphs.append({
                'text': row[0],
                'id': row[1],
                'municipality': row[2],
                'h5': row[3],
                'dan': row[4]
            })
            
        conn.close()
    except Exception as e:
        print(f"DB読み込みエラー: {e}")
        return

    print(f"対象段落数: {len(paragraphs)}")

    # 出力ファイル準備
    fieldnames = [
        'municipality', 'paragraph_num', 'doc_id', 'matched_codes',
        'morpheme_id', 'surface', 'pos1', 'pos2', 'pos3', 'pos4',
        'normalized_form', 'reading', 'dictionary_form'
    ]

    print(f"出力開始: {OUTPUT_CSV_PATH}")
    with open(OUTPUT_CSV_PATH, 'w', encoding='utf-8-sig', newline='') as f_out:
        writer = csv.DictWriter(f_out, fieldnames=fieldnames)
        writer.writeheader()

        count = 0
        for para in paragraphs:
            text = para.get('text')
            if not text: continue
            
            doc_id = para.get('id', para.get('municipality', 'unknown'))
            h5 = para.get('h5', '')
            dan = para.get('dan', '')
            p_num = f"{h5}-{dan}" if h5 and dan else ''
            municipality = para.get('municipality', '')

            try:
                morphemes = tokenizer_obj.tokenize(text, mode)
                
                # ルール適用 (この内部でSudachiの正規化形なども使われるようになった)
                matched = check_coding_rules(text, morphemes, coding_rules)
                codes_str = ','.join(matched)
                
                for i, m in enumerate(morphemes):
                    pos = m.part_of_speech()
                    row = {
                        'municipality': municipality,
                        'paragraph_num': p_num,
                        'doc_id': doc_id,
                        'matched_codes': codes_str,
                        'morpheme_id': i,
                        'surface': m.surface(),
                        'pos1': pos[0] if len(pos) > 0 else '*',
                        'pos2': pos[1] if len(pos) > 1 else '*',
                        'pos3': pos[2] if len(pos) > 2 else '*',
                        'pos4': pos[3] if len(pos) > 3 else '*',
                        'normalized_form': m.normalized_form(),
                        'reading': m.reading_form(),
                        'dictionary_form': m.dictionary_form(),
                    }
                    writer.writerow(row)
                
                count += 1
                if count % 100 == 0:
                    print(f"\r処理中: {count}/{len(paragraphs)} 段落完了", end='')

            except Exception as e:
                print(f"\nError at doc_id {doc_id}: {e}")
                traceback.print_exc()

    print(f"\n完了しました。結果: {OUTPUT_CSV_PATH}")

if __name__ == '__main__':
    analyze_text()