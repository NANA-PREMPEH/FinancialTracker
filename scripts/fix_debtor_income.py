"""
Fix existing debtor collection transactions that were incorrectly recorded as 'income'.
These should be 'debt_recovery' since they are return of money already lent, not earned income.

Run with: python scripts/fix_debtor_income.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import Expense

app = create_app()

with app.app_context():
    # Find all debt collection transactions incorrectly typed as income
    bad_collections = Expense.query.filter(
        Expense.transaction_type == 'income',
        Expense.tags.like('%debt_collection%')
    ).all()

    bad_recoveries = Expense.query.filter(
        Expense.transaction_type == 'income',
        Expense.tags.like('%bad_debt_recovery%')
    ).all()

    bad_records = bad_collections + bad_recoveries
    
    if not bad_records:
        print("No incorrectly typed debtor transactions found. Everything is clean!")
    else:
        print(f"Found {len(bad_records)} debtor transaction(s) incorrectly recorded as 'income':\n")
        for rec in bad_records:
            print(f"  ID={rec.id}  Amount={rec.amount}  Desc='{rec.description}'  Tags={rec.tags}  Date={rec.date}")
            rec.transaction_type = 'debt_recovery'

        db.session.commit()
        print(f"\n[FIXED] {len(bad_records)} record(s): transaction_type changed from 'income' to 'debt_recovery'")
