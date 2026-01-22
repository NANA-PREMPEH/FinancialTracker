
from app import create_app, db
from app.models import Wallet, Creditor, ExchangeRate
from datetime import datetime

app = create_app()

with app.app_context():
    print("Debugging Dashboard Values...")
    
    # 1. Replicate Total Wallet Balance Logic from routes.py
    wallets = Wallet.query.all()
    total_wallet_balance = 0.0
    
    print("\n--- Wallet Breakdown ---")
    for wallet in wallets:
        if wallet.currency == 'GHS':
            print(f"Wallet: {wallet.name} | {wallet.currency} {wallet.balance} -> GHS {wallet.balance}")
            total_wallet_balance += wallet.balance
        else:
            # Replicate rate fetching
            rate = ExchangeRate.query.filter_by(
                from_currency=wallet.currency, 
                to_currency='GHS'
            ).order_by(ExchangeRate.date.desc()).first()
            
            # Simplified for debug: use rate if exists, else 0 (or fetch? Dashboard fetches)
            # We won't make API calls here to keep it fast, just assume DB has rates or warn
            if rate:
                converted = wallet.balance * rate.rate
                print(f"Wallet: {wallet.name} | {wallet.currency} {wallet.balance} (Rate: {rate.rate}) -> GHS {converted}")
                total_wallet_balance += converted
            else:
                 print(f"Wallet: {wallet.name} | {wallet.currency} {wallet.balance} (NO RATE FOUND) -> GHS 0?")
                 # Dashboard makes API call here. If we miss this, our number will be low.
    
    print(f"Calculated Total Wallet Balance: {total_wallet_balance}")
    
    # 2. Total Debt
    creditors = Creditor.query.all()
    print("\n--- Creditor Breakdown ---")
    total_debt = 0.0
    for c in creditors:
         # Assuming Creditors are GHS for now as per model default
         print(f"Creditor: {c.name} | {c.amount}")
         total_debt += c.amount
         
    print(f"Calculated Total Debt: {total_debt}")
    
    # 3. Net
    net_bal = total_wallet_balance - total_debt
    print(f"\nResult Net Available: {net_bal}")
