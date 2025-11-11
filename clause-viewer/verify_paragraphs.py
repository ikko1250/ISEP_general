import json

file_path = '/home/ubuntu/cur/isep/clause-viewer/data-integrated.json'

try:
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"'{file_path}'の読み込みに成功しました。")
    print("「大空町」の最初の3つの段落を検索します...")
    print("-" * 20)

    count = 0
    found = False
    for p in data.get('paragraphs', []):
        if p.get('municipality') == '大空町':
            found = True
            print(json.dumps(p, ensure_ascii=False, indent=2))
            print("-" * 20)
            count += 1
            if count >= 3:
                break
    
    if not found:
        print("「大空町」の段落データが見つかりませんでした。")

except FileNotFoundError:
    print(f"エラー: ファイルが見つかりません: {file_path}")
except json.JSONDecodeError:
    print(f"エラー: ファイルのJSONデコードに失敗しました: {file_path}")
except Exception as e:
    print(f"予期せぬエラーが発生しました: {e}")
