from app import create_app, db
from app.models import Expense, Category, FinancialSummary, ProjectItem, ProjectItemPayment, DebtPayment, DebtorPayment, ContractPayment, User
from sqlalchemy import func, or_
from sqlalchemy.sql.functions import coalesce
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv(override=True)

app = create_app()

def test_coalesce_filter():
    with app.app_context():
        user = User.query.get(1)
        m_start = datetime(2026, 2, 1)
        m_end = datetime(2026, 3, 1)
        
        transfer_cat = Category.query.filter_by(name='Transfer', user_id=user.id).first()
        transfer_id = transfer_cat.id if transfer_cat else -1
        transfer_types = ('transfer', 'transfer_out', 'transfer_in')
        
        # COALESCE FILTER
        f_type = Expense.transaction_type.in_(transfer_types)
        f_tags = func.coalesce(Expense.tags, '').ilike('%transfer%')
        f_desc = func.coalesce(Expense.description, '').ilike('Transfer %')
        f_cat = Expense.category_id == transfer_id if transfer_id != -1 else False
        
        full_filter = or_(f_type, f_tags, f_desc, f_cat)

        q_kept = db.session.query(func.sum(Expense.amount)).filter(
            Expense.user_id == user.id,
            Expense.date >= m_start,
            Expense.date < m_end,
            Expense.transaction_type == 'expense',
            ~full_filter
        ).scalar() or 0
        
        print(f"SQLQuery Result (with COALESCE): {q_kept}")

if __name__ == "__main__":
    test_coalesce_filter()
