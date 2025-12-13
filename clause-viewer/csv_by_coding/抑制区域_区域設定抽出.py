import pandas as pd
import re

# データの読み込み
df = pd.read_csv('/home/ubuntu/cur/isep/clause-viewer/csv_by_coding/CLAUSE_ZONE_Lv1.csv')

# 分類関数の定義 (前回と同じロジック)
def classify_clause_refined(row):
    text = row['text']
    clean_text = text.replace('\n', '').replace(' ', '')
    
    # 1. Table Designation
    if '別表' in text and ('区域' in text or '土地' in text or '場所' in text):
        return '抑制区域の指定(表を使用)'
    
    # 2. Direct Designation
    # Pattern A: "Following areas"
    if ('次に掲げる区域' in text or '次の各号のいずれかに該当する区域' in text or '次の各号に掲げる区域' in text):
        return '抑制区域の指定(直接指定)'
    
    # Pattern B: List of laws
    law_keywords = ['砂防法', '地すべり', '急傾斜地', '農地法', '森林法', '自然公園法', '鳥獣保護', '文化財保護']
    has_law = any(k in text for k in law_keywords)
    has_enum = bool(re.search(r'\(1\)|\(2\)|①|②|第1号|第１号', text))
    
    # Must contain "Area" and NOT be about application forms or notifications
    if has_law and has_enum and '区域' in text and '別表' not in text and '事項' not in text and '申請書' not in text and '届出' not in text:
        return '抑制区域の指定(直接指定)'

    # 3. Others (Simplified for this task as we filter them out anyway)
    return 'その他'

# 分類を実行
df['classification'] = df.apply(classify_clause_refined, axis=1)

# 分類1: 直接指定のみ抽出
df_direct = df[df['classification'] == '抑制区域の指定(直接指定)'].copy()
df_direct = df_direct.sort_values('id')

# 分類2: 表を使用のみ抽出
df_table = df[df['classification'] == '抑制区域の指定(表を使用)'].copy()
df_table = df_table.sort_values('id')

# CSVファイルに出力
output_direct = 'CLAUSE_ZONE_Lv1_direct_designation.csv'
output_table = 'CLAUSE_ZONE_Lv1_table_designation.csv'

df_direct.to_csv(output_direct, index=False, encoding='utf-8-sig')
df_table.to_csv(output_table, index=False, encoding='utf-8-sig')

# 結果の確認
print(f"分類1: 直接指定 - {len(df_direct)} rows")
print(f"  File saved to: {output_direct}")
print(f"\n分類2: 表を使用 - {len(df_table)} rows")
print(f"  File saved to: {output_table}")
print(f"\n合計: {len(df_direct) + len(df_table)} rows")