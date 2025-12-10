
from app import create_app, db
from app.models import Wallet, Creditor
from sqlalchemy import func

app = create_app()

with app.app_context():
    print("Setting up test data...")
    # Clean previous
    Wallet.query.filter_by(name="TestWalletCred").delete()
    Creditor.query.filter_by(name="TestCreditor").delete()
    db.session.commit()
    
    # 1. Create Wallet
    wallet = Wallet(name="TestWalletCred", balance=1000.0, icon="W")
    db.session.add(wallet)
    db.session.commit()
    
    total_wallet = wallet.balance
    print(f"Total Wallet Balance: {total_wallet}")
    
    # 2. Verify Initial Net Balance (Should be 1000)
    creditors = Creditor.query.all()
    total_debt = sum(c.amount for c in creditors)
    net_bal = total_wallet - total_debt # Simplified logic for test (ignoring other real wallets/creditors for delta)
    
    # We need to capture the 'baseline' debt if any exists from real data
    baseline_debt = total_debt
    print(f"Baseline Debt: {baseline_debt}")
    
    # 3. Add Creditor
    print("Adding Creditor (Amount: 200)...")
    creditor = Creditor(name="TestCreditor", amount=200.0)
    db.session.add(creditor)
    db.session.commit()
    
    # 4. Verify New Calculations
    new_creditors = Creditor.query.all()
    new_total_debt = sum(c.amount for c in new_creditors)
    print(f"New Total Debt: {new_total_debt}")
    
    expected_debt = baseline_debt + 200.0
    
    try:
        assert abs(new_total_debt - expected_debt) < 0.01
        print("SUCCESS: Debt increased correctly.")
    except AssertionError:
        print(f"FAILURE: Expected debt {expected_debt}, got {new_total_debt}")
        
    # 5. Check Dashboard Logic (Net Balance)
    # For this test, assume we only care about the delta impact
    # Impact on Net Balance should be -200
    
    # Cleanup
    db.session.delete(wallet)
    db.session.delete(creditor)
    db.session.commit()
    print("Cleanup done.")
