
import requests
from app import create_app, db
from app.models import Expense, Wallet, Category, ExchangeRate

app = create_app()

with app.app_context():
    print("Verifying Database Schema...")
    # 1. Verify Columns Exist
    try:
        # Quick check by creating an object
        e = Expense(amount=10, description="Test", category_id=1, wallet_id=1,
                    original_amount=10, original_currency='USD')
        print("Expense model supports new columns.")
    except Exception as e:
        print(f"FAILED: Expense model error: {e}")

    print("\nVerifying Exchange Rate Logic...")
    # 2. Test get_exchange_rate (via direct usage or mocking)
    # We'll just check if we can query ExchangeRate
    count = ExchangeRate.query.count()
    print(f"ExchangeRate table has {count} entries.")

    print("\nVerifying Data Persistence...")
    # 3. Create a dummy expense with currency
    try:
        # Ensure we have a wallet and category
        w = Wallet.query.first()
        c = Category.query.first()
        if not w or not c:
            print("No wallet or category found to test with.")
        else:
            # Simulate adding 10 USD to a GHS wallet
            original_amount = 10
            original_currency = 'USD'
            
            # Create a fake rate for testing if not exists
            rate = ExchangeRate.query.filter_by(from_currency='USD', to_currency='GHS').first()
            if not rate:
                conversion_rate = 15.0 # Example
            else:
                conversion_rate = rate.rate
            
            converted_amount = original_amount * conversion_rate
            
            e = Expense(
                amount=converted_amount,
                description="Test Currency",
                category_id=c.id,
                wallet_id=w.id,
                transaction_type='expense',
                original_amount=original_amount,
                original_currency=original_currency
            )
            db.session.add(e)
            db.session.commit()
            
            # Read it back
            saved_e = Expense.query.get(e.id)
            print(f"Saved Expense ID: {saved_e.id}")
            print(f"Original: {saved_e.original_amount} {saved_e.original_currency}")
            print(f"Converted: {saved_e.amount} (Rate approx {saved_e.amount/saved_e.original_amount})")
            
            # Clean up
            db.session.delete(saved_e)
            db.session.commit()
            print("Test Expense deleted.")
            
    except Exception as e:
        print(f"FAILED: DB Persistence Error: {e}")
