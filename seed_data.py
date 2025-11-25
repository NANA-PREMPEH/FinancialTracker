from app import create_app, db
from app.models import Expense, Category
from datetime import datetime, timedelta
from run import init_db
import random

app = create_app()

def seed():
    with app.app_context():
        # Initialize DB and categories
        init_db()
        
        categories = Category.query.all()

        print("Seeding expenses...")
        
        # Add expenses for different periods
        # Today
        db.session.add(Expense(amount=50.00, description="Lunch", category=categories[0], date=datetime.utcnow()))
        
        # Yesterday
        db.session.add(Expense(amount=20.00, description="Bus fare", category=categories[1], date=datetime.utcnow() - timedelta(days=1)))
        
        # Last Week
        db.session.add(Expense(amount=150.00, description="Groceries", category=categories[0], date=datetime.utcnow() - timedelta(days=5)))
        
        # Last Month
        db.session.add(Expense(amount=300.00, description="Electricity Bill", category=categories[2], date=datetime.utcnow() - timedelta(days=20)))
        
        # Last Quarter
        db.session.add(Expense(amount=500.00, description="Car Service", category=categories[1], date=datetime.utcnow() - timedelta(days=80)))

        db.session.commit()
        print("Seeding complete!")

if __name__ == '__main__':
    seed()
