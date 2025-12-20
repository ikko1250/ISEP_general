import sqlite3
import csv
import os
import sys

# Configuration
DB_PATH = os.path.join(os.path.dirname(__file__), 'clause-viewer/clause_data4.db')
CSV_PATH = os.path.join(os.path.dirname(__file__), 'manual_updates.csv')

def update_db_from_csv():
    print(f"Database path: {DB_PATH}")
    print(f"CSV path: {CSV_PATH}")

    if not os.path.exists(DB_PATH):
        print(f"Error: Database not found at {DB_PATH}")
        return

    if not os.path.exists(CSV_PATH):
        print(f"Error: CSV file not found at {CSV_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get valid columns and their types
    cursor.execute("PRAGMA table_info(municipalities)")
    columns_info = cursor.fetchall()
    # columns_info structure: (cid, name, type, notnull, dflt_value, pk)
    valid_columns = {info[1]: info[2] for info in columns_info}
    
    # Columns that should not be updated manually
    protected_columns = ['id', 'name'] 

    print(f"Reading updates from {CSV_PATH}...")
    
    updates_count = 0
    skip_count = 0
    error_count = 0

    try:
        with open(CSV_PATH, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            # Check if headers are correct
            if not reader.fieldnames or 'municipality_name' not in reader.fieldnames or 'column_name' not in reader.fieldnames or 'new_value' not in reader.fieldnames:
                print("Error: CSV header must contain 'municipality_name', 'column_name', and 'new_value'.")
                return

            for row_idx, row in enumerate(reader, start=2):
                munic_name = row.get('municipality_name', '').strip()
                col_name = row.get('column_name', '').strip()
                new_val = row.get('new_value', '').strip()
                
                # Skip empty lines
                if not munic_name and not col_name and not new_val:
                    continue

                if not munic_name or not col_name:
                    print(f"Line {row_idx}: Missing municipality_name or column_name. Skipping.")
                    error_count += 1
                    continue

                if col_name not in valid_columns:
                    print(f"Line {row_idx}: Invalid column '{col_name}'. Skipping.")
                    error_count += 1
                    continue
                    
                if col_name in protected_columns:
                    print(f"Line {row_idx}: Column '{col_name}' is protected. Skipping.")
                    error_count += 1
                    continue

                # Check if municipality exists
                cursor.execute("SELECT id, " + col_name + " FROM municipalities WHERE name = ?", (munic_name,))
                result = cursor.fetchone()
                
                if not result:
                    print(f"Line {row_idx}: Municipality '{munic_name}' not found. Skipping.")
                    error_count += 1
                    continue
                
                current_val = result[1]
                
                # Convert current_val to string for comparison
                current_val_str = str(current_val) if current_val is not None else ""
                
                # Handle NULL/None explicitly if needed, but for now assume empty string in CSV means empty string or 0 depending on context.
                
                if current_val_str == new_val:
                    # Already updated
                    skip_count += 1
                    continue
                
                # Update
                try:
                    # Construct query safely. col_name is validated against schema, so it's safe from injection.
                    query = f"UPDATE municipalities SET {col_name} = ? WHERE name = ?"
                    cursor.execute(query, (new_val, munic_name))
                    updates_count += 1
                    print(f"Line {row_idx}: Updated {munic_name}.{col_name} | '{current_val_str}' -> '{new_val}'")
                except sqlite3.Error as e:
                    print(f"Line {row_idx}: Database error: {e}")
                    error_count += 1

        conn.commit()
        print("-" * 30)
        print(f"Finished processing.")
        print(f"Updated: {updates_count}")
        print(f"Skipped (already same): {skip_count}")
        print(f"Errors: {error_count}")

    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    update_db_from_csv()
