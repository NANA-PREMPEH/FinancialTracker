from app import create_app, db
from app.models import Expense, Category

app = create_app()

with app.app_context():
    try:
        print("Testing database connection...")
        category_count = Category.query.count()
        expense_count = Expense.query.count()
        print(f"Connection successful!")
        print(f"Categories: {category_count}")
        print(f"Expenses: {expense_count}")
    except Exception as e:
        print(f"Connection failed: {e}")
