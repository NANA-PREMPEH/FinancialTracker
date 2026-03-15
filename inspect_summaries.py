import sqlite3
import os

db_path = 'instance/site.db'

def inspect_summaries():
    if not os.path.exists(db_path):
        print(f"Database {db_path} not found.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print(f"Inspecting FinancialSummary in {db_path}:")
    
    # Check for any records at all
    cursor.execute("SELECT COUNT(*) FROM financial_summary;")
    total = cursor.fetchone()[0]
    print(f"Total summaries: {total}")
    
    if total > 0:
        cursor.execute("SELECT year, month, total_expense, total_income FROM financial_summary;")
        rows = cursor.fetchall()
        for r in rows:
            print(f"Year: {r[0]}, Month: {r[1]}, Exp: {r[2]}, Inc: {r[3]}")
    else:
        # Check MySQL if we can
        print("SQLite is empty. If the user has data, it MUST be in MySQL or another file.")

    conn.close()

if __name__ == "__main__":
    inspect_summaries()
