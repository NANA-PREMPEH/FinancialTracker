
from app import create_app, db
from app.models import Wallet, Expense, Category
from datetime import datetime

app = create_app()

with app.app_context():
    # Setup
    print("Setting up test data...")
    # Safe icons
    wallet_a = Wallet(name="History Wallet A", balance=1000.0, currency="GHS", icon="W")
    wallet_b = Wallet(name="History Wallet B", balance=0.0, currency="GHS", icon="W")
    db.session.add(wallet_a)
    db.session.add(wallet_b)
    db.session.commit()
    
    # Ensure Transfer Category
    cat = Category.query.filter_by(name='Transfer').first()
    if not cat:
        cat = Category(name='Transfer', icon='T', is_custom=False)
        db.session.add(cat)
        db.session.commit()
    
    # Create a few transfers
    print("Creating mock transfers...")
    expenses = []
    for i in range(3):
        exp = Expense(amount=100.0, description=f"Transfer {i} to B", category_id=cat.id, wallet_id=wallet_a.id, transaction_type='expense', tags='transfer', date=datetime.now())
        inc = Expense(amount=100.0, description=f"Transfer {i} from A", category_id=cat.id, wallet_id=wallet_b.id, transaction_type='income', tags='transfer', date=datetime.now())
        expenses.extend([exp, inc])
        db.session.add(exp)
        db.session.add(inc)
    
    db.session.commit()
    
    # Test Query (Logic from routes.py)
    print("Testing history query...")
    transfer_category = Category.query.filter_by(name='Transfer').first()
    transfers = []
    if transfer_category:
        transfers = Expense.query.filter_by(category_id=transfer_category.id)\
            .order_by(Expense.date.desc())\
            .limit(10).all()
            
    print(f"Found {len(transfers)} transfers.")
    
    try:
        assert len(transfers) >= 6
        print("SUCCESS: Retrieved recent transfers.")
        
        # Check details of one
        t = transfers[0]
        print(f"Sample: {t.date} - {t.description} - {t.amount} - {t.transaction_type}")
        assert t.category.name == 'Transfer'
        
    except AssertionError as e:
        print("FAILURE: Query did not return expected results.")
        
    # Cleanup
    print("Cleaning up...")
    for e in expenses:
        db.session.delete(e)
    # Re-query wallets to attach to session for delete
    w_a = Wallet.query.get(wallet_a.id)
    w_b = Wallet.query.get(wallet_b.id)
    if w_a: db.session.delete(w_a)
    if w_b: db.session.delete(w_b)
    
    db.session.commit()
    print("Done.")
