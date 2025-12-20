import pandas as pd
import re
import os
import glob
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import platform

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def analyze_solar_zones(file_path):
    """
    太陽光発電規制条例の抑制区域条文を分析する関数
    (Ver.3.4: 円グラフによる可視化機能付き)
    """
    print(f"[{file_path}] の分析を開始します (Ver.3.4)...")

    # --- ファイル存在確認と診断 ---
    if not os.path.exists(file_path):
        print(f"\n[エラー] 指定されたファイルが見つかりません: {file_path}")
        print(f"現在のディレクトリ: {os.getcwd()}")
        # CSVファイルの候補を探す
        files = os.listdir()
        csv_files = [f for f in files if f.endswith('.csv')]
        if csv_files:
            print("もしかして: " + ", ".join([f"'{f}'" for f in csv_files]))
        return

    # データの読み込み
    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        print(f"ファイルの読み込みに失敗しました: {e}")
        return

    target_col = 'text'
    if target_col not in df.columns:
        print(f"エラー: '{target_col}' カラムが見つかりません。")
        return

    # --- 1. 条文の分解 ---
    def split_clause(text):
        if pd.isna(text):
            return []
        text = str(text).replace('\n', '')
        # 分割パターン
        split_pattern = r'(?:[\(（]\d+[\)）]|[①-⑳]|\d+\.|[\(（][ア-ン][\)）]|[ア-ン]\.)'
        parts = re.split(split_pattern, text)
        cleaned_parts = []
        for part in parts:
            part = part.strip().strip('。、, 　')
            if len(part) > 3: 
                cleaned_parts.append(part)
        return cleaned_parts

    all_segments = []
    for _, row in df.iterrows():
        segments = split_clause(row[target_col])
        municipality = row.get('municipality_name', '不明')
        row_id = row.get('id', '')
        for seg in segments:
            all_segments.append({
                'id': row_id,
                'municipality': municipality,
                'original_text': seg
            })

    segment_df = pd.DataFrame(all_segments)
    if len(segment_df) == 0:
        print("抽出データなし")
        return

    # --- 2. 分類ロジック (Ver.3.4 拡充版) ---

    def classify_segment(text):
        # 1. 除外対象: リード文・条文番号 (「禁止区域」特有のリード文を追加)
        lead_keywords = [
            r'^第\d+条', r'^\d+\s+市長は', r'次に掲げる', 
            r'抑制区域とする', # 抑制区域のリード文も引き続き除外
            r'禁止区域とする', r'指定する区域', # 禁止区域のリード文を追加
            r'事業を実施してはならない', # 直接的な禁止表現
            r'含めてはならない', # 禁止区域を事業区域に含めてはならない
            r'同意を得なければ', r'別表第', r'定義する',
            r'次のとおりとする', # リード文追加
            r'いずれかの区域とする', # リード文追加
            r'次の各号', # リード文追加
            r'事業区域としてはならない', # 禁止規定リード文
        ]

        for pat in lead_keywords:
            if re.search(pat, text):
                if not re.search(r'法第\d+条|法律第\d+号', text):
                    return False, "除外: リード文・条文番号"
        
        # 1.5. 除外対象: 手続き関連条文（区域指定ではない）
        procedure_keywords = [
            r'許可を受けなければ|許可の申請|申請があったとき',  # 許可申請
            r'届け出なければ|届出の受理|届け出ることはできない',  # 届出
            r'同意しないものとする|同意しないこと',  # 同意制限
            r'協議しなければならない|協議を行',  # 協議
            r'勧告することができる|命ずることができる',  # 勧告・命令
            r'違反し|罰則|公表する',  # 違反・罰則
            r'施行日|附則|経過措置',  # 経過措置
            r'キロワット未満|キロワット以上|平方メートル',  # 適用範囲（数値条件）
            r'建築物の屋根又は屋上',  # 適用除外
            r'抑制区域とみなす',  # 区域みなし
            r'面積の縮小|面積の.*拡大',  # 軽微変更（事業区域関連）
            r'工事施工者の変更|設計者.*変更',  # 変更届出
            r'事業着手.*変更|完了.*変更',  # 変更届出
            r'規則で定めるところにより',  # 規則委任
            r'総合計画.*適合|都市計画.*適合',  # 適合条件
            r'措置が講じられている',  # 許可基準
            r'関係町内会等の同意',  # 同意規定
            r'説明会|協議を適切に',  # 手続き要件
            r'虚偽の.*届出|虚偽の.*協議',  # 罰則関連
            r'聴取を要さない',  # 協議会意見聴取免除
            r'該当しないもの',  # 適用除外条件
        ]
        
        for pat in procedure_keywords:
            if re.search(pat, text):
                return False, "除外: 手続き・適用範囲条文"
        
        # 1.6. 除外対象: 別図・別表参照のみ
        reference_keywords = [
            r'前\d+号に掲げる区域.*別図',  # 別図参照
            r'^別表.*に掲げる区域$',  # 別表参照のみ
            r'^規則で定める区域$',  # 規則委任のみ
            r'一体的な区域として別図',  # 別図参照
        ]
        
        for pat in reference_keywords:
            if re.search(pat, text):
                return False, "除外: 別図・別表参照"
        
        # 1.7. 除外対象: 定義条文 (〜をいう)
        definition_keywords = [
            r'をいう$|をいう。$',  # 定義条文の末尾
            r'^再生可能エネルギー\s',  # 定義条文の冒頭
            r'^事業者\s|^事業区域\s|^地域\s',  # 定義条文
            r'^住民等\s|^行政区',  # 定義条文
        ]
        
        for pat in definition_keywords:
            if re.search(pat, text):
                return False, "除外: 定義条文"
        
        # 1.8. 除外対象: 罰則・勧告対象行為、許可基準の項目
        sanction_keywords = [
            r'着手したとき|従わなかったとき',  # 罰則対象行為
            r'講じなかったとき|怠り',  # 義務違反
            r'拒み|妨げ|忌避|答弁',  # 立入検査拒否
            r'被害を与えたとき|被害を与えるおそれ',  # 被害発生
            r'禁止区域を含まないこと',  # 許可基準項目
            r'を設置したとき$',  # 罰則条件
            r'営牧場.*区域',  # 自治体固有の施設
            r'事前確認を行わなければ',  # 手続き条件
            r'努めなければならない$',  # 努力義務
        ]
        
        for pat in sanction_keywords:
            if re.search(pat, text):
                return False, "除外: 罰則・許可基準"
        
        # 1.8.5. 除外対象: 許可基準適合条件
        approval_criteria_keywords = [
            r'基準に適合していること',  # 許可基準
            r'写し$|写し。$',  # 必要書類（公図の写し等）
            r'^現況|^土地利用|^雨水|^排水|^求積',  # 必要書類名
        ]
        
        for pat in approval_criteria_keywords:
            if re.search(pat, text):
                return False, "除外: 許可基準・書類"
        
        # 1.9. 除外対象: 抑制区域の定義（禁止区域を除く残り）
        suppression_zone_keywords = [
            r'禁止区域を除く区域',  # 抑制区域の定義
            r'禁止区域・抑制区域の確認',  # 確認書類
            r'^事業禁止区域$|^禁止区域$',  # 見出しのみ
        ]
        
        for pat in suppression_zone_keywords:
            if re.search(pat, text):
                return False, "除外: 抑制区域定義・確認"

        # 2. 法令に基づく指定

        legal_patterns = [
            (r'農地法|農業振興|農用地区域|農振法', "法令: 農地・農業振興"),
            (r'森林法|保安林|地域森林計画', "法令: 森林・保安林"),
            (r'砂防法|砂防指定地', "法令: 砂防指定地"),
            (r'地すべり等防止法|地すべり防止区域', "法令: 地すべり防止区域"), 
            (r'急傾斜地法|急傾斜地崩壊危険区域', "法令: 急傾斜地崩壊危険区域"), 
            (r'自然公園法|国立公園|国定公園|県立自然公園', "法令: 自然公園"),
            (r'自然環境保全法|自然環境保全地域', "法令: 自然環境保全法"),
            (r'鳥獣保護|鳥獣捕獲', "法令: 鳥獣保護区"),
            (r'文化財保護|指定.*文化財|登録.*文化財|埋蔵文化財|史跡名勝天然記念物', "法令: 文化財・史跡"),
            (r'都市計画法|風致地区|市街化調整区域', "法令: 都市計画(風致・調整区域等)"),
            (r'都市緑地法|緑地保全地域|特別緑地保全地区', "法令: 都市緑地法・緑地保全"),
            (r'生産緑地法|生産緑地地区', "法令: 生産緑地法"),
            (r'景観法|景観計画|景観地区', "法令: 景観法・景観計画"),
            (r'河川法|河川区域|河川保全区域', "法令: 河川法"),
            (r'水防法|浸水想定区域', "法令: 水防法・浸水想定"),
            (r'宅地造成', "法令: 宅地造成規制区域"),
            (r'津波防災地域づくり|津波災害警戒区域', "法令: 津波防災・津波災害"),
            (r'特定都市河川浸水被害対策法', "法令: 特定都市河川浸水被害対策法"),
            (r'土砂災害防止法|土砂災害警戒区域|土砂災害特別警戒区域', "法令: 土砂災害防止法"),
            (r'水資源保全|水環境保全', "法令: 水資源・水環境保全"),  # 追加
            
            # キャッチオール的な法令判定
            (r'法第\d+条|法律第\d+号|県条例|市条例|町条例|村条例', "法令: その他/特定法令")
        ]
        for pattern, category in legal_patterns:
            if re.search(pattern, text):
                return True, category

        # 3. 定性的な記述
        qualitative_patterns = [
            (r'土砂災害|崩壊|地盤|崖崩れ|防災|災害|地すべり|急傾斜|斜度\d+度|勾配', "定性: 災害リスク・防災"), 
            (r'景観|眺望|風致', "定性: 景観・風致"),
            (r'自然|生態系|里山|緑地|植生|生息|湿原|鳥獣', "定性: 自然環境・生態系"),
            (r'歴史|文化|郷土|伝統|遺産|史跡|名勝|天然記念物', "定性: 歴史・文化"), 
            (r'住環境|生活|静穏|住宅', "定性: 住環境・生活環境"),
            (r'シンボル|象徴|ランドマーク', "定性: 地域のシンボル"),
            (r'道路|河川|国道|県道', "定性: 道路・河川隣接"),
            (r'学校|病院|公共施設|福祉', "定性: 公共・福祉施設周辺"),
            (r'農地|山林|農林', "定性: 農地・山林(法令言及なし)"),
            (r'公園|広場', "定性: 公園・広場")
        ]
        for pattern, category in qualitative_patterns:
            if re.search(pattern, text):
                return False, category

        # 4. 除外対象: 包括条項
        catch_all_keywords = [
            r'前各号', r'前号', r'その他.*市長', r'その他.*規則', 
            r'必要と認め', r'準ずる', r'配慮が必要', r'著しい影響',
            r'その他.*区域'
        ]
        for pat in catch_all_keywords:
            if re.search(pat, text):
                return False, "除外: 包括条項・その他"

        return False, "その他/不明"

    segment_df[['is_legal_based', 'category']] = segment_df['original_text'].apply(
        lambda x: pd.Series(classify_segment(x))
    )

    # --- 3. 統計情報の集計 ---
    valid_df = segment_df[~segment_df['category'].str.startswith('除外')]
    category_counts = valid_df['category'].value_counts()
    
    print("--- 【分析結果】有効な区域指定カテゴリ別出現数 ---")
    print(category_counts.to_string())
    print("-" * 30 + "\n")

    # --- 4. 可視化 (帯グラフ/横棒グラフ) ---
    print("--- グラフ描画中 ---")
    
    # 日本語フォントの設定 (環境依存を吸収する試み)
    system_name = platform.system()
    font_path = None
    
    # 一般的な日本語フォントの候補
    jp_fonts = [
        'Meiryo', 'Yu Gothic', 'Hiragino Sans', 'Hiragino Kaku Gothic ProN',
        'MS Gothic', 'TakaoGothic', 'IPAGothic', 'Noto Sans CJK JP', 'Noto Sans JP'
    ]
    
    # Matplotlibのフォントマネージャから利用可能なフォントを探す
    available_fonts = set([f.name for f in fm.fontManager.ttflist])
    found_font = None
    for font in jp_fonts:
        if font in available_fonts:
            found_font = font
            break
            
    if found_font:
        plt.rcParams['font.family'] = found_font
        print(f"フォント設定: {found_font}")
    else:
        print("※日本語フォントが自動検出できませんでした。グラフの文字が豆腐(□)になる可能性があります。")
        plt.rcParams['font.family'] = 'sans-serif'

    # データ準備
    total = category_counts.sum()
    threshold = 0.012  # 1.2%
    
    # 1.2%以上のカテゴリと未満のカテゴリを分離
    major_categories = category_counts[category_counts / total >= threshold].copy()
    minor_categories = category_counts[category_counts / total < threshold]
    
    # 少数カテゴリを「その他（少数カテゴリ）」として統合
    if len(minor_categories) > 0:
        minor_total = minor_categories.sum()
        minor_label = f"その他（少数 {len(minor_categories)}種）"
        major_categories[minor_label] = minor_total
        print(f"※ 1.2%未満の少数カテゴリ {len(minor_categories)}種を統合しました（計{minor_total}件）")
        print(f"  統合されたカテゴリ: {', '.join(minor_categories.index.tolist())}")
    
    # ソートし直す（件数降順 → 帯グラフでは下から上に表示されるので昇順に）
    category_counts_merged = major_categories.sort_values(ascending=True)
    
    labels = category_counts_merged.index
    sizes = category_counts_merged.values
    percentages = sizes / total * 100

    # グラフのサイズ設定
    n_categories = len(labels)
    fig_height = max(8, n_categories * 0.6)  # カテゴリ数に応じて高さ調整
    fig, ax = plt.subplots(figsize=(14, fig_height))

    # 色の準備（タブ20色を使用）
    colors = [plt.cm.tab20(i % 20) for i in range(len(labels))]

    # 横棒グラフ描画
    bars = ax.barh(labels, sizes, color=colors, edgecolor='white', linewidth=0.5)

    # 各バーに件数と%を表示（バーの外側に黒字で統一）
    for bar, count, pct in zip(bars, sizes, percentages):
        width = bar.get_width()
        ax.text(width + 5, bar.get_y() + bar.get_height()/2, 
                f'{count}件 ({pct:.1f}%)', 
                ha='left', va='center', fontsize=11, color='black')

    # 軸とタイトルの設定
    ax.set_xlabel('件数', fontsize=14)
    ax.set_title(f'太陽光発電規制条例 抑制区域の指定事由内訳\n（総数: {total}件）', fontsize=18, fontweight='bold')
    ax.set_xlim(0, max(sizes) * 1.15)  # 右端に余白
    
    # Y軸ラベルのフォントサイズ調整
    ax.tick_params(axis='y', labelsize=12)
    ax.tick_params(axis='x', labelsize=11)
    
    # グリッド線（薄く）
    ax.xaxis.grid(True, linestyle='--', alpha=0.3)
    ax.set_axisbelow(True)
    
    # 枠線を薄く
    for spine in ax.spines.values():
        spine.set_alpha(0.3)

    plt.tight_layout()

    # 画像保存
    graph_filename = os.path.join(BASE_DIR, "Lv2_zone_bar_chart.png")
    plt.savefig(graph_filename, dpi=150, bbox_inches='tight')
    print(f"\n[完了] 帯グラフを保存しました: {graph_filename}")
    
    # CSV出力
    output_filename = os.path.join(BASE_DIR, "Lv2_zone_classification_results.csv")
    try:
        segment_df.to_csv(output_filename, index=False, encoding='utf-8-sig')
        print(f"[完了] データCSVを保存しました: {output_filename}")
    except Exception as e:
        print(f"[エラー] CSV保存失敗: {e}")

    return segment_df

if __name__ == "__main__":
    # フィルタリング済みCSVを使用（filter_zone_clauses.pyで事前生成）
    file_path = '/home/ubuntu/cur/isep/clause-viewer/csv_by_coding/CLAUSE_ZONE_Lv2_filtered.csv'
    analyze_solar_zones(file_path)