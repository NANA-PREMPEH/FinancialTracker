from app import create_app, db
from app.models import User, Expense, Category, FinancialSummary, Wallet
from datetime import datetime
from sqlalchemy import func

app = create_app()

def inspect_db():
    with app.app_context():
        user = User.query.first()
        if not user:
            print("No user found.")
            return

        print(f"Inspecting data for user: {user.email}")
        
        # 1. Total Expenses (Live)
        total_live_exp = db.session.query(func.sum(Expense.amount)).filter(
            Expense.user_id == user.id,
            Expense.transaction_type == 'expense'
        ).scalar() or 0
        
        # 2. Total History
        total_hist_exp = db.session.query(func.sum(FinancialSummary.total_expense)).filter(
            FinancialSummary.user_id == user.id
        ).scalar() or 0
        
        # 3. Monthly Expenses (Current Month)
        now = datetime.utcnow()
        month_start = datetime(now.year, now.month, 1)
        curr_month_exp = db.session.query(func.sum(Expense.amount)).filter(
            Expense.user_id == user.id,
            Expense.transaction_type == 'expense',
            Expense.date >= month_start
        ).scalar() or 0

        # 4. Check for current month summary
        curr_month_hist = FinancialSummary.query.filter_by(
            user_id=user.id,
            year=now.year,
            month=now.month
        ).first()

        print(f"Total Live Expenses: {total_live_exp}")
        print(f"Total Hist Expenses: {total_hist_exp}")
        print(f"Current Month Live: {curr_month_exp}")
        print(f"Current Month Hist: {curr_month_hist.total_expense if curr_month_hist else 'None'}")
        
        # 5. Check "Actuals" category logic
        debt_lent_cat = Category.query.filter_by(name='Money Lent', user_id=user.id).first()
        coll_cat = Category.query.filter_by(name='Debt Collection', user_id=user.id).first()
        
        print(f"Money Lent Category ID: {debt_lent_cat.id if debt_lent_cat else 'Missing'}")
        print(f"Debt Collection Category ID: {coll_cat.id if coll_cat else 'Missing'}")
        
        # 6. Sample of Expenses to see tags and dates
        print("\nLast 10 Expenses:")
        expenses = Expense.query.filter_by(user_id=user.id).order_by(Expense.date.desc()).limit(10).all()
        for e in expenses:
            print(f"{e.date.strftime('%Y-%m-%d')} | {e.amount} | {e.transaction_type} | {e.category.name} | Tags: {e.tags}")

        # 7. Sample of History
        print("\nLast 5 Summaries:")
        summaries = FinancialSummary.query.filter_by(user_id=user.id).order_by(FinancialSummary.year.desc(), FinancialSummary.month.desc()).limit(5).all()
        for s in summaries:
            print(f"{s.year}-{s.month or 'Y'} | Exp: {s.total_expense} | Inc: {s.total_income}")

if __name__ == "__main__":
    inspect_db()
