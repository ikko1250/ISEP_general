#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import glob
import argparse
from pathlib import Path

def get_available_years():
    """利用可能な年別PDFディレクトリのリストを取得"""
    pattern = "out_pdf_*"
    dirs = glob.glob(pattern)
    years = []
    for d in dirs:
        if os.path.isdir(d):
            match = Path(d).name.replace("out_pdf_", "")
            if match.isdigit() and len(match) == 4:
                years.append(match)
    return sorted(years)

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

def process_single_year(year):
    """単一年のPDFディレクトリを処理してテキストファイルを作成"""
    # 入力ディレクトリと出力ディレクトリを設定
    pdf_dir = Path(f"out_pdf_{year}")
    txt_dir = Path(f"out_txt_{year}")

    if not pdf_dir.exists():
        print(f"エラー: ディレクトリが見つかりません: {pdf_dir}")
        return 0
    
    print(f"\n{'='*50}")
    print(f"Processing year: {year}")
    print(f"Input directory: {pdf_dir}")
    print(f"Output directory: {txt_dir}")
    print(f"{'='*50}")

    # 出力ディレクトリが存在しない場合は作成
    txt_dir.mkdir(exist_ok=True)

    # out_pdfディレクトリ内のすべてのPDFファイルを取得
    pdf_files = list(pdf_dir.glob("*.pdf"))
    
    if not pdf_files:
        print(f"警告: {pdf_dir} にPDFファイルが見つかりません。")
        return 0

    created_count = 0
    # 各PDFファイルに対応する空のテキストファイルを作成
    for pdf_file in pdf_files:
        # PDFファイル名から拡張子を除いた名前を取得
        txt_filename = pdf_file.stem + ".txt"
        txt_filepath = txt_dir / txt_filename
        
        # 既に存在する場合はスキップ
        if txt_filepath.exists():
            print(f"スキップ: {txt_filepath} (既に存在)")
            continue
        
        # 空のテキストファイルを作成
        txt_filepath.touch()
        print(f"作成: {txt_filepath}")
        created_count += 1

    print(f"\n年 {year} の処理完了: {created_count} 個のテキストファイルを新規作成 (総PDFファイル数: {len(pdf_files)})")
    return created_count

def main(year_input=None):
    """メイン処理関数"""
    print(f"Starting make_txt_file.py...")
    
    # 年の範囲または単年から処理対象を決定
    if year_input:
        years = parse_year_range(year_input)
    else:
        # デフォルトでは最新の年を使用
        available_years = get_available_years()
        if available_years:
            latest_year = available_years[-1]
            print(f"年が指定されていません。最新の年 {latest_year} を使用します。")
            years = [latest_year]
        else:
            print("エラー: PDFディレクトリが見つかりません。")
            print("利用可能なディレクトリ形式: out_pdf_YYYY")
            sys.exit(1)
    
    print(f"Processing {len(years)} year(s): {', '.join(years)}")
    
    total_created = 0
    missing_years = []
    
    for year in years:
        pdf_dir = Path(f"out_pdf_{year}")
        if not pdf_dir.exists():
            missing_years.append(year)
            continue
        
        created = process_single_year(year)
        total_created += created
    
    if missing_years:
        print(f"\n警告: 以下の年のディレクトリが見つかりませんでした: {', '.join(missing_years)}")
    
    # 最終的な統計情報を表示
    print(f"\n{'='*50}")
    print(f"全体の処理結果:")
    print(f"  処理年数: {len(years) - len(missing_years)}")
    print(f"  新規作成ファイル数: {total_created}")
    if missing_years:
        print(f"  見つからない年: {', '.join(missing_years)}")
    print(f"{'='*50}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="PDFファイル用の空テキストファイル作成ツール",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python make_txt_file.py                 # デフォルト（最新年）
  python make_txt_file.py --year 2014     # out_pdf_2014 を処理
  python make_txt_file.py -y 2015         # out_pdf_2015 を処理
  python make_txt_file.py --year 2014-2018  # 2014年から2018年まで順次処理
  python make_txt_file.py -y 2016-2017    # 2016年と2017年を処理
  python make_txt_file.py --list-years    # 利用可能な年のリストを表示
        """
    )
    parser.add_argument("--year", "-y", type=str, help="処理対象の年（例: 2014, 2015, 2014-2018）")
    parser.add_argument("--list-years", "-l", action="store_true", help="利用可能な年のリストを表示")
    
    args = parser.parse_args()
    
    if args.list_years:
        available_years = get_available_years()
        if available_years:
            print("利用可能な年:")
            for year in available_years:
                print(f"  {year} (out_pdf_{year}/)")
        else:
            print("年別PDFディレクトリが見つかりません。")
        sys.exit(0)
    
    main(year_input=args.year)