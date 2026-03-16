from app import db, create_app
from app.models import Expense, Category, DebtorPayment, ContractPayment, User
from datetime import datetime
from sqlalchemy import func, or_

def analyze_income():
    app = create_app()
    with app.app_context():
        user = User.query.first()
        if not user:
            print("No user found.")
            return

        print(f"User: {user.email} (ID: {user.id})")

        month_start = datetime(2026, 3, 1)
        month_end = datetime(2026, 4, 1)

        # Transfer filter
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

        income_txs = Expense.query.filter(
            Expense.user_id == user.id,
            Expense.transaction_type == 'income',
            Expense.date >= month_start,
            Expense.date < month_end,
            ~transfer_filter
        ).all()

        print("\n--- Income Transactions (Expense Table) ---")
        total_income = 0
        for e in income_txs:
            print(f"{e.date.strftime('%Y-%m-%d')} | {e.amount:,.2f} | {e.description} | {e.category.name if e.category else 'N/A'}")
            total_income += e.amount
        print(f"Total Income from Expense Table: {total_income:,.2f}")

        # Exclusions
        coll_cat = Category.query.filter_by(name='Debt Collection', user_id=user.id).first()
        coll_id = coll_cat.id if coll_cat else -1
        rec_cat = Category.query.filter_by(name='Bad Debt Recovery', user_id=user.id).first()
        rec_id = rec_cat.id if rec_cat else -1

        recovered = [e for e in income_txs if (e.category_id in [coll_id, rec_id] or 'debt_collection' in (e.tags or '') or 'bad_debt_recovery' in (e.tags or ''))]

        print("\n--- Excluded Debt Recoveries (from Expense table) ---")
        total_recovered = 0
        for r in recovered:
            print(f"{r.date.strftime('%Y-%m-%d')} | {r.amount:,.2f} | {r.description}")
            total_recovered += r.amount
        print(f"Total Recovered: {total_recovered:,.2f}")

        debtor_payments = DebtorPayment.query.filter(
            DebtorPayment.user_id == user.id,
            DebtorPayment.date >= month_start,
            DebtorPayment.date < month_end
        ).all()

        print("\n--- Excluded Debtor Payments (DebtorPayment Table) ---")
        total_debtor = 0
        for dp in debtor_payments:
            print(f"{dp.date.strftime('%Y-%m-%d')} | {dp.amount:,.2f} | {dp.notes or 'No notes'}")
            total_debtor += dp.amount
        print(f"Total Debtor Payments: {total_debtor:,.2f}")

        contract_payments = ContractPayment.query.filter(
            ContractPayment.user_id == user.id,
            ContractPayment.payment_date >= month_start,
            ContractPayment.payment_date < month_end
        ).all()

        print("\n--- Excluded Contract Payments (ContractPayment Table) ---")
        total_contract = 0
        for cp in contract_payments:
            print(f"{cp.payment_date.strftime('%Y-%m-%d')} | {cp.amount:,.2f} | {cp.description or 'No description'}")
            total_contract += cp.amount
        print(f"Total Contract Payments: {total_contract:,.2f}")

        actual_income = total_income - total_recovered
        print(f"\nFinal Actual Income for March 2026: {actual_income:,.2f}")
        print("(Calculated as: Total Income - Debt Recoveries)")

if __name__ == "__main__":
    analyze_income()
