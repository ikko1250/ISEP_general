import json
import os

notebooks = [
    '/home/ubuntu/cur/isep/clause-viewer/zone_analysis_suite/抑制区域分析.ipynb',
    '/home/ubuntu/cur/isep/clause-viewer/zone_analysis_suite/禁止区域分析.ipynb'
]

old_path = "/home/ubuntu/cur/isep/clause-viewer/"
new_path = "./"

for nb_path in notebooks:
    if not os.path.exists(nb_path):
        print(f"Notebook not found: {nb_path}")
        continue
        
    try:
        with open(nb_path, 'r', encoding='utf-8') as f:
            nb = json.load(f)
        
        changed = False
        
        for cell in nb.get('cells', []):
            if cell.get('cell_type') == 'code':
                new_source = []
                for line in cell.get('source', []):
                    # Replace OUTPUT_DIR definition
                    if "OUTPUT_DIR =" in line and old_path in line:
                        line = line.replace(old_path, new_path)
                        changed = True
                    # Replace other specific full paths if they match the old directory
                    elif old_path in line:
                         # Be careful not to replace DB path or input csv paths if they are meant to be absolute external
                         # But here we moved the intermediate CSVs too.
                         # Let's be specific.
                         if "clause_data4.db" not in line and "csv_by_coding" not in line:
                              # If it points to one of the moved CSVs, update it to relative
                              # Heuristic: if it points to OUTPUT_DIR explicitly, it might be fine if we updated OUTPUT_DIR.
                              # But if it hardcodes the path, we need to fix it.
                              line = line.replace(old_path, new_path)
                              changed = True
                    new_source.append(line)
                cell['source'] = new_source
        
        if changed:
            with open(nb_path, 'w', encoding='utf-8') as f:
                json.dump(nb, f, indent=1, ensure_ascii=False)
            print(f"Updated {nb_path}")
        else:
            print(f"No changes made to {nb_path}")

    except Exception as e:
        print(f"Error processing {nb_path}: {e}")
