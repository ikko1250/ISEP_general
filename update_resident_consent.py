import sqlite3
import os

# Database path
db_path = os.path.join(os.path.dirname(__file__), 'clause-viewer/clause_data3.db')

def update_resident_consent():
    if not os.path.exists(db_path):
        print(f"Error: Database file not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        print("Updating resident_consent column based on *CSC_bun coding...")

        # SQL to update resident_consent
        # Set '有' if the municipality has '*CSC_bun' coding, otherwise '無'
        sql = """
        UPDATE municipalities
        SET resident_consent = CASE
            WHEN id IN (
                SELECT DISTINCT p.municipality_id
                FROM paragraphs p
                JOIN paragraph_codings pc ON p.id = pc.paragraph_id
                JOIN coding_types ct ON pc.coding_type_id = ct.id
                WHERE ct.code = '*CSC_bun'
            ) THEN '有'
            ELSE '無'
        END;
        """
        
        cursor.execute(sql)
        rows_affected = cursor.rowcount
        conn.commit()
        
        print(f"Successfully updated {rows_affected} rows.")
        
        # Verification
        cursor.execute("SELECT COUNT(*) FROM municipalities WHERE resident_consent = '有'")
        count_yu = cursor.fetchone()[0]
        print(f"New count of municipalities with resident_consent = '有': {count_yu}")
        
        cursor.execute("SELECT COUNT(*) FROM municipalities WHERE resident_consent = '無'")
        count_mu = cursor.fetchone()[0]
        print(f"New count of municipalities with resident_consent = '無': {count_mu}")

    except sqlite3.Error as e:
        print(f"An error occurred: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    update_resident_consent()
