
from app import create_app, db
from app.models import Wallet, Expense, Category

app = create_app()

with app.app_context():
    # Setup
    print("Setting up test data...")
    # Using safe icons to avoid potential DB charset issues (utf8 vs utf8mb4)
    wallet_a = Wallet(name="Test Wallet A", balance=1000.0, currency="GHS", icon="W")
    wallet_b = Wallet(name="Test Wallet B", balance=0.0, currency="GHS", icon="W")
    db.session.add(wallet_a)
    db.session.add(wallet_b)
    db.session.commit()
    
    id_a = wallet_a.id
    id_b = wallet_b.id
    
    print(f"Initial: Wallet A: {wallet_a.balance}, Wallet B: {wallet_b.balance}")
    
    # Simulate Transfer Logic (replicating route logic)
    print("Simulating transfer of 500 GHS from A to B...")
    transfer_amount = 500.0
    
    # Get Transfer Category
    cat = Category.query.filter_by(name='Transfer').first()
    if not cat:
        # Use safe icon
        cat = Category(name='Transfer', icon='T', is_custom=False)
        db.session.add(cat)
        db.session.commit()
    else:
        # ensure it is attached to session
        cat = db.session.merge(cat)
        
    # Create Expenses
    exp = Expense(amount=transfer_amount, description=f"Transfer to {wallet_b.name}", category_id=cat.id, wallet_id=id_a, transaction_type='expense', tags='transfer')
    inc = Expense(amount=transfer_amount, description=f"Transfer from {wallet_a.name}", category_id=cat.id, wallet_id=id_b, transaction_type='income', tags='transfer')
    
    db.session.add(exp)
    db.session.add(inc)
    
    # Update Balances
    wallet_a.balance -= transfer_amount
    wallet_b.balance += transfer_amount
    db.session.commit()
    
    # Verification
    # Reload from DB
    db.session.expire_all()
    wallet_a = Wallet.query.get(id_a)
    wallet_b = Wallet.query.get(id_b)
    
    print(f"Final: Wallet A: {wallet_a.balance}, Wallet B: {wallet_b.balance}")
    
    try:
        assert wallet_a.balance == 500.0
        assert wallet_b.balance == 500.0
        print("SUCCESS: Balances updated correctly.")
    except AssertionError as e:
        print(f"FAILURE: {e}")
    
    # Cleanup
    print("Cleaning up test data...")
    # Delete expenses first to avoid foreign key/nullability issues
    db.session.query(Expense).filter(Expense.wallet_id == id_a).delete()
    db.session.query(Expense).filter(Expense.wallet_id == id_b).delete()
    
    # Now delete wallets
    # We need to re-fetch or merge if they were expired, but delete(obj) works on attached objects.
    # Since we called expire_all(), we should re-query them to be safe or use filter delete.
    Wallet.query.filter_by(id=id_a).delete()
    Wallet.query.filter_by(id=id_b).delete()
    
    db.session.commit()
    print("Cleanup complete.")
