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
user_id = 1

# Get Transfer and Money Lent categories (mimic routes.py)
cursor.execute("SELECT id FROM category WHERE name='Transfer' AND user_id=%s", (user_id,))
transfer_cat = cursor.fetchone()
transfer_id = transfer_cat[0] if transfer_cat else -1

cursor.execute("SELECT id FROM category WHERE name='Money Lent' AND user_id=%s", (user_id,))
debt_lent_cat = cursor.fetchone()
debt_lent_id = debt_lent_cat[0] if debt_lent_cat else -1

print(f"Transfer ID: {transfer_id}, Money Lent ID: {debt_lent_id}")

# Mimic the transfer filter logic
# ~ (Expense.transaction_type.in_(('transfer', 'transfer_out', 'transfer_in')) | tags ilike %transfer% | description ilike 'Transfer %' | category_id == transfer_id)

print("\n=== Detailed Feb 2026 Expense Breakdown ===")
query = """
SELECT amount, transaction_type, category_id, tags, description 
FROM expense 
WHERE user_id=%s AND date >= %s AND date < %s
"""
cursor.execute(query, (user_id, feb_start, feb_end))
rows = cursor.fetchall()

total_raw = 0
total_filtered_expense = 0
money_lent_subtotal = 0
transfers_excluded = 0

for r in rows:
    amt, ttype, cat_id, tags, desc = r
    total_raw += amt
    
    is_transfer = (
        ttype in ('transfer', 'transfer_out', 'transfer_in') or
        (tags and 'transfer' in tags.lower()) or
        (desc and desc.lower().startswith('transfer')) or
        cat_id == transfer_id
    )
    
    if is_transfer:
        transfers_excluded += amt
        continue
    
    if ttype == 'expense':
        total_filtered_expense += amt
        
        is_lent = (
            cat_id == debt_lent_id or 
            (tags and 'debt_lent' in tags.lower())
        )
        if is_lent:
            money_lent_subtotal += amt

print(f"Total Raw Amount: {total_raw}")
print(f"Transfers Excluded: {transfers_excluded}")
print(f"Filtered Expense Total (m_total): {total_filtered_expense}")
print(f"Money Lent Subtotal (m_lent): {money_lent_subtotal}")
print(f"Actual Expense (m_total - m_lent): {total_filtered_expense - money_lent_subtotal}")

print("\n=== Are there any Debt/Debtor/Project payments in Feb? ===")
# DebtPayment
cursor.execute("SELECT SUM(amount) FROM debt_payment WHERE user_id=%s AND date >= %s AND date < %s", (user_id, feb_start, feb_end))
print(f"DebtPayment Total: {cursor.fetchone()[0]}")

# DebtorPayment
cursor.execute("SELECT SUM(amount) FROM debtor_payment WHERE user_id=%s AND date >= %s AND date < %s", (user_id, feb_start, feb_end))
print(f"DebtorPayment Total: {cursor.fetchone()[0]}")

# ProjectItemPayment
cursor.execute("""
    SELECT SUM(p.amount) 
    FROM project_item_payment p
    JOIN project_item i ON p.project_item_id = i.id
    WHERE p.user_id=%s AND p.is_paid=1 AND p.payment_date >= %s AND p.payment_date < %s
    AND i.item_type != 'income'
""", (user_id, feb_start, feb_end))
print(f"Project Expense Payment Total: {cursor.fetchone()[0]}")

conn.close()
