from app import db, create_app
from app.models import Expense, Category, DebtorPayment, ContractPayment, DebtPayment, User
from datetime import datetime
from sqlalchemy import func, or_

def analyze_net_income():
    app = create_app()
    with app.app_context():
        user = User.query.first()
        if not user:
            print("No user found.")
            return

        print(f"User: {user.email} (ID: {user.id})")

        month_start = datetime(2026, 3, 1)
        month_end = datetime(2026, 4, 1)

        # Transfer filter (matching routes.py)
        transfer_cat = Category.query.filter_by(name='Transfer', user_id=user.id).first()
        transfer_id = transfer_cat.id if transfer_cat else -1
        transfer_types = ('transfer', 'transfer_out', 'transfer_in')
        
        transfer_filters = [
            Expense.transaction_type.in_(transfer_types),
            func.coalesce(Expense.tags, '').ilike('%transfer%'),
            func.coalesce(Expense.description, '').ilike('Transfer %')
        ]
        if transfer_id != -1:
            transfer_filters.append(Expense.category_id == transfer_id)
        
        transfer_filter = or_(*transfer_filters)

        # 1. ACTUAL INCOME
        income_txs = Expense.query.filter(
            Expense.user_id == user.id,
            Expense.transaction_type == 'income',
            Expense.date >= month_start,
            Expense.date < month_end,
            ~transfer_filter
        ).all()

        total_income = sum(e.amount for e in income_txs)
        
        coll_cat = Category.query.filter_by(name='Debt Collection', user_id=user.id).first()
        coll_id = coll_cat.id if coll_cat else -1
        rec_cat = Category.query.filter_by(name='Bad Debt Recovery', user_id=user.id).first()
        rec_id = rec_cat.id if rec_cat else -1
        
        recovered_total = sum(e.amount for e in income_txs if (e.category_id in [coll_id, rec_id] or 'debt_collection' in (e.tags or '') or 'bad_debt_recovery' in (e.tags or '')))
        
        actual_income = total_income - recovered_total

        # 2. ACTUAL EXPENSE
        expense_txs = Expense.query.filter(
            Expense.user_id == user.id,
            Expense.transaction_type == 'expense',
            Expense.date >= month_start,
            Expense.date < month_end,
            ~transfer_filter
        ).all()

        total_expense_primary = sum(e.amount for e in expense_txs)

        debt_lent_cat = Category.query.filter_by(name='Money Lent', user_id=user.id).first()
        debt_lent_id = debt_lent_cat.id if debt_lent_cat else -1
        
        money_lent_total = sum(e.amount for e in expense_txs if (e.category_id == debt_lent_id or 'debt_lent' in (e.tags or '')))
        
        # Note: routes.py adds debt_payments to expense_total but subtracts money_lent from actual_expense.
        # But we previously refined 'Actual' to only be manual expense. 
        # Actually, let's list the components clearly.
        
        actual_expense = total_expense_primary - money_lent_total

        print("\n--- ACTUAL INCOME COMPONENTS (March) ---")
        for e in income_txs:
            is_recovered = (e.category_id in [coll_id, rec_id] or 'debt_collection' in (e.tags or '') or 'bad_debt_recovery' in (e.tags or ''))
            status = "[EXCLUDED: Recovery]" if is_recovered else ""
            print(f"{e.date.strftime('%Y-%m-%d')} | {e.amount:10,.2f} | {e.description} {status}")
        
        print(f"\nTotal Actual Income: {actual_income:,.2f}")

        print("\n--- ACTUAL EXPENSE COMPONENTS (March) ---")
        for e in expense_txs:
            is_lent = (e.category_id == debt_lent_id or 'debt_lent' in (e.tags or ''))
            status = "[EXCLUDED: Lending]" if is_lent else ""
            print(f"{e.date.strftime('%Y-%m-%d')} | {e.amount:10,.2f} | {e.description} {status}")

        print(f"\nTotal Actual Expense: {actual_expense:,.2f}")
        print(f"\n--- ACTUAL NET INCOME (Income - Expense) ---")
        print(f"Net: {actual_income - actual_expense:,.2f}")

if __name__ == "__main__":
    analyze_net_income()
