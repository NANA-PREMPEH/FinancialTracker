from app import create_app, db
from app.models import Expense, Category, FinancialSummary, ProjectItem, ProjectItemPayment, DebtPayment, DebtorPayment, ContractPayment, User
from sqlalchemy import func, or_
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv(override=True)

app = create_app()

def verify_dashboard():
    with app.app_context():
        user = User.query.get(1)
        now = datetime(2026, 3, 13) # Simulate "today"
        
        transfer_cat = Category.query.filter_by(name='Transfer', user_id=user.id).first()
        transfer_id = transfer_cat.id if transfer_cat else -1
        transfer_types = ('transfer', 'transfer_out', 'transfer_in')
        
        # NEW ROBUST FILTER
        transfer_filter = or_(
            Expense.transaction_type.in_(transfer_types),
            func.coalesce(Expense.tags, '').ilike('%transfer%'),
            func.coalesce(Expense.description, '').ilike('Transfer %')
        )
        if transfer_id != -1:
            transfer_filter = or_(transfer_filter, Expense.category_id == transfer_id)

        debt_lent_cat = Category.query.filter_by(name='Money Lent', user_id=user.id).first()
        debt_lent_id = debt_lent_cat.id if debt_lent_cat else -1

        print("--- ALL-TIME TOTALS (DE-DUPLICATED) ---")
        dashboard_start_date = datetime(2024, 1, 1)
        
        latest_summary = FinancialSummary.query.filter_by(user_id=user.id).order_by(
            FinancialSummary.year.desc(), FinancialSummary.month.desc()).first()
        
        if latest_summary:
            ly, lm = latest_summary.year, latest_summary.month or 12
            if lm == 12:
                live_totals_start = datetime(ly + 1, 1, 1)
            else:
                live_totals_start = datetime(ly, lm + 1, 1)
            print(f"Latest Summary: {ly}-{lm}. Live data starts from: {live_totals_start.strftime('%Y-%m-%d')}")
        else:
            live_totals_start = dashboard_start_date
            print(f"No summaries found. Live data starts from: {dashboard_start_date.strftime('%Y-%m-%d')}")

        # Live Expenses Filtered
        live_expenses = db.session.query(func.sum(Expense.amount)).filter(
            Expense.user_id == user.id,
            Expense.transaction_type == 'expense',
            Expense.date >= live_totals_start,
            ~transfer_filter
        ).scalar() or 0
        
        # Extras (Live)
        extra_proj_exp = db.session.query(func.sum(ProjectItemPayment.amount)).filter(
            ProjectItemPayment.user_id == user.id,
            ProjectItemPayment.is_paid == True,
            ProjectItemPayment.payment_date >= live_totals_start
        ).scalar() or 0
        # Actually need to filter by ProjectItem.item_type != 'income' but for verification simple sum is okay if we know the data
        # Let's be precise
        extra_proj_exp = db.session.query(func.sum(ProjectItemPayment.amount)).join(
            ProjectItem, ProjectItemPayment.project_item_id == ProjectItem.id
        ).filter(
            ProjectItemPayment.user_id == user.id,
            ProjectItemPayment.is_paid == True,
            ProjectItemPayment.payment_date >= live_totals_start,
            ProjectItem.item_type != 'income'
        ).scalar() or 0

        extra_debt_exp = db.session.query(func.sum(DebtPayment.amount)).filter(
            DebtPayment.user_id == user.id,
            DebtPayment.date >= live_totals_start
        ).scalar() or 0

        # Hist Expenses
        hist_expenses = db.session.query(func.sum(FinancialSummary.total_expense)).filter(
            FinancialSummary.user_id == user.id,
            FinancialSummary.year >= 2024
        ).scalar() or 0

        total_final = float(live_expenses) + float(extra_proj_exp) + float(extra_debt_exp) + float(hist_expenses)
        print(f"Hist Total: {hist_expenses}")
        print(f"Live Total (Expense Table): {live_expenses}")
        print(f"Live Extras (Proj + Debt): {extra_proj_exp + extra_debt_exp}")
        print(f"TOTAL DASHBOARD ACTUALS: {total_final}")
        print("-" * 30)

        print("--- TRENDING DATA (6 MONTHS) ---")
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
            
            hist_m = FinancialSummary.query.filter_by(user_id=user.id, year=y, month=m).first()
            if hist_m:
                m_total = hist_m.total_expense
                source = "HISTORY"
            else:
                source = "LIVE"
                m_exp = db.session.query(func.sum(Expense.amount)).filter(
                    Expense.user_id == user.id,
                    Expense.transaction_type == 'expense',
                    Expense.date >= m_start,
                    Expense.date < m_end,
                    ~transfer_filter
                ).scalar() or 0
                
                m_extra_proj = db.session.query(func.sum(ProjectItemPayment.amount)).join(
                    ProjectItem, ProjectItemPayment.project_item_id == ProjectItem.id
                ).filter(
                    ProjectItemPayment.user_id == user.id,
                    ProjectItemPayment.is_paid == True,
                    ProjectItemPayment.payment_date >= m_start,
                    ProjectItemPayment.payment_date < m_end,
                    ProjectItem.item_type != 'income'
                ).scalar() or 0

                m_extra_debt = db.session.query(func.sum(DebtPayment.amount)).filter(
                    DebtPayment.user_id == user.id,
                    DebtPayment.date >= m_start,
                    DebtPayment.date < m_end
                ).scalar() or 0
                
                m_total = float(m_exp) + float(m_extra_proj) + float(m_extra_debt)

            print(f"Month {y}-{m:02d}: {m_total:10.2f} GHS [{source}]")

if __name__ == "__main__":
    verify_dashboard()
