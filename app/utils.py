
from . import db
from .models import ExchangeRate
from datetime import datetime
import requests

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
