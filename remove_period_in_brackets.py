#!/usr/bin/env python3
"""
括弧内の句点「。」を削除するスクリプト

処理内容:
- 括弧（全角：（）、半角：()）に囲まれた句点「。」を削除
- 括弧に囲まれていない句点は削除しない
- ネストされた括弧にも対応

入力: /home/ubuntu/cur/isep/texts/main4.3_2025-11-17.v.2.csv
出力: /home/ubuntu/cur/isep/texts/main4.3_2025-11-17.v.3.csv
"""

import csv
import re
from pathlib import Path


def remove_period_in_brackets(text: str) -> str:
    """
    括弧内の句点「。」を削除する。
    
    括弧の種類:
    - 全角: （ ）
    - 半角: ( )
    
    ネストされた括弧にも対応するため、スタックベースのアルゴリズムを使用。
    """
    if not text:
        return text
    
    # 括弧の対応を定義
    open_brackets = {'（', '('}
    close_brackets = {'）', ')'}
    bracket_pairs = {'（': '）', '(': ')'}
    
    result = []
    bracket_stack = []  # 開き括弧のスタック
    
    for char in text:
        if char in open_brackets:
            # 開き括弧: スタックに追加
            bracket_stack.append(char)
            result.append(char)
        elif char in close_brackets:
            # 閉じ括弧: スタックからポップ（対応する開き括弧がある場合）
            if bracket_stack:
                # 対応する括弧かどうかをチェック
                expected_close = bracket_pairs.get(bracket_stack[-1])
                if char == expected_close:
                    bracket_stack.pop()
            result.append(char)
        elif char == '。':
            # 句点: 括弧内（スタックが空でない）の場合は削除
            if bracket_stack:
                # 括弧内なので句点を削除（追加しない）
                pass
            else:
                # 括弧外なので句点を保持
                result.append(char)
        else:
            result.append(char)
    
    return ''.join(result)


def process_csv(input_path: str, output_path: str):
    """
    CSVファイルを処理し、指定された列の括弧内句点を削除する。
    """
    input_file = Path(input_path)
    output_file = Path(output_path)
    
    if not input_file.exists():
        raise FileNotFoundError(f"入力ファイルが見つかりません: {input_path}")
    
    # 統計情報
    total_rows = 0
    modified_rows = 0
    total_periods_removed = 0
    
    with open(input_file, 'r', encoding='utf-8') as infile, \
         open(output_file, 'w', encoding='utf-8', newline='') as outfile:
        
        reader = csv.DictReader(infile)
        fieldnames = reader.fieldnames
        
        if not fieldnames:
            raise ValueError("CSVファイルにヘッダーがありません")
        
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for row in reader:
            total_rows += 1
            original_text = row.get('本文', '')
            processed_text = remove_period_in_brackets(original_text)
            
            # 変更があったかチェック
            if original_text != processed_text:
                modified_rows += 1
                # 削除された句点の数をカウント
                periods_removed = original_text.count('。') - processed_text.count('。')
                total_periods_removed += periods_removed
            
            row['本文'] = processed_text
            writer.writerow(row)
    
    print(f"処理完了:")
    print(f"  入力ファイル: {input_path}")
    print(f"  出力ファイル: {output_path}")
    print(f"  総行数: {total_rows}")
    print(f"  変更された行数: {modified_rows}")
    print(f"  削除された句点の総数: {total_periods_removed}")


def test_remove_period():
    """
    テストケース
    """
    test_cases = [
        # (入力, 期待される出力)
        ("これはテスト。", "これはテスト。"),  # 括弧外の句点は保持
        ("（以下「事業」という。）", "（以下「事業」という）"),  # 括弧内の句点は削除
        ("(送電に係る鉄柱等を除く。)", "(送電に係る鉄柱等を除く)"),  # 半角括弧
        ("本文。（注釈。）続き。", "本文。（注釈）続き。"),  # 混在
        ("（外側（内側。）終わり。）", "（外側（内側）終わり）"),  # ネスト
        ("（一。）と（二。）", "（一）と（二）"),  # 複数括弧
        ("テスト文。", "テスト文。"),  # 括弧なし
        ("（）", "（）"),  # 空の括弧
        ("（テスト）", "（テスト）"),  # 括弧内に句点なし
        # 複雑なケース
        ("再生可能エネルギー（平成23年法律第108号。以下「法」という。）に基づく。",
         "再生可能エネルギー（平成23年法律第108号以下「法」という）に基づく。"),
    ]
    
    print("テスト実行:")
    all_passed = True
    for i, (input_text, expected) in enumerate(test_cases, 1):
        result = remove_period_in_brackets(input_text)
        status = "✓" if result == expected else "✗"
        if result != expected:
            all_passed = False
            print(f"  {status} テスト {i}:")
            print(f"      入力: {input_text}")
            print(f"      期待: {expected}")
            print(f"      結果: {result}")
        else:
            print(f"  {status} テスト {i}: OK")
    
    if all_passed:
        print("\nすべてのテストに合格しました。")
    else:
        print("\n一部のテストに失敗しました。")
    
    return all_passed


def show_examples(input_path: str, num_examples: int = 5):
    """
    処理例を表示する
    """
    print(f"\n処理例（最初の{num_examples}件の変更）:")
    
    with open(input_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            original = row.get('本文', '')
            processed = remove_period_in_brackets(original)
            if original != processed:
                count += 1
                print(f"\n例 {count}:")
                # 変更箇所を見つける
                # 括弧内の句点を含む部分を抽出
                pattern = r'[（(][^）)]*。[^）)]*[）)]'
                matches = re.findall(pattern, original)
                if matches:
                    for match in matches[:3]:  # 最大3つまで表示
                        processed_match = remove_period_in_brackets(match)
                        print(f"  変更前: {match}")
                        print(f"  変更後: {processed_match}")
                
                if count >= num_examples:
                    break


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='括弧内の句点を削除するスクリプト')
    parser.add_argument('--test', action='store_true', help='テストを実行')
    parser.add_argument('--examples', action='store_true', help='処理例を表示')
    parser.add_argument('--run', action='store_true', help='実際の処理を実行')
    parser.add_argument('--input', type=str, 
                        default='/home/ubuntu/cur/isep/texts/main4.3_2025-11-17.v.2.csv',
                        help='入力CSVファイルパス')
    parser.add_argument('--output', type=str,
                        default='/home/ubuntu/cur/isep/texts/main4.3_2025-11-17.v.3.csv',
                        help='出力CSVファイルパス')
    
    args = parser.parse_args()
    
    if args.test:
        test_remove_period()
    
    if args.examples:
        show_examples(args.input)
    
    if args.run:
        process_csv(args.input, args.output)
    
    if not (args.test or args.examples or args.run):
        # デフォルト: テスト、例、処理を順番に実行
        print("=" * 60)
        test_remove_period()
        print("\n" + "=" * 60)
        show_examples(args.input)
        print("\n" + "=" * 60)
        print("\n処理を実行するには --run オプションを使用してください:")
        print(f"  python {__file__} --run")
