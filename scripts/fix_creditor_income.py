"""
Fix existing creditor loan transactions that were incorrectly recorded as 'income'.
These should be 'liability' since they are borrowed money, not earned income.

Run with: python -m scripts.fix_creditor_income
Or from project root: python scripts/fix_creditor_income.py
"""
import sys
import os

# Add parent directory to path so we can import the app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import Expense

app = create_app()

with app.app_context():
    # Find all transactions that are loan_received but incorrectly typed as income
    bad_records = Expense.query.filter(
        Expense.transaction_type == 'income',
        Expense.tags.like('%loan_received%')
    ).all()

    if not bad_records:
        print("No incorrectly typed loan transactions found. Everything is clean!")
    else:
        print(f"Found {len(bad_records)} loan transaction(s) incorrectly recorded as 'income':\n")
        for rec in bad_records:
            print(f"  ID={rec.id}  Amount={rec.amount}  Desc='{rec.description}'  Date={rec.date}")
            rec.transaction_type = 'liability'

        db.session.commit()
        print(f"\n[FIXED] {len(bad_records)} record(s): transaction_type changed from 'income' to 'liability'")
