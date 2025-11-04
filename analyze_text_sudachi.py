
import pandas as pd
from sudachipy import tokenizer
from sudachipy import dictionary
import os
import csv
import json
import re

# --- 設定 ---
INPUT_JSON_PATH = '/home/ubuntu/cur/isep/clause-viewer/data-integrated.json'
MECAB_USER_DICT_PATH = '/home/ubuntu/cur/isep/solar_ordinance_userdic_mecab_safe_refined.csv'
FORCED_EXTRACTION_PATH = '/home/ubuntu/cur/isep/強制抽出_v2.0.txt'
CODING_RULES_PATH = '/home/ubuntu/cur/isep/khcoder_coding_rules_PV_v3.5.txt'
SUDACHI_USER_DICT_CSV_PATH = '/home/ubuntu/cur/isep/sudachi_user.csv'
SUDACHI_USER_DICT_PATH = '/home/ubuntu/cur/isep/sudachi_user.dic'
OUTPUT_CSV_PATH = '/home/ubuntu/cur/isep/analysis_results_sudachi_paragraphs.csv'

# --- コーディングルールの読み込み ---
def load_coding_rules():
    """
    KH Coderのコーディングルールファイルを読み込み、辞書形式で返す
    """
    rules = {}
    current_code = None
    
    try:
        with open(CODING_RULES_PATH, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if line.startswith('*'):
                    current_code = line
                    rules[current_code] = ''
                elif current_code:
                    rules[current_code] += ' ' + line
        
        # 各ルールをクリーンアップ
        for code in rules:
            rules[code] = rules[code].strip()
        
        print(f"コーディングルール {len(rules)} 件を読み込みました")
        return rules
    except Exception as e:
        print(f"コーディングルール読み込みエラー: {e}")
        return {}

# --- 簡易的なルール判定（キーワードベース） ---
def check_coding_rules(text, morphemes, rules):
    """
    テキストと形態素リストに対してコーディングルールを適用
    該当するコードのリストを返す
    """
    matched_codes = []
    
    # 形態素の表層形と原形のリストを作成
    surfaces = [m.surface() for m in morphemes]
    dict_forms = [m.dictionary_form() for m in morphemes]
    
    for code, rule in rules.items():
        if evaluate_rule(text, surfaces, dict_forms, rule):
            matched_codes.append(code)
    
    return matched_codes

def evaluate_rule(text, surfaces, dict_forms, rule):
    """
    KH Coderのルール構文を完全に評価
    """
    # ルールを評価可能な形に変換
    try:
        return parse_and_evaluate(rule, text, surfaces, dict_forms)
    except Exception as e:
        # エラーが発生した場合は該当なしとする
        return False

def parse_and_evaluate(expr, text, surfaces, dict_forms):
    """
    式を再帰的にパースして評価
    """
    expr = expr.strip()
    
    # 括弧の処理
    if expr.startswith('(') and expr.endswith(')'):
        # 最外の括弧を除去
        expr = expr[1:-1].strip()
    
    # or演算子で分割（最も優先度が低い）
    parts = split_by_operator(expr, 'or')
    if len(parts) > 1:
        return any(parse_and_evaluate(part, text, surfaces, dict_forms) for part in parts)
    
    # and演算子で分割
    parts = split_by_operator(expr, 'and')
    if len(parts) > 1:
        return all(parse_and_evaluate(part, text, surfaces, dict_forms) for part in parts)
    
    # not演算子の処理
    if expr.startswith('not '):
        return not parse_and_evaluate(expr[4:].strip(), text, surfaces, dict_forms)
    
    # near構文の処理
    near_match = re.match(r'near\(([^)]+)\)\[([b\d]+)\]', expr)
    if near_match:
        words = near_match.group(1).split('-')
        distance_str = near_match.group(2)
        # bが付いている場合は後方検索、数値のみは前方検索
        backward = distance_str.startswith('b')
        distance = int(distance_str.replace('b', ''))
        return check_near(words, surfaces, dict_forms, distance, backward)
    
    # seq構文の処理
    seq_match = re.match(r'seq\(([^)]+)\)\[([b\d]+)\]', expr)
    if seq_match:
        words = seq_match.group(1).split('-')
        distance_str = seq_match.group(2)
        backward = distance_str.startswith('b')
        distance = int(distance_str.replace('b', ''))
        return check_seq(words, surfaces, dict_forms, distance, backward)
    
    # 単純なキーワード検索
    keyword = expr.strip()
    return check_keyword(keyword, text, surfaces, dict_forms)

def split_by_operator(expr, operator):
    """
    括弧のネストを考慮して演算子で式を分割
    """
    parts = []
    current = []
    depth = 0
    i = 0
    
    while i < len(expr):
        char = expr[i]
        
        if char == '(':
            depth += 1
            current.append(char)
        elif char == ')':
            depth -= 1
            current.append(char)
        elif depth == 0:
            # 演算子の検出
            if expr[i:i+len(operator)+2] == f' {operator} ':
                parts.append(''.join(current).strip())
                current = []
                i += len(operator) + 1
            else:
                current.append(char)
        else:
            current.append(char)
        
        i += 1
    
    if current:
        parts.append(''.join(current).strip())
    
    return parts if len(parts) > 1 else [expr]

def check_near(words, surfaces, dict_forms, distance, backward=False):
    """
    near構文の判定: 複数の単語が指定距離内に出現するか
    """
    all_terms = surfaces + dict_forms
    
    # 各単語の出現位置を取得
    positions = {}
    for word in words:
        positions[word] = []
        for i, term in enumerate(all_terms):
            if word in term or term in word:
                positions[word].append(i)
    
    # すべての単語が出現しているか確認
    if not all(positions[word] for word in words):
        return False
    
    # 任意の組み合わせで距離条件を満たすか確認
    for i, word1 in enumerate(words[:-1]):
        for pos1 in positions[word1]:
            for word2 in words[i+1:]:
                for pos2 in positions[word2]:
                    if backward:
                        # 後方検索: word2がword1より前にあり、距離以内
                        if pos2 < pos1 and pos1 - pos2 <= distance:
                            return True
                    else:
                        # 前方検索: word2がword1より後にあり、距離以内
                        if pos2 > pos1 and pos2 - pos1 <= distance:
                            return True
    
    return False

def check_seq(words, surfaces, dict_forms, distance, backward=False):
    """
    seq構文の判定: 単語が指定された順序で距離内に出現するか
    """
    all_terms = surfaces + dict_forms
    
    # 最初の単語の位置を探す
    first_word = words[0]
    for i, term in enumerate(all_terms):
        if first_word in term or term in first_word:
            # この位置から順番に他の単語を探す
            current_pos = i
            found_all = True
            
            for next_word in words[1:]:
                found = False
                search_range = range(current_pos + 1, min(current_pos + distance + 1, len(all_terms)))
                
                if backward:
                    search_range = range(max(0, current_pos - distance), current_pos)
                
                for j in search_range:
                    if next_word in all_terms[j] or all_terms[j] in next_word:
                        current_pos = j
                        found = True
                        break
                
                if not found:
                    found_all = False
                    break
            
            if found_all:
                return True
    
    return False

def check_keyword(keyword, text, surfaces, dict_forms):
    """
    単純なキーワード検索
    """
    all_terms = surfaces + dict_forms
    
    # テキスト中に直接含まれるか
    if keyword in text:
        return True
    
    # 形態素リストに含まれるか
    for term in all_terms:
        if keyword == term or keyword in term:
            return True
    
    return False

# --- 1. ユーザー辞書の準備 ---
def prepare_user_dictionary():
    """
    MeCabのユーザー辞書と強制抽出リストを読み込み、Sudachi用のユーザー辞書ファイルを作成する。
    """
    print("ユーザー辞書を準備しています...")
    custom_words = set()

    # MeCab辞書から単語を読み込み
    try:
        with open(MECAB_USER_DICT_PATH, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if row:
                    custom_words.add(row[0])
    except FileNotFoundError:
        print(f"警告: MeCabユーザー辞書が見つかりません: {MECAB_USER_DICT_PATH}")
    except Exception as e:
        print(f"MeCabユーザー辞書読み込みエラー: {e}")


    # 強制抽出リストから単語を読み込み
    try:
        with open(FORCED_EXTRACTION_PATH, 'r', encoding='utf-8') as f:
            for line in f:
                word = line.strip()
                if word:
                    custom_words.add(word)
    except FileNotFoundError:
        print(f"警告: 強制抽出ファイルが見つかりません: {FORCED_EXTRACTION_PATH}")
    except Exception as e:
        print(f"強制抽出ファイル読み込みエラー: {e}")

    # Sudachi用ユーザー辞書ファイルを作成（CSV形式）
    # Sudachi辞書のCSVフォーマット (18列, RFC4180):
    # 1表層形, 2左連接ID, 3右連接ID, 4コスト, 5見出し, 6品詞1, 7品詞2, 8品詞3,
    # 9品詞4, 10活用型, 11活用形, 12読み, 13正規化表記, 14辞書形ID,
    # 15分割タイプ, 16A単位, 17B単位, 18未使用
    with open(SUDACHI_USER_DICT_CSV_PATH, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        for word in sorted(list(custom_words)):
            left_id = '4786'
            right_id = '4786'
            cost = '5000'
            reading = word  # 読み指定が無ければ表層形
            normalized = word  # 正規化表記は表層形を再利用

            writer.writerow([
                word,          # 表層形
                left_id,       # 左連接ID
                right_id,      # 右連接ID
                cost,          # 連接コスト
                word,          # 見出し
                '名詞',        # 品詞1
                '固有名詞',    # 品詞2
                '一般',        # 品詞3
                '*',           # 品詞4
                '*',           # 活用型
                '*',           # 活用形
                reading,       # 読み
                normalized,    # 正規化表記
                '*',           # 辞書形ID
                '*',           # 分割タイプ
                '*',           # A単位
                '*',           # B単位
                '*'            # 未使用
            ])
    
    print(f"Sudachi用ユーザー辞書CSVを作成しました: {SUDACHI_USER_DICT_CSV_PATH} ({len(custom_words)}語)")
    
    # CSVをバイナリ辞書にコンパイル
    print("ユーザー辞書をコンパイルしています...")
    import subprocess
    import sys
    
    # 仮想環境のsudachipyコマンドパスを構築
    venv_bin = os.path.dirname(sys.executable)
    sudachipy_cmd = os.path.join(venv_bin, 'sudachipy')
    
    # システム辞書のパスを探す
    try:
        import site
        site_packages = site.getsitepackages()[0]
        system_dict_path = os.path.join(site_packages, 'sudachidict_core', 'resources', 'system.dic')
        
        if not os.path.exists(system_dict_path):
            # 別の場所を試す
            import sudachidict_core
            dict_dir = os.path.dirname(sudachidict_core.__file__)
            system_dict_path = os.path.join(dict_dir, 'resources', 'system.dic')
    except Exception as e:
        print(f"警告: システム辞書のパス取得に失敗: {e}")
        print("ユーザー辞書のコンパイルをスキップします。")
        return False
    
    print(f"システム辞書: {system_dict_path}")
    
    try:
        result = subprocess.run(
            [sudachipy_cmd, 'ubuild', '-s', system_dict_path, '-o', SUDACHI_USER_DICT_PATH, SUDACHI_USER_DICT_CSV_PATH],
            capture_output=True,
            text=True,
            check=True
        )
        print(f"ユーザー辞書のコンパイルが完了しました: {SUDACHI_USER_DICT_PATH}")
        if result.stdout:
            print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"警告: ユーザー辞書のコンパイルに失敗しました")
        print(f"エラー詳細: {e.stderr}")
        print("ユーザー辞書なしで処理を続行します。")
        return False
    except Exception as e:
        print(f"警告: {e}")
        print("ユーザー辞書なしで処理を続行します。")
        return False

# --- 2. 形態素解析の実行 ---
def analyze_text():
    """
    JSONファイルを読み込み、段落ごとにSudachiで形態素解析を実行し、結果をCSVに出力する。
    """
    # ユーザー辞書を準備
    user_dict_success = prepare_user_dictionary()

    # Sudachiトークナイザーを初期化
    print("Sudachiトークナイザーを初期化しています...")
    
    # ユーザー辞書があれば設定ファイルを作成
    config = None
    if user_dict_success and os.path.exists(SUDACHI_USER_DICT_PATH):
        import json as config_json
        config = {
            "userDict": [SUDACHI_USER_DICT_PATH]
        }
        config_path = '/home/ubuntu/cur/isep/sudachi_config.json'
        with open(config_path, 'w', encoding='utf-8') as f:
            config_json.dump(config, f, ensure_ascii=False, indent=2)
        print(f"ユーザー辞書設定ファイルを作成しました: {config_path}")
        
        try:
            # 設定ファイルを使ってトークナイザーを初期化
            tokenizer_obj = dictionary.Dictionary(config_path=config_path, dict="core").create()
            print("ユーザー辞書を適用したトークナイザーを初期化しました。")
        except Exception as e:
            print(f"ユーザー辞書付きの初期化に失敗: {e}")
            print("デフォルト辞書で初期化します。")
            tokenizer_obj = dictionary.Dictionary(dict="core").create()
    else:
        print(f"ユーザー辞書なしでトークナイザーを初期化します")
        tokenizer_obj = dictionary.Dictionary(dict="core").create()
        print("デフォルト辞書で初期化しました。")

    mode = tokenizer.Tokenizer.SplitMode.C

    # 入力JSONを読み込み
    print(f"入力ファイルを読み込んでいます: {INPUT_JSON_PATH}")
    try:
        with open(INPUT_JSON_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        paragraphs = data.get('paragraphs', [])
        if not paragraphs:
            print("エラー: JSON内に 'paragraphs' が見つからないか、空です。")
            return
    except FileNotFoundError:
        print(f"エラー: 入力ファイルが見つかりません: {INPUT_JSON_PATH}")
        return
    except json.JSONDecodeError:
        print(f"エラー: JSONの解析に失敗しました: {INPUT_JSON_PATH}")
        return
    except Exception as e:
        print(f"入力ファイルの読み込みエラー: {e}")
        return

    # 解析結果を格納するリスト
    analysis_results = []
    
    # コーディングルールを読み込み
    coding_rules = load_coding_rules()
    
    print("形態素解析を開始します...")
    # 各段落の本文を解析
    for para in paragraphs:
        text = para.get('text')
        # doc_idを段落のidキーから取得
        doc_id = para.get('id', para.get('municipality', 'unknown'))
        # 段落番号を取得（h5-dan形式）
        h5 = para.get('h5', '')
        dan = para.get('dan', '')
        paragraph_num = f"{h5}-{dan}" if h5 and dan else ''
        # 自治体名を取得
        municipality = para.get('municipality', '')

        if not text or pd.isna(text):
            continue

        try:
            morphemes = tokenizer_obj.tokenize(text, mode)
            
            # コーディングルールを適用
            matched_codes = check_coding_rules(text, morphemes, coding_rules)
            codes_str = ','.join(matched_codes) if matched_codes else ''
            
            for i, m in enumerate(morphemes):
                analysis_results.append({
                    'municipality': municipality,
                    'paragraph_num': paragraph_num,
                    'doc_id': doc_id,
                    'matched_codes': codes_str,
                    'morpheme_id': i,
                    'surface': m.surface(),
                    'pos1': m.part_of_speech()[0],
                    'pos2': m.part_of_speech()[1],
                    'pos3': m.part_of_speech()[2],
                    'pos4': m.part_of_speech()[3],
                    'conjugated_type': m.part_of_speech()[4],
                    'conjugated_form': m.part_of_speech()[5],
                    'normalized_form': m.normalized_form(),
                    'reading': m.reading_form(),
                    'dictionary_form': m.dictionary_form(),
                })
        except Exception as e:
            print(f"doc_id {doc_id} の解析中にエラーが発生しました: {e}")


    print("解析が完了しました。結果をファイルに出力します...")
    # 結果をDataFrameに変換してCSVに出力
    results_df = pd.DataFrame(analysis_results)
    try:
        results_df.to_csv(OUTPUT_CSV_PATH, index=False, encoding='utf-8-sig')
        print(f"解析結果を {OUTPUT_CSV_PATH} に保存しました。")
    except Exception as e:
        print(f"結果の保存中にエラーが発生しました: {e}")

if __name__ == '__main__':
    analyze_text()
