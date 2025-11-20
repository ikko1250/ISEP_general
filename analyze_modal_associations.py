import sqlite3
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import os

# Configuration
DB_PATH = 'clause-viewer/clause_data3.db'
OUTPUT_CSV = 'analysis_result.csv'
OUTPUT_IMG = 'modal_associations_by_regulation.png'
FONT_PATH = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf' # Fallback font if needed, though matplotlib usually handles it.
# If Japanese characters are needed in the plot, we might need a specific font.
# I'll stick to English labels for the plot to avoid font issues unless the user strictly required Japanese in the plot (they asked for Japanese conversation, but plot labels are often better in English or might break).
# However, the user asked "会話の際には日本語で出力してくれると助かる" (It helps if you output in Japanese during conversation).
# I will try to use Japanese labels in the CSV but keep the plot keys in English or simple terms to ensure it renders correctly in a headless env without specific JP fonts.
# Wait, I can verify if a Japanese font is available. If not, I will use English labels for the graph.

TARGET_CLAUSES = [
    '*CLAUSE_POSITIVE_PERMISSION_CONSENT',
    '*CLAUSE_ZONE_Lv1',
    '*CLAUSE_ZONE_Lv2',
    '*CLAUSE_ENVIRONMENT'
]

TARGET_MODALS = [
    '*MODAL_MUST',
    '*MODAL_SHOULD'
]

def get_data():
    conn = sqlite3.connect(DB_PATH)

    # Load data
    df_codings = pd.read_sql_query("SELECT * FROM paragraph_codings", conn)
    df_coding_types = pd.read_sql_query("SELECT * FROM coding_types", conn)
    df_paragraphs = pd.read_sql_query("SELECT * FROM paragraphs", conn)
    df_municipalities = pd.read_sql_query("SELECT * FROM municipalities", conn)

    conn.close()

    # Merge data
    # coding_types -> paragraph_codings
    df = df_codings.merge(df_coding_types[['id', 'code']], left_on='coding_type_id', right_on='id', suffixes=('', '_type'))

    # paragraphs -> (result of above)
    df = df.merge(df_paragraphs[['id', 'municipality_id']], left_on='paragraph_id', right_on='id', suffixes=('', '_para'))

    # municipalities -> (result of above)
    df = df.merge(df_municipalities[['id', 'regulation_type']], left_on='municipality_id', right_on='id', suffixes=('', '_muni'))

    return df

def calculate_associations(df):
    # Filter out NULL regulation_type
    df_clean = df.dropna(subset=['regulation_type'])

    results = []

    # Unique regulation types + 'Overall'
    reg_types = ['Overall'] + sorted(df_clean['regulation_type'].unique().tolist())

    for reg_type in reg_types:
        if reg_type == 'Overall':
            current_df = df_clean
        else:
            current_df = df_clean[df_clean['regulation_type'] == reg_type]

        # Group by paragraph to get set of codes per paragraph
        # We need to know which paragraphs have the clause, and check if they have the modal.

        # Create a pivot or simple group by to list codes per paragraph
        # Optimizing: filter only relevant codes first to speed up
        relevant_codes = TARGET_CLAUSES + TARGET_MODALS
        subset = current_df[current_df['code'].isin(relevant_codes)]

        # paragraph_id -> set of codes
        para_codes = subset.groupby('paragraph_id')['code'].apply(set).to_dict()

        for clause in TARGET_CLAUSES:
            # Count paragraphs with this clause
            # We iterate through the dictionary to count.
            # (Could be done with vectorization but dict iteration is fine for this scale)
            clause_count = 0
            must_count = 0
            should_count = 0

            for pid, codes in para_codes.items():
                if clause in codes:
                    clause_count += 1
                    if '*MODAL_MUST' in codes:
                        must_count += 1
                    if '*MODAL_SHOULD' in codes:
                        should_count += 1

            if clause_count > 0:
                must_rate = must_count / clause_count
                should_rate = should_count / clause_count
            else:
                must_rate = 0.0
                should_rate = 0.0

            results.append({
                'Regulation_Type': reg_type,
                'Clause': clause,
                'Total_Clause_Occurrences': clause_count,
                'Cooccurrence_MUST': must_count,
                'Rate_MUST': must_rate,
                'Cooccurrence_SHOULD': should_count,
                'Rate_SHOULD': should_rate
            })

    return pd.DataFrame(results)

def plot_results(df_results):
    # Melt for plotting
    df_melt = df_results.melt(
        id_vars=['Regulation_Type', 'Clause'],
        value_vars=['Rate_MUST', 'Rate_SHOULD'],
        var_name='Modal_Type',
        value_name='Cooccurrence_Rate'
    )

    # Clean up Modal_Type names for legend
    df_melt['Modal_Type'] = df_melt['Modal_Type'].replace({
        'Rate_MUST': 'MUST',
        'Rate_SHOULD': 'SHOULD'
    })

    # Filter out 'Overall' for the grouped plot, or maybe include it?
    # The user asked to examine the difference by regulation type.
    # Let's plot the Regulation Types (excluding Overall for the main comparison plot to avoid clutter, or separate them).
    # Let's stick to Regulation Types only for the main visualization as requested.

    plot_data = df_melt[df_melt['Regulation_Type'] != 'Overall']

    # Set up the plot
    sns.set_theme(style="whitegrid")

    # Use a categorical plot (FactorPlot/CatPlot)
    # X axis: Clause
    # Y axis: Rate
    # Hue: Modal
    # Col: Regulation Type

    g = sns.catplot(
        data=plot_data,
        x='Clause',
        y='Cooccurrence_Rate',
        hue='Modal_Type',
        col='Regulation_Type',
        kind='bar',
        height=5,
        aspect=1.2,
        palette="muted"
    )

    g.set_axis_labels("Clause Coding", "Co-occurrence Rate")
    g.set_titles("{col_name}")

    # Rotate x-axis labels
    for ax in g.axes.flat:
        for label in ax.get_xticklabels():
            label.set_rotation(45)
            label.set_ha('right')

    plt.tight_layout()
    plt.savefig(OUTPUT_IMG)
    print(f"Plot saved to {OUTPUT_IMG}")

def main():
    print("Loading data...")
    df_raw = get_data()

    print("Calculating associations...")
    df_results = calculate_associations(df_raw)

    print("Saving CSV...")
    df_results.to_csv(OUTPUT_CSV, index=False)
    print(df_results)

    print("Plotting...")
    # We need to check if we have Japanese fonts if we want to use Japanese labels.
    # For now, the codes are in English (e.g. *CLAUSE_ZONE_Lv1), so the plot will be readable.
    # The Regulation Types are in Japanese (e.g. '届出制優位').
    # Matplotlib might struggle with Japanese characters without setup.
    # I will check if I can map them to English for the plot or install a font.
    # Mapping is safer.

    reg_map = {
        '届出制優位': 'Notification Dominant',
        '許可制優位': 'Permission Dominant',
        'Overall': 'Overall'
    }

    df_results_plot = df_results.copy()
    df_results_plot['Regulation_Type'] = df_results_plot['Regulation_Type'].map(lambda x: reg_map.get(x, x))

    plot_results(df_results_plot)

    print("Done.")

if __name__ == "__main__":
    main()
