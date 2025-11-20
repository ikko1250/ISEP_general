import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'clause-viewer/clause_data3.db')

def is_clean_text(text):
    if not text:
        return False
    text = text.strip()
    if text.startswith('○'): return False
    if text.startswith('(目的)'): return True
    if text.startswith('(趣旨)'): return True
    if text.startswith('第1条'): return True
    return False

def clean_database():
    if not os.path.exists(db_path):
        print(f"Error: Database file not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Get all municipalities
        cursor.execute("SELECT id, name FROM municipalities")
        municipalities = cursor.fetchall()
        
        total_deleted_paragraphs = 0
        total_deleted_codings = 0
        affected_municipalities = 0

        print("Starting database cleanup...")

        for munic_id, munic_name in municipalities:
            # Get all years for this municipality
            cursor.execute("""
                SELECT DISTINCT year 
                FROM paragraphs 
                WHERE municipality_id = ?
            """, (munic_id,))
            years = [row[0] for row in cursor.fetchall()]
            
            if len(years) <= 1:
                continue

            # Check each year's first paragraph to determine if it's "clean"
            clean_years = []
            dirty_years = []
            
            for year in years:
                # Get the first paragraph (dan_number = 1)
                # Try with category='条例' first, then fallback
                cursor.execute("""
                    SELECT text FROM paragraphs 
                    WHERE municipality_id = ? AND year = ? AND dan_number = 1 AND category = '条例'
                """, (munic_id, year))
                row = cursor.fetchone()
                
                if not row:
                    cursor.execute("""
                        SELECT text FROM paragraphs 
                        WHERE municipality_id = ? AND year = ? AND dan_number = 1
                    """, (munic_id, year))
                    row = cursor.fetchone()
                
                if row and is_clean_text(row[0]):
                    clean_years.append(year)
                else:
                    dirty_years.append(year)
            
            # Decision logic
            years_to_delete = []
            
            if clean_years:
                # If we have clean years, delete all dirty years
                years_to_delete.extend(dirty_years)
                
                # If we have multiple clean years, keep the one with the smallest year (assuming enactment year)
                # Or should we keep the latest? The user said "correct year".
                # In the previous analysis, the "clean" one was usually the correct one.
                # If there are multiple clean ones, we might have a problem, but let's just keep the first one found (min year) for now if they are duplicates.
                # Actually, let's just delete the dirty ones for now. If there are multiple clean ones, we leave them.
                pass
            else:
                # If no clean years found, we don't know which one is correct, so skip deletion to be safe
                # Or maybe we should delete nothing.
                continue
            
            if not years_to_delete:
                continue

            print(f"Municipality: {munic_name}")
            print(f"  Keeping years: {clean_years}")
            print(f"  Deleting years: {years_to_delete}")
            
            affected_municipalities += 1
            
            for year in years_to_delete:
                # Find paragraph IDs to delete
                cursor.execute("""
                    SELECT id FROM paragraphs 
                    WHERE municipality_id = ? AND year = ?
                """, (munic_id, year))
                p_ids = [row[0] for row in cursor.fetchall()]
                
                if not p_ids:
                    continue
                    
                # Delete from paragraph_codings first
                placeholders = ','.join('?' for _ in p_ids)
                cursor.execute(f"""
                    DELETE FROM paragraph_codings 
                    WHERE paragraph_id IN ({placeholders})
                """, p_ids)
                total_deleted_codings += cursor.rowcount
                
                # Delete from paragraphs
                cursor.execute(f"""
                    DELETE FROM paragraphs 
                    WHERE id IN ({placeholders})
                """, p_ids)
                total_deleted_paragraphs += cursor.rowcount

        conn.commit()
        print("-" * 40)
        print("Cleanup complete.")
        print(f"Affected Municipalities: {affected_municipalities}")
        print(f"Deleted Paragraphs: {total_deleted_paragraphs}")
        print(f"Deleted Codings: {total_deleted_codings}")

    except sqlite3.Error as e:
        print(f"An error occurred: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    clean_database()
