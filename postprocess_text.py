"""
条例・規則テキストファイルの後処理スクリプト

HTMLファイルとPDFファイルから抽出されたテキストを統一的な形式に整形する。
主な処理:
1. HTMLファイル: 号（(1)、ア など）を直前の文と同段落にし、句点を挿入
2. PDFファイル: 不要な改行・スペースを削除し、HTMLと同様の形式に整形
"""

import re
import os
from pathlib import Path


def is_gou_marker(line):
    """
    行が「号」（(1)、(2)、ア、イ など）で始まるかどうかを判定
    
    Args:
        line: 判定対象の行
    
    Returns:
        bool: 号で始まる場合True
    """
    line = line.strip()
    if not line:
        return False
    
    # (1), (2), (3) などの数字の号
    if re.match(r'^[(（]\d+[)）]', line):
        return True
    
    # ア、イ、ウ などのカタカナの号
    if re.match(r'^[ア-ン]', line):
        return True
    
    return False


def is_title_or_section(line):
    """
    行がタイトルや条・項番号かどうかを判定
    
    Args:
        line: 判定対象の行
    
    Returns:
        bool: タイトル・条・項番号の場合True
    """
    line = line.strip()
    if not line:
        return False
    
    # ページ番号（-1-、-2-など）
    if re.match(r'^[-－―ー]\s*\d+\s*[-－―ー]$', line):
        return True
    
    # 単純なページ番号（全角数字のみの行はページ番号とみなす）
    if re.match(r'^[０-９]+$', line):
        return True
    
    # 条例・規則名（○で始まる）
    if line.startswith('○'):
        return True
    
    # 日付（令和、平成など）- 単独で日付のみの行
    if re.match(r'^(令和|平成|昭和)[\d０-９]+年.{0,10}$', line):
        return True
    
    # 条例・規則番号 - 単独で番号のみの行
    if re.match(r'^(条例|規則|告示)第[\d０-９]+号\s*$', line):
        return True
    
    # 条番号（第1条、第2条など）- 単独で条番号のみの行
    # 条番号の後にスペースや本文が続く場合は除外
    if re.match(r'^第[\d０-９]+条\s*$', line):
        return True
    
    # 項番号（単独の半角数字）- ただし、段落中の数字と区別するため2以上のみ
    if re.match(r'^[2-9]$', line):
        return True
    
    # 括弧付き見出し（(趣旨)、(定義)など）- 全角半角両方対応、単独で見出しのみの行
    if re.match(r'^[（(][^)）]+[）)]\s*$', line):
        return True
    
    # 附則
    if line.startswith('附則') or line.startswith('附　則'):
        return True
    
    return False


def process_html_text(text):
    """
    HTMLから取得したテキストを処理
    
    号（(1)、ア など）を含む段落全体を1行にまとめる。
    条文と号の間の空行も削除する。
    
    Args:
        text: 処理対象のテキスト
    
    Returns:
        str: 処理後のテキスト
    """
    lines = text.split('\n')
    result = []
    
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        
        # 空行の場合
        if not stripped:
            # 次の行が号で始まる場合は空行をスキップ
            if i + 1 < len(lines) and is_gou_marker(lines[i + 1].strip()):
                i += 1
                continue
            # それ以外は空行を保持
            result.append('')
            i += 1
            continue
        
        # タイトル・条・項番号の場合
        if is_title_or_section(stripped):
            result.append(stripped)
            i += 1
            continue
        
        # 通常の行または号で始まる行
        # この行から始まる段落全体を結合する
        paragraph = stripped
        
        # 次の行を確認し、タイトルが来るまで結合（空行も含めて）
        i += 1
        while i < len(lines):
            next_stripped = lines[i].strip()
            
            # タイトルが来たら終了
            if next_stripped and is_title_or_section(next_stripped):
                break
            
            # 空行の場合、その次が号かどうか確認
            if not next_stripped:
                # 次の次の行を確認
                if i + 1 < len(lines) and is_gou_marker(lines[i + 1].strip()):
                    # 空行をスキップして次へ
                    i += 1
                    continue
                else:
                    # 段落の終わり
                    break
            
            # 号で始まる行の場合、句点がなければ追加
            if is_gou_marker(next_stripped):
                if not paragraph.endswith('。') and not paragraph.endswith('。）') and not paragraph.endswith('。」'):
                    paragraph += '。'
            
            # 次の行を結合
            paragraph += next_stripped
            i += 1
        
        result.append(paragraph)
    
    return '\n'.join(result)


def process_pdf_text(text):
    """
    PDFから取得したテキストを処理
    
    不要な改行・スペースを削除し、HTMLと同様の形式に整形する。
    
    Args:
        text: 処理対象のテキスト
    
    Returns:
        str: 処理後のテキスト
    """
    # 日本語文字間の不要なスペースを削除（行内のみ、改行は保持）
    def remove_japanese_spaces(text):
        # 全角文字のパターン（ひらがな、カタカナ、漢字、全角記号など）
        japanese_pattern = r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF\u3000-\u303F（）「」『』【】〔〕\uff01-\uff5e]'
        
        lines = text.split('\n')
        processed_lines = []
        
        for line in lines:
            # 各行内のスペースのみを削除（改行は保持）
            prev_line = None
            while prev_line != line:
                prev_line = line
                # 日本語文字 + スペース（改行以外） + 日本語文字 のパターンを置換
                line = re.sub(f'({japanese_pattern})[ 　\t]+({japanese_pattern})', r'\1\2', line)
            processed_lines.append(line)
        
        return '\n'.join(processed_lines)
    
    # テキスト全体から不要なスペースを削除（行内のみ）
    text = remove_japanese_spaces(text)
    
    lines = text.split('\n')
    
    # 前処理: 文の途中にある単一の空行を削除
    # 例: 「...安曇野市」\n\n「条例第3号...」 → 「...安曇野市」\n「条例第3号...」
    preprocessed_lines = []
    i = 0
    while i < len(lines):
        current = lines[i].strip()
        
        # 空行の場合
        if not current:
            # 前の行（preprocessed_linesの最後の行）を確認
            has_prev = len(preprocessed_lines) > 0 and preprocessed_lines[-1].strip()
            has_next = i + 1 < len(lines) and lines[i+1].strip()
            
            if has_prev and has_next:
                prev_line = preprocessed_lines[-1].strip()
                next_line = lines[i+1].strip()
                
                # 前の行が文の途中で終わっている（句点で終わらない）
                # かつ、次の行がタイトルや号で始まっていない場合は、空行をスキップ
                if (not prev_line.endswith('。') and 
                    not prev_line.endswith('。）') and 
                    not prev_line.endswith('。」') and
                    not is_title_or_section(next_line) and
                    not is_gou_marker(next_line)):
                    # 空行をスキップ（前の行と次の行を結合する）
                    i += 1
                    continue
        
        preprocessed_lines.append(lines[i])
        i += 1
    
    # メイン処理
    lines = preprocessed_lines
    result = []
    
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        
        # 空行の場合
        if not stripped:
            # 次の行が号で始まる場合は空行をスキップ
            if i + 1 < len(lines) and is_gou_marker(lines[i + 1].strip()):
                i += 1
                continue
            # それ以外は空行を保持
            result.append('')
            i += 1
            continue
        
        # タイトル・条・項番号の場合
        if is_title_or_section(stripped):
            result.append(stripped)
            i += 1
            continue
        
        # 号で始まる場合
        if is_gou_marker(stripped):
            # 直前の行が存在し、タイトルや空行でない場合は結合
            if result and result[-1] and not is_title_or_section(result[-1]):
                # 句点がない場合は追加
                if not result[-1].endswith('。') and not result[-1].endswith('。）') and not result[-1].endswith('。」'):
                    result[-1] += '。'
                result[-1] += stripped
            else:
                # 新しい行として開始
                result.append(stripped)
            
            # 号の後に続く行を結合
            i += 1
            while i < len(lines):
                next_stripped = lines[i].strip()
                
                # タイトルが来たら終了
                if next_stripped and is_title_or_section(next_stripped):
                    break
                
                # 空行の場合、その次が号かどうか確認
                if not next_stripped:
                    # 次の次の行を確認
                    if i + 1 < len(lines) and is_gou_marker(lines[i + 1].strip()):
                        # 空行をスキップして次へ
                        i += 1
                        continue
                    else:
                        # 段落の終わり
                        break
                
                # 別の号が来たら終了
                if is_gou_marker(next_stripped):
                    break
                
                # 続きの文を結合
                result[-1] += next_stripped
                i += 1
            continue
        
        # 通常の行（段落）
        # 新しい段落として開始
        paragraph = stripped
        
        # 次の行が続きかどうかを確認
        i += 1
        while i < len(lines):
            next_stripped = lines[i].strip()
            
            # タイトルが来たら終了
            if next_stripped and is_title_or_section(next_stripped):
                break
            
            # 空行の場合、その次が号かどうか確認
            if not next_stripped:
                # 次の次の行を確認
                if i + 1 < len(lines) and is_gou_marker(lines[i + 1].strip()):
                    # 空行をスキップして次へ
                    i += 1
                    continue
                else:
                    # 段落の終わり
                    break
            
            # 号が来た場合
            if is_gou_marker(next_stripped):
                # 句点を追加してから号を結合
                if not paragraph.endswith('。') and not paragraph.endswith('。）') and not paragraph.endswith('。」'):
                    paragraph += '。'
                paragraph += next_stripped
                i += 1
                continue
            
            # 続きの文を結合
            paragraph += next_stripped
            i += 1
        
        result.append(paragraph)
    
    return '\n'.join(result)


def process_file(input_path, output_dir):
    """
    ファイルを処理して結果を出力
    
    Args:
        input_path: 入力ファイルのパス
        output_dir: 出力ディレクトリのパス
    """
    # ファイルを読み込み
    with open(input_path, 'r', encoding='utf-8') as f:
        text = f.read()
    
    # ファイル名を取得
    filename = os.path.basename(input_path)
    
    # HTMLかPDFかを判定
    if filename.endswith('_HTML.txt'):
        processed = process_html_text(text)
        file_type = 'HTML'
    elif filename.endswith('_PDF.txt'):
        processed = process_pdf_text(text)
        file_type = 'PDF'
    else:
        print(f"スキップ: {filename} (HTML/PDFファイルではありません)")
        return
    
    # 出力ファイルパスを作成
    output_path = os.path.join(output_dir, filename)
    
    # 結果を出力
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(processed)
    
    print(f"処理完了 ({file_type}): {filename}")


def main():
    """
    メイン処理
    """
    # 入力・出力ディレクトリの設定
    input_dir = 'out'
    output_dir = 'out_processed'
    
    # 出力ディレクトリを作成
    os.makedirs(output_dir, exist_ok=True)
    
    # outディレクトリ内のすべてのテキストファイルを処理
    input_path = Path(input_dir)
    txt_files = list(input_path.glob('*.txt'))
    
    print(f"処理対象ファイル数: {len(txt_files)}")
    print("-" * 50)
    
    for txt_file in sorted(txt_files):
        process_file(str(txt_file), output_dir)
    
    print("-" * 50)
    print(f"すべての処理が完了しました。")
    print(f"結果は {output_dir} ディレクトリに保存されています。")


if __name__ == '__main__':
    main()
