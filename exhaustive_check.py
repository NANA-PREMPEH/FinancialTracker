from app import create_app, db
from app.models import *
from sqlalchemy import func

app = create_app()

def exhaustive_check():
    with app.app_context():
        print(f"URL: {app.config['SQLALCHEMY_DATABASE_URI']}")
        
        user = User.query.first()
        if not user:
            print("No users at all.")
            return
            
        print(f"User: {user.email}")
        
        # Check all possible sources of "Actuals"
        sources = {
            'Expenses': Expense.query.count(),
            'Summaries': FinancialSummary.query.count(),
            'Projects': Project.query.count(),
            'Project Items': ProjectItem.query.count(),
            'Project Payments': ProjectItemPayment.query.count(),
            'Creditors': Creditor.query.count(),
            'Debtors': Debtor.query.count(),
            'Budgets': Budget.query.count(),
            'Wallets': Wallet.query.count(),
            'Transactions': Expense.query.filter(Expense.user_id==user.id).count()
        }
        
        for k, v in sources.items():
            print(f"{k}: {v}")
            
        if sources['Project Payments'] > 0:
            p = ProjectItemPayment.query.first()
            print(f"Sample Payment: {p.amount} | User ID: {p.user_id}")

        if sources['Expenses'] > 0:
            e = Expense.query.first()
            print(f"Sample Expense: {e.amount} | User ID: {e.user_id} | Date: {e.date}")

if __name__ == "__main__":
    exhaustive_check()
