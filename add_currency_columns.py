
import sqlite3
import os

def upgrade_db():
    db_path = os.path.join('app', 'expenses.db')
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        print("Adding original_amount column...")
        cursor.execute("ALTER TABLE expense ADD COLUMN original_amount FLOAT")
        print("Success.")
    except sqlite3.OperationalError as e:
        print(f"Column might already exist: {e}")

    try:
        print("Adding original_currency column...")
        cursor.execute("ALTER TABLE expense ADD COLUMN original_currency VARCHAR(10)")
        print("Success.")
    except sqlite3.OperationalError as e:
        print(f"Column might already exist: {e}")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    upgrade_db()
