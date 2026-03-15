from app import create_app, db
from app.models import Expense, Category, FinancialSummary, ProjectItem, ProjectItemPayment, DebtPayment, DebtorPayment, ContractPayment, User
from sqlalchemy import func, or_
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv(override=True)

app = create_app()

def simulate_dashboard():
    with app.app_context():
        user = User.query.get(1)
        now = datetime(2026, 3, 13) # Simulate "today"
        
        transfer_cat = Category.query.filter_by(name='Transfer', user_id=user.id).first()
        transfer_id = transfer_cat.id if transfer_cat else -1
        transfer_types = ('transfer', 'transfer_out', 'transfer_in')
        transfer_filters = [
            Expense.transaction_type.in_(transfer_types),
            Expense.tags.ilike('%transfer%'),
            Expense.description.ilike('Transfer to %'),
            Expense.description.ilike('Transfer from %')
        ]
        if transfer_id != -1:
            transfer_filters.append(Expense.category_id == transfer_id)
        transfer_filter = or_(*transfer_filters)

        debt_lent_cat = Category.query.filter_by(name='Money Lent', user_id=user.id).first()
        debt_lent_id = debt_lent_cat.id if debt_lent_cat else -1

        print(f"Transfer ID: {transfer_id}, Money Lent ID: {debt_lent_id}")

        monthly_trend = []
        for i in range(5, -1, -1):
            m = now.month - i
            y = now.year
            while m <= 0:
                m += 12
                y -= 1
            m_start = datetime(y, m, 1)
            if m == 12:
                m_end = datetime(y + 1, 1, 1)
            else:
                m_end = datetime(y, m + 1, 1)
            
            # --- EXPENSES ---
            m_total = db.session.query(func.sum(Expense.amount)).filter(
                Expense.user_id == user.id,
                Expense.transaction_type == 'expense',
                Expense.date >= m_start,
                Expense.date < m_end,
                ~transfer_filter
            ).scalar() or 0

            # Add Historical Data for this month
            hist_summary = FinancialSummary.query.filter_by(
                user_id=user.id,
                year=y,
                month=m
            ).first()
            if hist_summary:
                m_total += hist_summary.total_expense

            # Extra payments for this month
            m_extra_proj_exp = db.session.query(func.sum(ProjectItemPayment.amount)).join(
                ProjectItem, ProjectItemPayment.project_item_id == ProjectItem.id
            ).filter(
                ProjectItemPayment.user_id == user.id,
                ProjectItemPayment.is_paid == True,
                ProjectItemPayment.payment_date >= m_start,
                ProjectItemPayment.payment_date < m_end,
                ProjectItem.item_type != 'income'
            ).scalar() or 0

            m_extra_debt_exp = db.session.query(func.sum(DebtPayment.amount)).filter(
                DebtPayment.user_id == user.id,
                DebtPayment.date >= m_start,
                DebtPayment.date < m_end
            ).scalar() or 0

            m_total_with_extras = float(m_total) + float(m_extra_proj_exp) + float(m_extra_debt_exp)

            m_lent = db.session.query(func.sum(Expense.amount)).filter(
                Expense.user_id == user.id,
                Expense.transaction_type == 'expense',
                Expense.date >= m_start,
                Expense.date < m_end,
                or_(Expense.category_id == debt_lent_id, Expense.tags.ilike('%debt_lent%'))
            ).scalar() or 0

            actual_amount = float(m_total_with_extras) - float(m_lent)

            # --- INCOME ---
            m_income_total = db.session.query(func.sum(Expense.amount)).filter(
                Expense.user_id == user.id,
                Expense.transaction_type == 'income',
                Expense.date >= m_start,
                Expense.date < m_end,
                ~transfer_filter
            ).scalar() or 0
            
            if hist_summary:
                m_income_total += hist_summary.total_income
            
            # Extra income
            m_extra_proj_inc = db.session.query(func.sum(ProjectItemPayment.amount)).join(
                ProjectItem, ProjectItemPayment.project_item_id == ProjectItem.id
            ).filter(
                ProjectItemPayment.user_id == user.id,
                ProjectItemPayment.is_paid == True,
                ProjectItemPayment.payment_date >= m_start,
                ProjectItemPayment.payment_date < m_end,
                ProjectItem.item_type == 'income'
            ).scalar() or 0
            
            m_extra_debtor_inc = db.session.query(func.sum(DebtorPayment.amount)).filter(
                DebtorPayment.user_id == user.id,
                DebtorPayment.date >= m_start,
                DebtorPayment.date < m_end
            ).scalar() or 0
            
            m_extra_contract_inc = db.session.query(func.sum(ContractPayment.amount)).filter(
                ContractPayment.user_id == user.id,
                ContractPayment.payment_date >= m_start,
                ContractPayment.payment_date < m_end
            ).scalar() or 0
            
            m_income_total_with_extras = float(m_income_total) + float(m_extra_proj_inc) + float(m_extra_debtor_inc) + float(m_extra_contract_inc)

            print(f"Month: {y}-{m}")
            print(f"  Live Expense (Filtered): {float(m_total) - (hist_summary.total_expense if hist_summary else 0)}")
            print(f"  Hist Expense: {float(hist_summary.total_expense) if hist_summary else 0}")
            print(f"  Extra Proj Exp: {float(m_extra_proj_exp)}")
            print(f"  Extra Debt Exp: {float(m_extra_debt_exp)}")
            print(f"  Lent (Subtract): {float(m_lent)}")
            print(f"  Actual Expense: {actual_amount}")
            print(f"  Actual Income: {m_income_total_with_extras}") # Simplified for now
            print("-" * 20)

if __name__ == "__main__":
    simulate_dashboard()
