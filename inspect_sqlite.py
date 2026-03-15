import sqlite3
import os

db_path = 'instance/site.db'

def inspect_sqlite():
    if not os.path.exists(db_path):
        print(f"Database {db_path} not found.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print(f"Inspecting SQLite database: {db_path}")
    
    # List tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print("Tables:", [t[0] for t in tables])
    
    # User data
    cursor.execute("SELECT id, email FROM user;")
    users = cursor.fetchall()
    print("\nUsers:", users)
    
    for user_id, email in users:
        print(f"\nData for {email} (ID: {user_id}):")
        
        # Expenses
        cursor.execute("SELECT COUNT(*) FROM expense WHERE user_id=?;", (user_id,))
        exp_count = cursor.fetchone()[0]
        
        # Financial Summary
        cursor.execute("SELECT COUNT(*) FROM financial_summary WHERE user_id=?;", (user_id,))
        sum_count = cursor.fetchone()[0]
        
        print(f"  Expenses: {exp_count} | Summaries: {sum_count}")
        
        if exp_count > 0:
            cursor.execute("SELECT MIN(date), MAX(date) FROM expense WHERE user_id=?;", (user_id,))
            dates = cursor.fetchone()
            print(f"  Expense Date Range: {dates}")
            
        if sum_count > 0:
            cursor.execute("SELECT MIN(year), MAX(year) FROM financial_summary WHERE user_id=?;", (user_id,))
            years = cursor.fetchone()
            print(f"  Summary Year Range: {years}")
            
            # Print last 5 summaries
            cursor.execute("SELECT year, month, total_expense, total_income FROM financial_summary WHERE user_id=? ORDER BY year DESC, month DESC LIMIT 5;", (user_id,))
            print("  Recent Summaries:", cursor.fetchall())

    conn.close()

if __name__ == "__main__":
    inspect_sqlite()
