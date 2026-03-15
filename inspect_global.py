import sqlite3
import os

db_path = 'instance/site.db'

def inspect_agnostic():
    if not os.path.exists(db_path):
        print(f"Database {db_path} not found.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print(f"Global inspection of {db_path}:")
    
    # 1. Check all users
    cursor.execute("SELECT id, email FROM user;")
    users = cursor.fetchall()
    print("Users:", users)
    
    # 2. Check total record counts for key tables
    tables = ['expense', 'financial_summary', 'wallet', 'category', 'creditor', 'debtor', 'project']
    for t in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {t};")
        count = cursor.fetchone()[0]
        print(f"Table {t}: {count} records")
        
    # 3. If wallets exist, show balances
    if 'wallet' in tables:
        cursor.execute("SELECT name, balance, user_id FROM wallet;")
        print("\nWallets:", cursor.fetchall())

    conn.close()

if __name__ == "__main__":
    inspect_agnostic()
