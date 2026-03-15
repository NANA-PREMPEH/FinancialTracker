from app import create_app, db
from app.models import User, Expense, Category, FinancialSummary, Wallet
from sqlalchemy import func

app = create_app()

def inspect_all():
    with app.app_context():
        users = User.query.all()
        print(f"Total Users: {len(users)}")
        for u in users:
            exp_count = Expense.query.filter_by(user_id=u.id).count()
            sum_count = FinancialSummary.query.filter_by(user_id=u.id).count()
            print(f"User: {u.email} (ID: {u.id}) | Expenses: {exp_count} | Summaries: {sum_count}")
            
            if exp_count > 0:
                min_date = db.session.query(func.min(Expense.date)).filter_by(user_id=u.id).scalar()
                max_date = db.session.query(func.max(Expense.date)).filter_by(user_id=u.id).scalar()
                print(f"  Expense Date Range: {min_date} to {max_date}")
            
            if sum_count > 0:
                min_year = db.session.query(func.min(FinancialSummary.year)).filter_by(user_id=u.id).scalar()
                max_year = db.session.query(func.max(FinancialSummary.year)).filter_by(user_id=u.id).scalar()
                print(f"  Summary Year Range: {min_year} to {max_year}")

if __name__ == "__main__":
    inspect_all()
