import os
from pathlib import Path

# 入力ディレクトリと出力ディレクトリを設定
pdf_dir = Path("out_pdf_2020")
txt_dir = Path("out_txt_2020")

# 出力ディレクトリが存在しない場合は作成
txt_dir.mkdir(exist_ok=True)

# out_pdfディレクトリ内のすべてのPDFファイルを取得
pdf_files = list(pdf_dir.glob("*.pdf"))

# 各PDFファイルに対応する空のテキストファイルを作成
for pdf_file in pdf_files:
    # PDFファイル名から拡張子を除いた名前を取得
    txt_filename = pdf_file.stem + ".txt"
    txt_filepath = txt_dir / txt_filename
    
    # 空のテキストファイルを作成
    txt_filepath.touch()
    print(f"作成: {txt_filepath}")

print(f"\n合計 {len(pdf_files)} 個のテキストファイルを作成しました。")