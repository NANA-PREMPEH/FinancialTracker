from app import create_app, db
from app.models import Expense, Category, Budget
from datetime import datetime
from sqlalchemy import func

app = create_app()

with app.app_context():
    # Find "Food and Drink" category
    category = Category.query.filter(Category.name.like('%Food%')).first()
    
    if not category:
        print("Category 'Food and Drink' not found.")
    else:
        print(f"Category: {category.name} (ID: {category.id})")
        
        # Check Budget
        budget = Budget.query.filter_by(category_id=category.id, is_active=True).first()
        if budget:
            print(f"\nBudget found: Amount={budget.amount}, Period={budget.period}")
            print(f"Budget Creation Date: {budget.start_date}")
            
            # Calculate effective start date (NEW LOGIC)
            now = datetime.utcnow()
            if budget.period == 'weekly':
                effective_start = now - timedelta(days=now.weekday())
            elif budget.period == 'monthly':
                effective_start = datetime(now.year, now.month, 1)
            elif budget.period == 'yearly':
                effective_start = datetime(now.year, 1, 1)
            else:
                effective_start = budget.start_date
            
            print(f"Effective Start Date (for calculation): {effective_start}")
            
            # Calculate spent amount using new logic
            spent = db.session.query(func.sum(Expense.amount)).filter(
                Expense.category_id == budget.category_id,
                Expense.transaction_type == 'expense',
                Expense.date >= effective_start
            ).scalar() or 0
            
            print(f"\nTotal Spent (using effective start): GHS {spent:.2f}")
            print(f"Budget Amount: GHS {budget.amount:.2f}")
            print(f"Remaining: GHS {budget.amount - spent:.2f}")
            print(f"Percentage Used: {(spent / budget.amount * 100):.1f}%")
            
            # Show all expenses for this category
            expenses = Expense.query.filter_by(
                category_id=category.id, 
                transaction_type='expense'
            ).order_by(Expense.date.desc()).all()
            
            print(f"\nAll expenses for {category.name}:")
            for exp in expenses:
                included = "✓" if exp.date >= effective_start else "✗"
                print(f"  {included} {exp.date.strftime('%Y-%m-%d')}: GHS {exp.amount:.2f} - {exp.description}")
        else:
            print("No active budget found for this category.")
