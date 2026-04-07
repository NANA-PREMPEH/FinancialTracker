"""Verify analytics actual_expense calculation after fix"""
from datetime import datetime
from app import create_app, db
from app.models import Expense, Category, DebtPayment
from sqlalchemy import func, or_

app = create_app()

with app.app_context():
    now = datetime.utcnow()
    month_start = datetime(now.year, now.month, 1)
    
    if month_start.month == 12:
        month_end = datetime(month_start.year + 1, 1, 1)
    else:
        month_end = datetime(month_start.year, month_start.month + 1, 1)
    
    # Transfer filter
    transfer_cat = Category.query.filter_by(name='Transfer', user_id=1).first()
    transfer_id = transfer_cat.id if transfer_cat else -1
    transfer_types = ('transfer', 'transfer_out', 'transfer_in')
    transfer_filter = or_(
        Expense.transaction_type.in_(transfer_types),
        func.coalesce(Expense.tags, '').ilike('%transfer%'),
        func.coalesce(Expense.description, '').ilike('Transfer %')
    )
    if transfer_id != -1:
        transfer_filter = or_(transfer_filter, Expense.category_id == transfer_id)
    
    # Debt lent category
    debt_lent_cat = Category.query.filter_by(name='Money Lent', user_id=1).first()
    debt_lent_id = debt_lent_cat.id if debt_lent_cat else -1
    
    # Calculate like analytics does
    expense_total = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == 1,
        Expense.transaction_type == 'expense',
        Expense.date >= month_start,
        Expense.date < month_end,
        ~transfer_filter
    ).scalar() or 0
    
    m_lent = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == 1,
        Expense.transaction_type == 'expense',
        Expense.date >= month_start,
        Expense.date < month_end,
        or_(Expense.category_id == debt_lent_id, Expense.tags.ilike('%debt_lent%'))
    ).scalar() or 0
    
    m_extra_debt_exp = db.session.query(func.sum(DebtPayment.amount)).filter(
        DebtPayment.user_id == 1,
        DebtPayment.date >= month_start,
        DebtPayment.date < month_end
    ).scalar() or 0
    
    expense_total += m_extra_debt_exp
    
    print(f"=== ANALYTICS CALCULATION (April 2026) ===")
    print(f"Regular expenses: {expense_total - m_extra_debt_exp:.2f}")
    print(f"Debt payments: {m_extra_debt_exp:.2f}")
    print(f"Money lent: {m_lent:.2f}")
    print(f"\nExpenses (total): {expense_total:.2f}")
    print(f"Actual Expenses (expenses - lent - debt_payments): {expense_total - m_lent - m_extra_debt_exp:.2f}")
    print(f"\nExpected: Actual Expenses should be 726.00")
