
from app import db, create_app
from app.models import FinancialSummary, User

app = create_app()
with app.app_context():
    user = User.query.first()
    if not user:
        print("No user found")
    else:
        summaries = FinancialSummary.query.filter_by(user_id=user.id, year=2024).all()
        print(f"Summaries for 2024 (User ID {user.id}):")
        for s in summaries:
            print(f"ID: {s.id}, Month: {s.month}, Income: {s.total_income}, Expense: {s.total_expense}, Notes: {s.notes}")
