from decimal import Decimal
from datetime import datetime

from . import db
from .models import ExchangeRate, Wallet, Category
import requests


WALLET_OUTFLOW_TRANSACTION_TYPES = {'expense', 'transfer', 'transfer_out'}
WALLET_INFLOW_TRANSACTION_TYPES = {'income', 'liability', 'debt_recovery', 'transfer_in'}


def to_float(value, default=0.0):
    """Normalize DB numerics such as Decimal/None into a plain float."""
    if value is None:
        return default
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def wallet_balance_delta(transaction_type, amount):
    """Return the signed wallet delta for applying a transaction."""
    normalized_type = (transaction_type or '').strip().lower()
    numeric_amount = to_float(amount)

    if normalized_type in WALLET_OUTFLOW_TRANSACTION_TYPES:
        return -numeric_amount
    if normalized_type in WALLET_INFLOW_TRANSACTION_TYPES:
        return numeric_amount
    return 0.0


def apply_transaction_to_wallet(wallet, transaction_type, amount, reverse=False):
    """Apply or reverse a transaction's wallet effect in place."""
    if wallet is None:
        return 0.0

    delta = wallet_balance_delta(transaction_type, amount)
    if reverse:
        delta = -delta

    wallet.balance = to_float(wallet.balance) + delta
    return delta


def get_exchange_rate(from_currency, to_currency='GHS'):
    if from_currency == to_currency:
        return 1.0
        
    # Get exchange rate from DB
    rate = ExchangeRate.query.filter_by(
        from_currency=from_currency, 
        to_currency=to_currency
    ).order_by(ExchangeRate.date.desc()).first()
    
    # If rate exists and is recent (e.g., within 24 hours), use it
    if rate and (datetime.utcnow() - rate.date).days < 1:
        return rate.rate
    
    # Otherwise fetch new rate
    try:
        api_url = f'https://api.exchangerate-api.com/v4/latest/{from_currency}'
        response = requests.get(api_url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            current_rate = data.get('rates', {}).get(to_currency, 0)
            
            if current_rate > 0:
                # Save new rate
                new_rate = ExchangeRate(
                    from_currency=from_currency,
                    to_currency=to_currency,
                    rate=current_rate
                )
                db.session.add(new_rate)
                db.session.commit()
                return current_rate
    except Exception as e:
        print(f"Error fetching rate fo {from_currency}: {e}")
    
    # Fallback to last known rate if available
    if rate:
        return rate.rate
        
    return 1.0 # Default fallback if nothing works

def initialize_user_data(user):
    """Create default wallet and categories for a new user."""
    # 1. Create default 'Cash' wallet
    if not any(w.name == 'Cash' for w in user.wallets):
        default_wallet = Wallet(
            name='Cash', 
            balance=0.0, 
            icon='💵', 
            wallet_type='cash',
            user_id=user.id
        )
        db.session.add(default_wallet)
    
    # 2. Create default categories
    if not user.categories:
        default_categories = [
            ('Food & Drink', '🍽️'),
            ('Transport', '🚗'),
            ('Utilities', '💡'),
            ('Entertainment', '🎬'),
            ('Health', '🏥'),
            ('Shopping', '🛍️'),
            ('Work', '👔'),
            ('Travel', '✈️'),
            ('Gifts', '🎁'),
            ('Home', '🏠'),
            ('Salary', '💵'),
            ('Allowance', '💰'),
            ('Transfer', '↔️'),
            ('Other', '📝')
        ]
        for cat_name, icon in default_categories:
            db.session.add(Category(
                name=cat_name, 
                icon=icon, 
                user_id=user.id,
                is_custom=False
            ))
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error initializing user data: {e}")
