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
        with open(CODING_RULES_PATH, 'r', encoding='utf-8') as f:
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
    
    for code, rule in rules.items():
        if evaluate_rule(text, surfaces, dict_forms, normalized_forms, rule):
            matched_codes.append(code)
    
    return matched_codes

def evaluate_rule(text, surfaces, dict_forms, normalized_forms, rule):
    try:
        return parse_and_evaluate(rule, text, surfaces, dict_forms, normalized_forms)
    except Exception:
        # ルール解析エラーは無視してFalseを返す
        return False

def parse_and_evaluate(expr, text, surfaces, dict_forms, normalized_forms):
    expr = expr.strip()
    
    # 括弧の処理
    if expr.startswith('(') and expr.endswith(')'):
        inner = expr[1:-1].strip()
        if split_by_operator(inner, 'or') == [inner] and split_by_operator(inner, 'and') == [inner]:
             pass 
        else:
             return parse_and_evaluate(inner, text, surfaces, dict_forms, normalized_forms)

    # or演算子
    parts = split_by_operator(expr, 'or')
    if len(parts) > 1:
        return any(parse_and_evaluate(p, text, surfaces, dict_forms, normalized_forms) for p in parts)
    
    # and演算子
    parts = split_by_operator(expr, 'and')
    if len(parts) > 1:
        return all(parse_and_evaluate(p, text, surfaces, dict_forms, normalized_forms) for p in parts)
    
    # not演算子
    if expr.lower().startswith('not '):
        return not parse_and_evaluate(expr[4:].strip(), text, surfaces, dict_forms, normalized_forms)
    
    # near構文
    near_match = re.match(r'near\s*\(([^)]+)\)\s*\[([b\d]+)\]', expr, re.IGNORECASE)
    if near_match:
        content = near_match.group(1)
        words = [w.strip() for w in content.split('-')]
        distance_str = near_match.group(2)
        backward = distance_str.startswith('b')
        distance = int(distance_str.replace('b', ''))
        return check_distance_logic(words, surfaces, dict_forms, normalized_forms, distance, backward, mode='near')
    
    # seq構文
    seq_match = re.match(r'seq\s*\(([^)]+)\)\s*\[([b\d]+)\]', expr, re.IGNORECASE)
    if seq_match:
        content = seq_match.group(1)
        words = [w.strip() for w in content.split('-')]
        distance_str = seq_match.group(2)
        backward = distance_str.startswith('b')
        distance = int(distance_str.replace('b', ''))
        return check_distance_logic(words, surfaces, dict_forms, normalized_forms, distance, backward, mode='seq')
    
    # 単純キーワード (修正: テキスト検索ではなく単語検索へ)
    return check_keyword(expr, surfaces, dict_forms, normalized_forms)

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

def check_distance_logic(words, surfaces, dict_forms, normalized_forms, distance, backward, mode='near'):
    """nearとseqのロジック統合版 (単語単位での位置特定)"""
    
    # 各単語の出現位置リストを取得
    positions = []
    for word in words:
        word_pos = []
        # 表層形、辞書形、正規化形のいずれかに一致すればその位置を記録
        # zipでまとめてループ
        for i, (surf, dic, norm) in enumerate(zip(surfaces, dict_forms, normalized_forms)):
            # 完全一致で判定 (KH Coderの挙動に合わせる)
            if word == surf or word == dic or word == norm:
                word_pos.append(i)
        
        if not word_pos:
            return False
        positions.append(word_pos)
    
    import itertools
    if mode == 'near':
        for combo in itertools.product(*positions):
            sorted_idx = sorted(combo)
            min_idx = sorted_idx[0]
            max_idx = sorted_idx[-1]
            dist_check = (max_idx - min_idx) <= distance
            if dist_check:
                if not backward:
                    return True
                else:
                    if list(combo) == sorted(list(combo)):
                        return True
        return False

    elif mode == 'seq':
        for combo in itertools.product(*positions):
            isValid = True
            for k in range(len(combo) - 1):
                p1 = combo[k]
                p2 = combo[k+1]
                if not (p1 < p2 and (p2 - p1) <= distance):
                    isValid = False
                    break
            if isValid:
                return True
        return False

def check_keyword(keyword, surfaces, dict_forms, normalized_forms):
    """
    単純なキーワード検索
    修正: 生テキストの部分一致ではなく、形態素リストとの完全一致を確認する
    """
    for surf, dic, norm in zip(surfaces, dict_forms, normalized_forms):
        if keyword == surf or keyword == dic or keyword == norm:
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
    cmd = [sys.executable, "-m", "sudachipy", "ubuild", "-o", SUDACHI_USER_DICT_PATH, SUDACHI_USER_DICT_CSV_PATH]
    
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        print("コンパイル成功")
        return True
    except subprocess.CalledProcessError as e:
        print(f"コンパイル失敗: {e.stderr.decode('utf-8', errors='ignore')}")
        return False

def analyze_text():
    # 辞書作成トライ
    has_user_dict = prepare_user_dictionary()
    
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
    except Exception as e:
        print(f"トークナイザー初期化失敗: {e}")
        return

    mode = tokenizer.Tokenizer.SplitMode.C
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