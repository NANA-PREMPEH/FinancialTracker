from app import create_app, db
from app.models import FinancialSummary

app = create_app()
with app.app_context():
    summaries = FinancialSummary.query.all()
    print(f"Total summaries found: {len(summaries)}")
    for s in summaries:
        print(f"ID: {s.id}, Year: {s.year}, Month: {s.month}, UserID: {s.user_id}, Income: {s.total_income}, Expense: {s.total_expense}")
