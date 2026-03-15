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

feb_start = '2026-02-01'
feb_end = '2026-03-01'
user_id = 1  # primary user

print("=== Expense table (Feb 2026) ===")
cursor.execute("SELECT COUNT(*), SUM(amount), transaction_type FROM expense WHERE user_id=%s AND date >= %s AND date < %s GROUP BY transaction_type", (user_id, feb_start, feb_end))
for row in cursor.fetchall():
    print(f"  {row[2]}: {row[0]} records, total={row[1]}")

print("\n=== FinancialSummary table (Feb 2026) ===")
cursor.execute("SELECT year, month, total_income, total_expense FROM financial_summary WHERE user_id=%s AND year=2026 AND month=2", (user_id,))
rows = cursor.fetchall()
if rows:
    for r in rows:
        print(f"  {r[0]}-{r[1]}: income={r[2]}, expense={r[3]}")
else:
    print("  No FinancialSummary record for Feb 2026")

print("\n=== ProjectItemPayment (Feb 2026) ===")
cursor.execute("SELECT COUNT(*), SUM(amount) FROM project_item_payment WHERE user_id=%s AND is_paid=1 AND payment_date >= %s AND payment_date < %s", (user_id, feb_start, feb_end))
row = cursor.fetchone()
print(f"  {row[0]} records, total={row[1]}")

print("\n=== Historical FinancialSummary (all records) ===")
cursor.execute("SELECT year, month, total_income, total_expense FROM financial_summary WHERE user_id=%s ORDER BY year, month", (user_id,))
for r in cursor.fetchall():
    print(f"  {r[0]}-{r[1]}: income={r[2]}, expense={r[3]}")

print("\n=== Recent Expenses (last 10) ===")
cursor.execute("SELECT date, amount, transaction_type, description FROM expense WHERE user_id=%s ORDER BY date DESC LIMIT 10", (user_id,))
for r in cursor.fetchall():
    print(f"  {r[0]}: {r[2]} {r[1]} - {r[3]}")

conn.close()
