from app import create_app, db
from app.models import Expense, Category, User
from sqlalchemy import func, or_
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv(override=True)

app = create_app()

def verify_null_theory():
    with app.app_context():
        user = User.query.get(1)
        feb_start = datetime(2026, 2, 1)
        feb_end = datetime(2026, 3, 1)

        # 1. Total records in Feb
        total_count = db.session.query(func.count(Expense.id)).filter(
            Expense.user_id == user.id,
            Expense.date >= feb_start,
            Expense.date < feb_end
        ).scalar()
        print(f"Total Feb records: {total_count}")

        # 2. Records with NULL tags
        null_tags_count = db.session.query(func.count(Expense.id)).filter(
            Expense.user_id == user.id,
            Expense.date >= feb_start,
            Expense.date < feb_end,
            Expense.tags == None
        ).scalar()
        print(f"Records with NULL tags: {null_tags_count}")

        # 3. Current filter applied
        transfer_types = ('transfer', 'transfer_out', 'transfer_in')
        transfer_filters = [
            Expense.transaction_type.in_(transfer_types),
            Expense.tags.ilike('%transfer%'),
            Expense.description.ilike('Transfer to %'),
            Expense.description.ilike('Transfer from %')
        ]
        # Skip category filter for simplicity
        transfer_filter = or_(*transfer_filters)

        filtered_count = db.session.query(func.count(Expense.id)).filter(
            Expense.user_id == user.id,
            Expense.date >= feb_start,
            Expense.date < feb_end,
            ~transfer_filter
        ).scalar()
        print(f"Records after ~transfer_filter: {filtered_count}")

        # 4. Filter with NULL handling
        improved_filter = or_(
            Expense.transaction_type.in_(transfer_types),
            Expense.tags.ilike('%transfer%'),
            Expense.description.ilike('Transfer to %'),
            Expense.description.ilike('Transfer from %')
        )
        
        # This is one way to do it: explicitly say NOT (A or B or C) OR (D is NULL and ...)
        # Better: use coalesce
        from sqlalchemy import coalesce
        robust_filter = or_(
            Expense.transaction_type.in_(transfer_types),
            coalesce(Expense.tags, '').ilike('%transfer%'),
            coalesce(Expense.description, '').ilike('Transfer %')
        )
        
        robust_filtered_count = db.session.query(func.count(Expense.id)).filter(
            Expense.user_id == user.id,
            Expense.date >= feb_start,
            Expense.date < feb_end,
            ~robust_filter
        ).scalar()
        print(f"Records after ~robust_filter: {robust_filtered_count}")

if __name__ == "__main__":
    verify_null_theory()
