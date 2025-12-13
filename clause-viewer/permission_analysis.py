"""
許可条文分類スクリプト
太陽光発電規制条例における「首長による許可」に関する条文を分類する

分類軸:
1. 許可の種類 (permission_type)
2. 許可の条件 (permission_condition)  
3. 許可に伴う手続き (permission_procedure)
"""

import pandas as pd
import re
import os

# 設定
INPUT_FILE = '/home/ubuntu/cur/isep/clause-viewer/csv_by_coding/CLAUSE_POSITIVE_PERMISSION_CONSENT.csv'
OUTPUT_DIR = '/home/ubuntu/cur/isep/clause-viewer/'
OUTPUT_FILE = os.path.join(OUTPUT_DIR, 'permission_classification_result.csv')


def main():
    # 1. データの読み込み
    try:
        df = pd.read_csv(INPUT_FILE)
        print(f"ファイル読み込み成功: {INPUT_FILE} (全{len(df)}行)")
    except FileNotFoundError:
        print(f"エラー: ファイル '{INPUT_FILE}' が見つかりません。")
        return

    # 2. 分類条件の設定

    # 2-1. 許可の種類
    permission_type_criteria = {
        '設置許可': [
            r'設置許可',
            r'許可の申請',
            r'許可を受けなければ',
            r'町長の許可',
            r'市長の許可',
            r'村長の許可',
            r'発電事業許可',
            r'許可申請',
            r'許可事業者',
            r'許可を.{0,10}受け',
        ],
        '変更許可': [
            r'変更許可',
            r'変更の許可',
            r'変更しようとするとき.{0,30}許可',
        ],
        '承継承認': [
            r'承継承認',
            r'地位を承継',
            r'承継.{0,20}承認',
        ],
        '許可取消': [
            r'許可を取り消す',
            r'取消し',
            r'許可の取消',
        ],
        '勧告': [
            r'勧告',
        ],
        '命令': [
            r'命ず',
            r'命じ',
            r'措置を命',
        ],
        '通知': [
            r'通知',
            r'通知書',
        ],
        '同意決定': [
            r'同意の可否',
            r'同意通知',
            r'不同意通知',
            r'同意をしない',
            r'同意しない',
            r'同意を得',
        ],
        '検査': [
            r'検査',
            r'完了検査',
            r'立入検査',
        ],
        '申請書': [
            r'申請書',
            r'申請の提出',
        ],
    }

    # 2-2. 許可の条件
    permission_condition_criteria = {
        '区域条件': [
            r'保全地区',
            r'抑制区域',
            r'指定区域',
            r'禁止区域',
            r'規制区域',
        ],
        '規模条件': [
            r'\d+.*平方メートル',
            r'\d+.*キロワット',
            r'一定の規模',
            r'事業区域の面積が',
            r'大規模事業',
        ],
        '基準適合': [
            r'基準に適合',
            r'規則で定める基準',
            r'要件を満た',
            r'いずれにも該当',
            r'許可内容に適合',
            r'いずれにも適合',
        ],
        '条件付与': [
            r'条件を付す',
            r'条件を付する',
            r'必要な条件',
            r'条件に違反',
            r'意見を付す',
            r'必要な限度',
        ],
        '違反対応': [
            r'違反',
            r'保全義務',
            r'遵守',
            r'不正',
        ],
        '軽微変更': [
            r'軽微な変更',
            r'規則で定める軽微',
        ],
        '撤去・原状回復': [
            r'撤去',
            r'原状回復',
            r'除却',
            r'復旧',
        ],
        '着手期限': [
            r'着手.{0,20}日',
            r'起算して',
            r'を経過',
            r'着手しなかった',
        ],
        '環境保全': [
            r'自然環境',
            r'景観',
            r'生活環境',
            r'災害',
            r'土砂',
            r'防止',
        ],
    }

    # 2-3. 許可に伴う手続き
    permission_procedure_criteria = {
        '同意': [
            r'同意を得',
            r'同意を求め',
            r'同意.{0,10}必要',
            r'市長の同意',
            r'町長の同意',
            r'村長の同意',
            r'同意の可否',
            r'同意通知',
            r'不同意通知',
        ],
        '協議': [
            r'協議',
            r'意見を聴',
            r'意見を求',
        ],
        '審議会': [
            r'審議会の議を経',
            r'審議会に諮問',
            r'審議会.{0,20}議',
        ],
        '届出': [
            r'届出',
            r'届け出',
        ],
        '通知手続': [
            r'通知する',
            r'通知書',
            r'公表',
        ],
        '事前期限': [
            r'\d+日前まで',
            r'あらかじめ',
            r'事前に',
        ],
        '計画提出': [
            r'事業計画',
            r'計画を定め',
            r'申請書.{0,20}提出',
        ],
    }

    print("分類条件を設定しました。")

    # 3. マッチング処理

    def identify_categories(text, criteria_dict):
        """テキストに対して分類条件をチェックし、マッチしたカテゴリを返す"""
        if not isinstance(text, str):
            return None
        
        hits = set()
        for category, patterns in criteria_dict.items():
            for pattern in patterns:
                if re.search(pattern, text):
                    hits.add(category)
                    break  # そのカテゴリ内で1つヒットすればOK
        
        if not hits:
            return 'その他'
        
        return ','.join(sorted(list(hits)))

    # 各分類軸で分類を実行
    df['permission_type'] = df['text'].apply(
        lambda x: identify_categories(x, permission_type_criteria)
    )
    df['permission_condition'] = df['text'].apply(
        lambda x: identify_categories(x, permission_condition_criteria)
    )
    df['permission_procedure'] = df['text'].apply(
        lambda x: identify_categories(x, permission_procedure_criteria)
    )

    # 4. 結果の出力
    print(f"\n--- 実行結果 ---")
    print(f"処理件数: {len(df)} 件")

    # CSVファイルへの書き出し
    df.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')
    print(f"ファイルを保存しました: {OUTPUT_FILE}")

    # 5. 分析結果の表示
    print(f"\n--- 許可の種類 (permission_type) ---")
    print(df['permission_type'].value_counts())

    print(f"\n--- 許可の条件 (permission_condition) ---")
    print(df['permission_condition'].value_counts())

    print(f"\n--- 許可に伴う手続き (permission_procedure) ---")
    print(df['permission_procedure'].value_counts())


if __name__ == "__main__":
    main()
