import os
from dotenv import load_dotenv

# Set the path to the current directory's .env file
load_dotenv(dotenv_path=os.path.join(os.getcwd(), '.env'))

from app import create_app, db
from app.models import Expense, FinancialSummary, User

app = create_app()

def check_mysql():
    with app.app_context():
        print(f"DATABASE_URL from Env: {os.environ.get('DATABASE_URL')}")
        print(f"Current App DB URI: {app.config['SQLALCHEMY_DATABASE_URI']}")
        
        try:
            user_count = User.query.count()
            print(f"Total Users: {user_count}")
            
            exp_count = Expense.query.count()
            print(f"Total Expenses: {exp_count}")
            
            hist_count = FinancialSummary.query.count()
            print(f"Total Summaries: {hist_count}")
            
            if exp_count > 0:
                e = Expense.query.first()
                print(f"Sample Expense: {e.amount} | Date: {e.date}")
                
        except Exception as e:
            print(f"Error connecting to DB: {e}")

if __name__ == "__main__":
    check_mysql()
