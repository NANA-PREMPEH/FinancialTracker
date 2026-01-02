
from app import create_app, db
from app.models import Wallet, Creditor, Expense, Category
from datetime import datetime

app = create_app()

with app.app_context():
    print("Setting up test data...")
    # Clean previous
    Wallet.query.filter_by(name="TestWalletPay").delete()
    Creditor.query.filter_by(name="TestCreditorPay").delete()
    db.session.commit()
    
    # 1. Create Wallet and Creditor
    wallet = Wallet(name="TestWalletPay", balance=1000.0, icon="W")
    creditor = Creditor(name="TestCreditorPay", amount=500.0)
    db.session.add(wallet)
    db.session.add(creditor)
    db.session.commit()
    
    print(f"Initial: API Owe {creditor.amount}, Wallet Has {wallet.balance}")
    
    # 2. Simulate Payment Logic (Directly test logic used in route)
    amount_to_pay = 200.0
    
    wallet.balance -= amount_to_pay
    creditor.amount -= amount_to_pay
    
    debt_cat = Category.query.filter_by(name='Debt Payment').first()
    if not debt_cat:
        debt_cat = Category(name='Debt Payment', icon='D', is_custom=False)
        db.session.add(debt_cat)
        db.session.commit()
        
    expense = Expense(
        amount=amount_to_pay,
        description=f"Payment to {creditor.name}",
        category_id=debt_cat.id,
        wallet_id=wallet.id,
        date=datetime.now(),
        transaction_type='expense',
        tags='debt_payment'
    )
    db.session.add(expense)
    db.session.commit()
    
    print("Payment Simulated.")
    
    # 3. Verify
    new_balance = wallet.balance
    new_debt = creditor.amount
    
    print(f"Final: Creditor Owe {new_debt}, Wallet Has {new_balance}")
    
    try:
        assert new_balance == 800.0
        assert new_debt == 300.0
        print("SUCCESS: Balances updated correctly.")
    except AssertionError:
        print("FAILURE: Balances incorrect.")
        
    last_expense = Expense.query.order_by(Expense.id.desc()).first()
    try:
        assert last_expense.amount == 200.0
        assert last_expense.category.name == 'Debt Payment'
        print("SUCCESS: Expense record created.")
    except AssertionError:
        print("FAILURE: Expense record incorrect.")

    # Cleanup
    db.session.delete(wallet)
    db.session.delete(creditor)
    db.session.delete(last_expense)
    db.session.commit()
    print("Cleanup done.")
