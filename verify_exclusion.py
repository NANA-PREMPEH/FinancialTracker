
from app import create_app, db
from app.models import Wallet, Expense, Category
from sqlalchemy import func
from datetime import datetime

app = create_app()

with app.app_context():
    print("Setting up test data...")
    # Clean previous test data if any
    
    # Get Transfer ID
    transfer_cat = Category.query.filter_by(name='Transfer').first()
    if not transfer_cat:
        transfer_cat = Category(name='Transfer', icon='T', is_custom=False)
        db.session.add(transfer_cat)
        db.session.commit()
    transfer_id = transfer_cat.id
    
    # Create normal expense category
    food_cat = Category.query.filter_by(name='TestFood').first()
    if not food_cat:
        food_cat = Category(name='TestFood', icon='F', is_custom=True)
        db.session.add(food_cat)
        db.session.commit()
        
    wallet = Wallet.query.first()
    if not wallet:
        wallet = Wallet(name="Test Wallet", balance=1000)
        db.session.add(wallet)
        db.session.commit()
        
    print("Verifying calculations...")
    
    # helper for calc
    def get_total_expenses():
        return db.session.query(func.sum(Expense.amount)).filter(
            Expense.transaction_type == 'expense',
            Expense.category_id != transfer_id
        ).scalar() or 0
        
    initial_total = get_total_expenses()
    print(f"Initial Total: {initial_total}")
        
    # Create 1 Normal Expense
    exp_normal = Expense(amount=100, description="Navel", category_id=food_cat.id, wallet_id=wallet.id, transaction_type='expense')
    db.session.add(exp_normal)
    db.session.commit()
    
    after_normal = get_total_expenses()
    print(f"After Normal (Expected +100): {after_normal}")
    
    # Create 1 Transfer Expense
    exp_transfer = Expense(amount=500, description="Transfer Out", category_id=transfer_id, wallet_id=wallet.id, transaction_type='expense', tags='transfer')
    db.session.add(exp_transfer)
    db.session.commit()
    
    final_total = get_total_expenses()
    print(f"After Transfer (Expected +0): {final_total}")
    
    try:
        # Check delta
        assert (after_normal - initial_total) == 100
        assert (final_total - after_normal) == 0
        print("SUCCESS: Normal expense added to total, Transfer did not.")
    except AssertionError:
        print(f"FAILURE: Normal Delta={after_normal - initial_total}, Transfer Delta={final_total - after_normal}")
        
    # Cleanup
    db.session.delete(exp_normal)
    db.session.delete(exp_transfer)
    if food_cat.name == 'TestFood': db.session.delete(food_cat)
    db.session.commit()
    print("Done.")
