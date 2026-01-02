
from app import create_app, db
from app.models import Expense
app = create_app()

with app.app_context():
    # Test Query (Logic from routes.py)
    print("Testing history query...")
    # Logic: Expense.query.filter(Expense.tags.like('%debt_payment%')).order_by(Expense.date.desc()).all()
    
    payment_history = Expense.query.filter(Expense.tags.like('%debt_payment%')).order_by(Expense.date.desc()).limit(5).all()
            
    print(f"Found {len(payment_history)} payment records.")
    
    if payment_history:
        last = payment_history[0]
        print(f"Most Recent: {last.date} - {last.description} - {last.amount}")
        assert 'debt_payment' in last.tags
        print("SUCCESS: Retrieved record has correct tag.")
    else:
        print("WARNING: No history found (Did you run verify_payment.py?)")
        
    print("Done.")
