from app import create_app, db
from app.models import Expense, Category, FinancialSummary, ProjectItem, ProjectItemPayment, DebtPayment, DebtorPayment, ContractPayment, User
from sqlalchemy import func, or_
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv(override=True)

app = create_app()

def debug_feb_filter():
    with app.app_context():
        user = User.query.get(1)
        m_start = datetime(2026, 2, 1)
        m_end = datetime(2026, 3, 1)
        
        transfer_cat = Category.query.filter_by(name='Transfer', user_id=user.id).first()
        transfer_id = transfer_cat.id if transfer_cat else -1
        transfer_types = ('transfer', 'transfer_out', 'transfer_in')
        
        # Define separate filters to test them
        f_type = Expense.transaction_type.in_(transfer_types)
        f_tags = Expense.tags.ilike('%transfer%') == True
        f_desc = Expense.description.ilike('Transfer %') == True
        f_cat = Expense.category_id == transfer_id if transfer_id != -1 else False
        
        full_filter = or_(f_type, f_tags, f_desc, f_cat)

        expenses = Expense.query.filter(
            Expense.user_id == user.id,
            Expense.date >= m_start,
            Expense.date < m_end
        ).all()

        print(f"Total records in Feb: {len(expenses)}")
        
        filtered_count = 0
        kept_count = 0
        total_kept_amount = 0
        
        for e in expenses:
            # Manually evaluate logic
            is_transfer_type = e.transaction_type in transfer_types
            is_transfer_tag = "transfer" in (e.tags.lower() if e.tags else "")
            is_transfer_desc = (e.description or "").lower().startswith("transfer")
            is_transfer_cat = e.category_id == transfer_id
            
            should_filter = is_transfer_type or is_transfer_tag or is_transfer_desc or is_transfer_cat
            
            if should_filter:
                filtered_count += 1
                # print(f"FILTERED: {e.id} | {e.amount} | {e.transaction_type} | {e.tags} | {e.description}")
            else:
                kept_count += 1
                total_kept_amount += float(e.amount)
                # print(f"KEPT: {e.id} | {e.amount} | {e.transaction_type} | {e.tags} | {e.description}")

        print(f"Result: Kept {kept_count} records totaling {total_kept_amount}")
        print(f"Filtered {filtered_count} records.")

        # test the SQLAlchemy query directly as well
        q_kept = db.session.query(func.sum(Expense.amount)).filter(
            Expense.user_id == user.id,
            Expense.date >= m_start,
            Expense.date < m_end,
            Expense.transaction_type == 'expense',
            ~full_filter
        ).scalar() or 0
        print(f"SQLQuery Result (Expense Only, Filtered): {q_kept}")

if __name__ == "__main__":
    debug_feb_filter()
