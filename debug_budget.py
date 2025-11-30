from app import create_app, db
from app.models import Expense, Category, Budget
from datetime import datetime

app = create_app()

with app.app_context():
    # Find "Food and Drink" category (or similar)
    category = Category.query.filter(Category.name.like('%Food%')).first()
    
    if not category:
        print("Category 'Food and Drink' not found.")
    else:
        print(f"Category: {category.name} (ID: {category.id})")
        
        # Check Budget
        budget = Budget.query.filter_by(category_id=category.id, is_active=True).first()
        if budget:
            print(f"Budget found: Amount={budget.amount}, Period={budget.period}")
            print(f"Budget Start Date: {budget.start_date}")
            
            # Check Expenses
            expenses = Expense.query.filter_by(category_id=category.id, transaction_type='expense').all()
            print(f"Total Expenses found: {len(expenses)}")
            
            included_count = 0
            excluded_count = 0
            for exp in expenses:
                if exp.date >= budget.start_date:
                    included_count += 1
                else:
                    excluded_count += 1
                    print(f"Excluded Expense: Date={exp.date}, Amount={exp.amount}")
            
            print(f"Included in Budget: {included_count}")
            print(f"Excluded from Budget: {excluded_count}")
        else:
            print("No active budget found for this category.")
