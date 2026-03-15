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
jan_start = '2026-01-01'
jan_end = '2026-02-01'

print("=== ALL Jan 2026 Records ===")
query = "SELECT date, amount, transaction_type, category_id, tags, description FROM expense WHERE user_id=%s AND date >= %s AND date < %s ORDER BY date ASC"
cursor.execute(query, (user_id, jan_start, jan_end))
rows = cursor.fetchall()
for r in rows:
    if r[2] == 'expense' and r[4] and 'transfer' in r[4].lower():
         print(f"Transfer-tagged Expense: {r}")
    elif r[2] == 'expense':
         print(f"Normal Expense: {r}")
    else:
         print(f"Other: {r}")

conn.close()
