import os
from dotenv import load_dotenv
import pymysql
from datetime import datetime

load_dotenv(override=True)

db_url = os.environ.get('DATABASE_URL')
part1 = db_url.split('://')[1]
creds, host_part = part1.split('@')
user, password = creds.split(':')
host_db = host_part.split('/')
host = host_db[0].split(':')[0]
port = int(host_db[0].split(':')[1]) if ':' in host_db[0] else 3306
db_name = host_db[1]

conn = pymysql.connect(host=host, port=port, user=user, password=password, db=db_name)
cursor = conn.cursor()

user_id = 1
start_date = '2024-01-01'

# Get Transfer and Money Lent categories (mimic routes.py)
cursor.execute("SELECT id FROM category WHERE name='Transfer' AND user_id=%s", (user_id,))
transfer_cat = cursor.fetchone()
transfer_id = transfer_cat[0] if transfer_cat else -1

print(f"Transfer ID: {transfer_id}")

# 1. Total Live Expenses (excluding transfers)
cursor.execute("""
    SELECT SUM(amount) FROM expense 
    WHERE user_id=%s AND transaction_type='expense' AND date >= %s
    AND NOT (
        transaction_type IN ('transfer', 'transfer_out', 'transfer_in') OR
        tags LIKE '%%transfer%%' OR
        description LIKE 'Transfer %%' OR
        category_id = %s
    )
""", (user_id, start_date, transfer_id))
live_total = cursor.fetchone()[0] or 0

# 2. Total Historical Expenses
cursor.execute("SELECT SUM(total_expense) FROM financial_summary WHERE user_id=%s AND year >= 2024", (user_id,))
hist_total = cursor.fetchone()[0] or 0

print(f"Total Live (Filtered): {live_total}")
print(f"Total Historical: {hist_total}")
print(f"Combined (Current Dashboard Logic): {live_total + hist_total}")

# 3. Check specific months to see if they exist in both
print("\n=== Overlapping Months (Summary exists and Expense exists) ===")
cursor.execute("SELECT DISTINCT year, month FROM financial_summary WHERE user_id=%s ORDER BY year, month", (user_id,))
summaries = cursor.fetchall()
for y, m in summaries:
    m_start = f"{y}-{m:02d}-01"
    if m == 12:
        m_end = f"{y+1}-01-01"
    else:
        m_end = f"{y}-{m+1:02d}-01"
    
    cursor.execute("""
        SELECT SUM(amount) FROM expense 
        WHERE user_id=%s AND transaction_type='expense' AND date >= %s AND date < %s
        AND NOT (
            transaction_type IN ('transfer', 'transfer_out', 'transfer_in') OR
            tags LIKE '%%transfer%%' OR
            description LIKE 'Transfer %%' OR
            category_id = %s
        )
    """, (user_id, m_start, m_end, transfer_id))
    m_live = cursor.fetchone()[0] or 0
    if m_live > 0:
        cursor.execute("SELECT total_expense FROM financial_summary WHERE user_id=%s AND year=%s AND month=%s", (user_id, y, m))
        m_hist = cursor.fetchone()[0]
        print(f"  {y}-{m}: Live={m_live}, Hist={m_hist} -> DOUBLED!")

conn.close()
