import sqlite3
import os

db_path = 'instance/site.db'

def inspect_brute():
    if not os.path.exists(db_path):
        print(f"Database {db_path} not found.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print(f"Brute force inspection of {db_path}:")
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [t[0] for t in cursor.fetchall()]
    
    for t in tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {t};")
            count = cursor.fetchone()[0]
            if count > 0:
                print(f"Table {t}: {count} records")
                # Show first row to see structure/sample
                cursor.execute(f"SELECT * FROM {t} LIMIT 1;")
                print(f"  Sample: {cursor.fetchone()}")
        except Exception as e:
            print(f"Table {t}: Error {e}")

    conn.close()

if __name__ == "__main__":
    inspect_brute()
