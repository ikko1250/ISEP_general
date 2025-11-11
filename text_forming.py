#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import pandas as pd
import os
import glob
import sys
import argparse

def format_text(text):
    """
    テキストを整形する。「号」レベル（(1), (2), （1）など）と
    カタカナ（ア、イ、ウなど）で始まる行の前の改行を削除する。
    
    Parameters:
    - text: 入力テキスト
    
    Returns:
    - formatted_text: 整形されたテキスト
    """
    # 行ごとに分割
    lines = text.split('\n')
    
    # 整形後のテキストを格納y
    formatted_lines = []
    
    for i, line in enumerate(lines):
        line_stripped = line.strip()
        
        # 空行はスキップ
        if not line_stripped:
            continue
        
        # 「号」パターン: (1), (2), （1）, （2） など（括弧+数字）で始まる行
        is_gou = re.match(r'^[（\(]\d+[）\)]', line_stripped)
        
        # カタカナパターン: ア、イ、ウ、エ、オ などで始まる行
        is_katakana = re.match(r'^[ァ-ヶー]+[\s　]', line_stripped) or re.match(r'^[ァ-ヶー]+$', line_stripped) or re.match(r'^[ァ-ヶー]+[^ァ-ヶー]', line_stripped)
        
        if (is_gou or is_katakana) and formatted_lines:
            # 号またはカタカナの場合は改行せず、直前の行に連結
            # 前の行の末尾に「。」がない場合は追加
            if not formatted_lines[-1].endswith('。'):
                formatted_lines[-1] += '。'
            formatted_lines[-1] += line_stripped
        else:
            # それ以外（条、項など）は改行を保持
            formatted_lines.append(line_stripped)
    
    # 整形されたテキストを結合
    formatted_text = '\n'.join(formatted_lines)
    
    return formatted_text

def extract_metadata_from_filename(filename):
    """
    ファイル名から自治体名と区分を抽出する
    例: "芳賀町_Haga_Town_Ordinance_PDF.txt" -> ("芳賀町", "条例")
        "Haga_Town_Ordinance_PDF.txt" -> ("Haga Town", "条例")
        "Haga_Town_Regulation_HTML.txt" -> ("Haga Town", "施行規則")
    
    Parameters:
    - filename: ファイル名
    
    Returns:
    - jichitai: 自治体名
    - kubun: 区分
    """
    # 拡張子を除去
    name = os.path.splitext(filename)[0]
    
    # "_PDF", "_HTML", "_Ordinance", "_Regulation" などのノイズを除去
    # 区分を判定
    if 'Ordinance' in name:
        kubun = '条例'
        name = name.replace('_Ordinance', '')
    elif 'Regulation' in name:
        kubun = '施行規則'
        name = name.replace('_Regulation', '')
    else:
        kubun = '不明'
    
    # PDFやHTMLのノイズを除去
    name = name.replace('_PDF', '').replace('_HTML', '')
    
    # 日本語と英語が混在している場合、日本語を優先
    # アンダースコアで分割
    parts = name.split('_')
    
    # 日本語を含む部分を探す
    japanese_parts = []
    for part in parts:
        # 日本語文字（ひらがな、カタカナ、漢字）が含まれているかチェック
        if re.search(r'[ぁ-んァ-ヶ一-龥]', part):
            japanese_parts.append(part)
    
    # 日本語がある場合は日本語を優先、なければ英語部分を使用
    if japanese_parts:
        jichitai = '_'.join(japanese_parts)
    else:
        # 英語の場合はスペースに変換
        jichitai = name.replace('_', ' ').strip()
    
    return jichitai, kubun

def get_available_years():
    """利用可能な年別ディレクトリのリストを取得"""
    years = set()
    
    # out_xxxx形式のディレクトリを検索
    pattern = "out_*"
    dirs = glob.glob(pattern)
    for d in dirs:
        if os.path.isdir(d):
            match = re.search(r'out_(\d{4})$', d)
            if match:
                years.add(match.group(1))
    
    # out_txt_xxxx形式のディレクトリを検索
    pattern = "out_txt_*"
    dirs = glob.glob(pattern)
    for d in dirs:
        if os.path.isdir(d):
            match = re.search(r'out_txt_(\d{4})$', d)
            if match:
                years.add(match.group(1))
    
    return sorted(list(years))

def parse_year_range(year_input):
    """年の範囲文字列を解析して年のリストを返す"""
    if not year_input:
        return []
    
    if '-' in year_input:
        # 範囲指定（例: 2014-2018）
        try:
            start_year, end_year = year_input.split('-', 1)
            start_year = int(start_year.strip())
            end_year = int(end_year.strip())
            if start_year > end_year:
                print(f"エラー: 開始年（{start_year}）が終了年（{end_year}）より大きいです。")
                sys.exit(1)
            return [str(year) for year in range(start_year, end_year + 1)]
        except ValueError:
            print(f"エラー: 年の範囲指定が無効です: {year_input}")
            print("正しい形式: YYYY-YYYY (例: 2014-2018)")
            sys.exit(1)
    else:
        # 単年指定（例: 2015）
        try:
            year = int(year_input.strip())
            return [str(year)]
        except ValueError:
            print(f"エラー: 年の指定が無効です: {year_input}")
            print("正しい形式: YYYY または YYYY-YYYY (例: 2015 または 2014-2018)")
            sys.exit(1)

def extract_year_from_directory(directory):
    """
    ディレクトリ名から制定年を抽出する
    例: "out_2022" -> "2022"
        "out_txt_2023" -> "2023"
    
    Parameters:
    - directory: ディレクトリ名
    
    Returns:
    - year: 制定年（文字列）、抽出できない場合はNone
    """
    # ディレクトリ名から4桁の数字を抽出
    match = re.search(r'(\d{4})', directory)
    if match:
        return match.group(1)
    return None

def get_target_directories(years=None):
    """
    処理対象のディレクトリリストを取得
    out_xxxx と out_txt_xxxx の両方を対象とする
    
    Parameters:
    - years: 対象年のリスト。Noneの場合は全ての利用可能な年
    
    Returns:
    - directories: 存在するディレクトリのリスト
    """
    if years is None:
        years = get_available_years()
    
    directories = []
    missing_years = []
    
    for year in years:
        year_dirs = []
        
        # out_xxxx形式のディレクトリをチェック
        out_dir = f"out_{year}"
        if os.path.exists(out_dir) and os.path.isdir(out_dir):
            year_dirs.append(out_dir)
        
        # out_txt_xxxx形式のディレクトリをチェック
        out_txt_dir = f"out_txt_{year}"
        if os.path.exists(out_txt_dir) and os.path.isdir(out_txt_dir):
            year_dirs.append(out_txt_dir)
        
        if year_dirs:
            directories.extend(year_dirs)
        else:
            missing_years.append(year)
    
    if missing_years:
        print(f"警告: 以下の年のディレクトリが見つかりません: {', '.join(missing_years)}")
        print("       対象ディレクトリ形式: out_YYYY, out_txt_YYYY")
    
    return directories

def process_multiple_files(directories, output_csv):
    """
    複数のディレクトリからテキストファイルを読み込み、整形してCSVにまとめる
    ディレクトリ名から制定年を自動判定する
    
    Parameters:
    - directories: テキストファイルが格納されているディレクトリのリスト
    - output_csv: 出力CSVファイルのパス
    
    Returns:
    - success_count: 成功した件数
    - error_count: エラーが発生した件数
    - duplicate_count: 重複した件数
    """
    all_data = []
    success_count = 0
    error_count = 0
    duplicate_count = 0
    
    # 処理済みファイルを記録するセット（ファイル名 + 制定年 + 区分の組み合わせ）
    processed_files = set()
    
    # 既存のCSVを読み込み（存在する場合）
    existing_df = None
    if os.path.exists(output_csv):
        try:
            existing_df = pd.read_csv(output_csv)
            if len(existing_df) > 0:
                print(f"既存のCSVファイルを読み込みました: {len(existing_df)} 行")
                # 既存のエントリーを処理済みセットに追加
                for _, row in existing_df.iterrows():
                    key = f"{row['自治体']}_{row['制定年']}_{row['区分']}"
                    processed_files.add(key)
            else:
                print("既存のCSVファイルは空です。新規作成します。")
                existing_df = None
        except (pd.errors.EmptyDataError, pd.errors.ParserError) as e:
            print(f"既存のCSVファイルの読み込みに失敗しました: {str(e)}")
            print("新しいCSVファイルを作成します。")
            existing_df = None
    
    # 各ディレクトリからテキストファイルを取得
    for directory in directories:
        if not os.path.exists(directory):
            print(f"⚠️  ディレクトリが見つかりません: {directory}")
            continue
        
        # ディレクトリ名から制定年を抽出
        seiteinen = extract_year_from_directory(directory)
        if not seiteinen:
            print(f"⚠️  ディレクトリ名から制定年を抽出できません: {directory}")
            continue
        
        print(f"\n📁 処理中: {directory} (制定年: {seiteinen})")
        
        # ディレクトリ内のすべてのテキストファイルを取得
        txt_files = glob.glob(os.path.join(directory, '*.txt'))
        print(f"   {len(txt_files)} 個のテキストファイルが見つかりました")
        
        for txt_file in txt_files:
            try:
                # ファイルを読み込み
                with open(txt_file, 'r', encoding='utf-8') as f:
                    text = f.read()
                
                # テキストを整形
                formatted_text = format_text(text)
                
                # ファイル名からメタデータを抽出
                filename = os.path.basename(txt_file)
                jichitai, kubun = extract_metadata_from_filename(filename)
                
                # 重複チェック用のキーを作成
                key = f"{jichitai}_{seiteinen}_{kubun}"
                
                # 重複チェック
                if key in processed_files:
                    print(f"   ⚠️  重複スキップ: {filename} ({jichitai}, {seiteinen}, {kubun})")
                    duplicate_count += 1
                    continue  # 重複の場合はスキップ
                
                # 処理済みセットに追加
                processed_files.add(key)
                
                # データを追加
                row_data = {
                    '本文': formatted_text,
                    '制定年': seiteinen,
                    '自治体': jichitai,
                    '区分': kubun
                }
                all_data.append(row_data)
                
                print(f"   ✓ 処理完了: {filename} ({jichitai}, {seiteinen}, {kubun})")
                success_count += 1
            
            except Exception as e:
                print(f"   ✗ エラー: {filename} - {str(e)}")
                error_count += 1
    
    # データフレームを作成
    if all_data:
        new_df = pd.DataFrame(all_data)
        
        # 既存のデータと結合
        if existing_df is not None:
            final_df = pd.concat([existing_df, new_df], ignore_index=True)
        else:
            final_df = new_df
        
        # CSVに保存
        final_df.to_csv(output_csv, index=False, encoding='utf-8')
        print(f"\n{'='*60}")
        print(f"📊 処理完了")
        print(f"{'='*60}")
        print(f"✓ 成功: {success_count} 件")
        print(f"✗ エラー: {error_count} 件")
        print(f"⚠️  重複: {duplicate_count} 件")
        print(f"📄 出力ファイル: {output_csv}")
        print(f"📈 CSVの総行数: {len(final_df)} 行")
        print(f"{'='*60}")
    else:
        print("\n⚠️  処理するファイルが見つかりませんでした")
    
    return success_count, error_count, duplicate_count

def main(year_input=None, output_csv=None):
    """メイン処理"""
    print("="*60)
    print("複数テキストファイル整形ツール")
    print("="*60)
    
    # デフォルトの設定
    if output_csv is None:
        output_csv = 'main2.6.csv'
    
    # 年の範囲または単年から処理対象を決定
    if year_input:
        years = parse_year_range(year_input)
        print(f"指定された年: {', '.join(years)}")
    else:
        # デフォルトでは利用可能な全ての年を使用
        available_years = get_available_years()
        if available_years:
            years = available_years
            print(f"年が指定されていません。利用可能な全ての年を処理します: {', '.join(years)}")
        else:
            print("エラー: 処理対象のディレクトリが見つかりません。")
            print("対象ディレクトリ形式: out_YYYY, out_txt_YYYY")
            sys.exit(1)
    
    # 処理対象ディレクトリを取得
    target_dirs = get_target_directories(years)
    
    if not target_dirs:
        print("⚠️  エラー: 処理対象のディレクトリが見つかりません")
        print("   'out_YYYY' または 'out_txt_YYYY' 形式のディレクトリを確認してください")
        sys.exit(1)
    
    # ディレクトリを表示
    print(f"\n検出されたディレクトリ:")
    for directory in sorted(target_dirs):
        year = extract_year_from_directory(directory)
        txt_count = len(glob.glob(os.path.join(directory, '*.txt')))
        print(f"  - {directory} (制定年: {year}, ファイル数: {txt_count})")
    
    # 確認
    print(f"\n出力先: {output_csv}")
    print(f"処理対象年: {', '.join(years)}")
    print(f"処理ディレクトリ数: {len(target_dirs)}")
    
    # 処理を実行
    print("\n処理を開始します...\n")
    success_count, error_count, duplicate_count = process_multiple_files(target_dirs, output_csv)
    
    # 終了
    if error_count > 0:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="複数テキストファイル整形ツール - out_xxxx と out_txt_xxxx ディレクトリを処理",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python text_forming.py                       # デフォルト（全ての利用可能な年）
  python text_forming.py --year 2014           # out_2014 と out_txt_2014 を処理
  python text_forming.py -y 2015               # out_2015 と out_txt_2015 を処理
  python text_forming.py --year 2014-2018      # 2014年から2018年まで順次処理
  python text_forming.py -y 2016-2017          # 2016年と2017年を処理
  python text_forming.py --list-years          # 利用可能な年のリストを表示
  python text_forming.py --output custom.csv   # 出力ファイル名を指定
        """
    )
    parser.add_argument("--year", "-y", type=str, help="処理対象の年（例: 2014, 2015, 2014-2018）")
    parser.add_argument("--output", "-o", type=str, default="main2.6.csv", help="出力CSVファイル名（デフォルト: main2.6.csv）")
    parser.add_argument("--list-years", "-l", action="store_true", help="利用可能な年のリストを表示")
    
    args = parser.parse_args()
    
    if args.list_years:
        available_years = get_available_years()
        if available_years:
            print("利用可能な年:")
            for year in available_years:
                out_dir = f"out_{year}"
                out_txt_dir = f"out_txt_{year}"
                
                out_exists = "✓" if os.path.exists(out_dir) else "✗"
                out_txt_exists = "✓" if os.path.exists(out_txt_dir) else "✗"
                
                print(f"  {year}: out_{year} {out_exists}  out_txt_{year} {out_txt_exists}")
        else:
            print("年別ディレクトリが見つかりません。")
            print("対象ディレクトリ形式: out_YYYY, out_txt_YYYY")
        sys.exit(0)
    
    try:
        main(year_input=args.year, output_csv=args.output)
    except KeyboardInterrupt:
        print("\n\n処理が中断されました")
        sys.exit(1)
    except Exception as e:
        print(f"\n予期しないエラーが発生しました: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)