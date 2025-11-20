import sqlite3
import os
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import matplotlib.font_manager as fm

# Database path
db_path = os.path.join(os.path.dirname(__file__), 'clause-viewer/clause_data3.db')

def visualize_enactment_years():
    if not os.path.exists(db_path):
        print(f"Error: Database file not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    
    # Query to get municipality name, enactment year, area_type, and text snippet for filtering
    sql = """
    SELECT m.name, p.year, m.area_type, p.text
    FROM municipalities m
    JOIN paragraphs p ON m.id = p.municipality_id
    WHERE m.resident_consent = '有' AND p.dan_number = 1 AND p.category = '条例'
    """
    
    try:
        raw_df = pd.read_sql_query(sql, conn)
        conn.close()
        
        if raw_df.empty:
            print("No data found for resident_consent = '有'")
            return

        # Process data to find the correct enactment year
        processed_data = []
        
        # Group by municipality
        for name, group in raw_df.groupby('name'):
            # Filter for "Clean" text
            # Pattern: Starts with (目的), (趣旨), or 第1条
            # And does NOT start with ○ (which indicates a header like ○XX市条例...)
            
            def is_clean(text):
                text = text.strip()
                if text.startswith('○'): return False
                if text.startswith('(目的)'): return True
                if text.startswith('(趣旨)'): return True
                if text.startswith('第1条'): return True
                return False

            clean_rows = group[group['text'].apply(is_clean)]
            
            if not clean_rows.empty:
                # If clean rows exist, use the minimum year from them
                enactment_year = clean_rows['year'].min()
                area_type = clean_rows.iloc[0]['area_type'] # area_type should be same for municipality
            else:
                # Fallback: use minimum year from all rows
                enactment_year = group['year'].min()
                area_type = group.iloc[0]['area_type']
            
            processed_data.append({
                'name': name,
                'enactment_year': int(enactment_year),
                'area_type': area_type
            })
            
        df = pd.DataFrame(processed_data)

        print("Data preview:")
        print(df.head())
        print(f"Total municipalities: {len(df)}")

        # Set Japanese font
        # Try to find a Japanese font available on the system
        # Common fonts: IPAexGothic, VL Gothic, TakaoGothic
        font_path = None
        font_names = [f.name for f in fm.fontManager.ttflist]
        preferred_fonts = ['IPAexGothic', 'VL Gothic', 'TakaoGothic', 'Noto Sans CJK JP', 'Droid Sans Japanese']
        
        for font in preferred_fonts:
            if font in font_names:
                plt.rcParams['font.family'] = font
                print(f"Using font: {font}")
                break
        else:
            # Fallback: try to find font file directly if family name doesn't work or not found
            # This is a common issue in some environments
            font_files = fm.findSystemFonts()
            for f in font_files:
                if 'Gothic' in f or 'gothic' in f:
                    try:
                        prop = fm.FontProperties(fname=f)
                        plt.rcParams['font.family'] = prop.get_name()
                        print(f"Using font file: {f}")
                        break
                    except:
                        continue

        # Create the plot
        plt.figure(figsize=(12, 8))
        
        # Define the order for stacking (from bottom to top)
        # Note: seaborn histplot stacks in reverse order of hue_order (first item on top)
        hue_order = [
            '2層構造(抑制+禁止)',
            '禁止地区制',
            '抑制地区制',
            '区域設定あり(少数)',
            '区域設定なし'
        ]
        
        # Create a histogram with stacked bars for area_type
        # We can use seaborn's histplot with 'hue' and 'multiple="stack"'
        sns.histplot(
            data=df,
            x='enactment_year',
            hue='area_type',
            multiple='stack',
            binwidth=1,
            discrete=True,
            palette='viridis',
            hue_order=hue_order
        )
        
        plt.title('自治体の条例制定年分布 (住民同意要件あり)', fontsize=16)
        plt.xlabel('制定年', fontsize=14)
        plt.ylabel('自治体数', fontsize=14)
        plt.grid(axis='y', linestyle='--', alpha=0.7)
        
        # Adjust x-axis ticks to show all years if possible
        min_year = df['enactment_year'].min()
        max_year = df['enactment_year'].max()
        plt.xticks(range(min_year, max_year + 1), rotation=45)
        
        plt.tight_layout()
        
        output_file = 'enactment_year_histogram.png'
        plt.savefig(output_file)
        print(f"Histogram saved to {output_file}")
        
    except Exception as e:
        print(f"An error occurred: {e}")
        if conn:
            conn.close()

if __name__ == "__main__":
    visualize_enactment_years()
