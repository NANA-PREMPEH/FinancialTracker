
from app import db, create_app
from app.models import FinancialSummary, User, Expense, Category, DebtPayment, DebtorPayment, ContractPayment
from sqlalchemy import func, or_
from datetime import datetime

app = create_app()
with app.app_context():
    user = User.query.first()
    year = 2024
    
    y_expense = 0
    y_income = 0
    y_lent = 0
    y_recovered = 0

    # Logic from routes_analytics.py
    yearly_hist = FinancialSummary.query.filter_by(
        user_id=user.id, year=year, month=None
    ).first()

    if yearly_hist:
        y_expense = yearly_hist.total_expense or 0
        y_income = yearly_hist.total_income or 0
        print(f"Found Yearly Summary for {year}: Income={y_income}, Expense={y_expense}")
    else:
        print(f"No Yearly Summary for {year}, checking monthly/live data...")
        # (Simplified monthly/live check for this verification)
        
    actual_expense = y_expense - y_lent
    actual_income = y_income - y_recovered
    
    print(f"Final 2024 Data:")
    print(f"  Income: {y_income} (Act: {actual_income})")
    print(f"  Expense: {y_expense} (Act: {actual_expense})")
    
    if y_income == 102745.0 and y_expense == 51235.0:
        print("VERIFICATION SUCCESSFUL")
    else:
        print("VERIFICATION FAILED")
