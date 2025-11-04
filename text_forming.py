import re
import pandas as pd
import os
import glob
import sys

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

def extract_year_from_directory(directory):
    """
    ディレクトリ名から制定年を抽出する
    例: "out_2022" -> "2022"
        "out_2023" -> "2023"
    
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
    
    # 既存のCSVを読み込み（存在する場合）
    existing_df = None
    if os.path.exists(output_csv):
        try:
            existing_df = pd.read_csv(output_csv)
            if len(existing_df) > 0:
                print(f"既存のCSVファイルを読み込みました: {len(existing_df)} 行")
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
                
                # 重複チェック（既存のCSVおよび今回追加するデータの両方）
                is_duplicate = False
                
                # 既存のCSVでチェック
                if existing_df is not None:
                    duplicate_rows = existing_df[(existing_df['自治体'] == jichitai) & 
                                                (existing_df['制定年'] == seiteinen) & 
                                                (existing_df['区分'] == kubun)]
                    is_duplicate = len(duplicate_rows) > 0
                
                # 今回追加しようとしているデータ内でもチェック
                if not is_duplicate and all_data:
                    for existing_row in all_data:
                        if (existing_row['自治体'] == jichitai and 
                            existing_row['制定年'] == seiteinen and 
                            existing_row['区分'] == kubun):
                            is_duplicate = True
                            break
                
                if is_duplicate:
                    print(f"   ⚠️  重複スキップ: {filename} ({jichitai}, {seiteinen}, {kubun})")
                    duplicate_count += 1
                    continue  # 重複の場合はスキップ
                
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

def main():
    """メイン処理"""
    print("="*60)
    print("複数テキストファイル整形ツール (CUI版)")
    print("="*60)
    
    # デフォルトの設定
    output_csv = 'main2.6.csv'
    
    # カレントディレクトリから年度別ディレクトリを自動検出
    # out_YYYY形式のディレクトリを検索
    all_dirs = [d for d in os.listdir('.') if os.path.isdir(d)]
    year_dirs = [d for d in all_dirs if re.match(r'out_\d{4}', d)]
    
    if not year_dirs:
        print("⚠️  エラー: 処理対象のディレクトリが見つかりません")
        print("   'out_YYYY' 形式のディレクトリを作成してください")
        sys.exit(1)
    
    # ディレクトリを表示
    print(f"\n検出されたディレクトリ:")
    for directory in sorted(year_dirs):
        year = extract_year_from_directory(directory)
        txt_count = len(glob.glob(os.path.join(directory, '*.txt')))
        print(f"  - {directory} (制定年: {year}, ファイル数: {txt_count})")
    
    # 確認
    print(f"\n出力先: {output_csv}")
    response = input("\n処理を開始しますか? [y/N]: ").strip().lower()
    
    if response not in ['y', 'yes']:
        print("処理をキャンセルしました")
        sys.exit(0)
    
    # 処理を実行
    print("\n処理を開始します...\n")
    success_count, error_count, duplicate_count = process_multiple_files(year_dirs, output_csv)
    
    # 終了
    if error_count > 0:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n処理が中断されました")
        sys.exit(1)
    except Exception as e:
        print(f"\n予期しないエラーが発生しました: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)