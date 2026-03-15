from app import create_app, db
from app.models import Expense, Category, FinancialSummary, ProjectItem, ProjectItemPayment, DebtPayment, DebtorPayment, ContractPayment, User
from sqlalchemy import func, or_
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv(override=True)

app = create_app()

def verify_separation():
    with app.app_context():
        user = User.query.get(1)
        now = datetime(2026, 3, 13) 
        
        transfer_cat = Category.query.filter_by(name='Transfer', user_id=user.id).first()
        transfer_id = transfer_cat.id if transfer_cat else -1
        transfer_types = ('transfer', 'transfer_out', 'transfer_in')
        
        transfer_filter = or_(
            Expense.transaction_type.in_(transfer_types),
            func.coalesce(Expense.tags, '').ilike('%transfer%'),
            func.coalesce(Expense.description, '').ilike('Transfer %')
        )
        if transfer_id != -1:
            transfer_filter = or_(transfer_filter, Expense.category_id == transfer_id)

        print("--- DASHBOARD TOTALS (PROJECTS EXCLUDED) ---")
        latest_summary = FinancialSummary.query.filter_by(user_id=user.id).order_by(
            FinancialSummary.year.desc(), FinancialSummary.month.desc()).first()
        
        if latest_summary:
            ly, lm = latest_summary.year, latest_summary.month or 12
            live_totals_start = datetime(ly + 1, 1, 1) if lm == 12 else datetime(ly, lm + 1, 1)
        else:
            live_totals_start = datetime(2024, 1, 1)

        # 1. Expense Table (Total)
        live_expenses = db.session.query(func.sum(Expense.amount)).filter(
            Expense.user_id == user.id,
            Expense.transaction_type == 'expense',
            Expense.date >= live_totals_start,
            ~transfer_filter
        ).scalar() or 0
        
        # 2. Manual Project Expenses in Expense Table
        manual_project_exp = db.session.query(func.sum(Expense.amount)).filter(
            Expense.user_id == user.id,
            Expense.transaction_type == 'expense',
            Expense.date >= live_totals_start,
            func.coalesce(Expense.tags, '').ilike('%Project%'),
            ~transfer_filter
        ).scalar() or 0

        # 3. Project Item Payments (MODULE) - SHOULD BE EXCLUDED NOW
        project_module_exp = db.session.query(func.sum(ProjectItemPayment.amount)).join(
            ProjectItem, ProjectItemPayment.project_item_id == ProjectItem.id
        ).filter(
            ProjectItemPayment.user_id == user.id,
            ProjectItemPayment.is_paid == True,
            ProjectItemPayment.payment_date >= live_totals_start,
            ProjectItem.item_type != 'income'
        ).scalar() or 0

        # 4. Debt Payments
        debt_payments = db.session.query(func.sum(DebtPayment.amount)).filter(
            DebtPayment.user_id == user.id,
            DebtPayment.date >= live_totals_start
        ).scalar() or 0

        hist_expenses = db.session.query(func.sum(FinancialSummary.total_expense)).filter(
            FinancialSummary.user_id == user.id,
            FinancialSummary.year >= 2024
        ).scalar() or 0

        new_total = float(live_expenses) + float(debt_payments) + float(hist_expenses)
        old_total_with_proj = new_total + float(project_module_exp)

        print(f"Manual Project Expenses (Kept): {manual_project_exp}")
        print(f"Project Module Payments (Removed): {project_module_exp}")
        print(f"Debt Payments (Kept): {debt_payments}")
        print(f"New Dashboard Total: {new_total}")
        print(f"Old Inflated Total: {old_total_with_proj}")
        print("-" * 30)

        print("--- TRENDING FEB 2026 ---")
        m_start = datetime(2026, 2, 1)
        m_end = datetime(2026, 3, 1)
        m_exp = db.session.query(func.sum(Expense.amount)).filter(
            Expense.user_id == user.id,
            Expense.transaction_type == 'expense',
            Expense.date >= m_start,
            Expense.date < m_end,
            ~transfer_filter
        ).scalar() or 0
        m_debt = db.session.query(func.sum(DebtPayment.amount)).filter(
            DebtPayment.user_id == user.id,
            DebtPayment.date >= m_start,
            DebtPayment.date < m_end
        ).scalar() or 0
        
        print(f"Feb Live Expense: {m_exp}")
        print(f"Feb Debt Pay: {m_debt}")
        print(f"Feb Total: {float(m_exp) + float(m_debt)}")

if __name__ == "__main__":
    verify_separation()
