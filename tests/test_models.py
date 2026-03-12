"""
Unit tests for SQLAlchemy models.

Tests model creation, relationships, constraints, and business logic.
"""

import pytest
from app.models import (
    User, Wallet, Category, Expense, Budget, 
    RecurringTransaction, Investment, Creditor, Debtor
)


class TestUserModel:
    """Tests for User model."""
    
    def test_create_user(self, app, db):
        """Test user creation with password hashing."""
        with app.app_context():
            user = User(
                email='test@example.com',
                username='testuser',
                first_name='Test',
                last_name='User'
            )
            user.set_password('securepassword123')
            db.session.add(user)
            db.session.commit()
            
            assert user.id is not None
            assert user.email == 'test@example.com'
            assert user.username == 'testuser'
            assert user.password_hash is not None
            assert user.check_password('securepassword123')
            assert not user.check_password('wrongpassword')
    
    def test_user_password_hashing(self, app, db):
        """Test password hashing generates different hashes."""
        with app.app_context():
            user = User(
                email='test@example.com',
                username='testuser'
            )
            user.set_password('password123')
            
            hash1 = user.password_hash
            user.set_password('password123')
            hash2 = user.password_hash
            
            # Same password should produce same hash
            assert hash1 == hash2
            
            # Different password should produce different hash
            user.set_password('different')
            assert user.password_hash != hash1
    
    def test_user_relationships(self, app, db):
        """Test user has relationships with other models."""
        with app.app_context():
            user = User(
                email='test@example.com',
                username='testuser'
            )
            user.set_password('password')
            db.session.add(user)
            db.session.commit()
            
            # Create wallet for user
            wallet = Wallet(
                user_id=user.id,
                name='Test Wallet',
                balance=100.00
            )
            db.session.add(wallet)
            db.session.commit()
            
            assert wallet in user.wallets


class TestWalletModel:
    """Tests for Wallet model."""
    
    def test_create_wallet(self, app, test_user, db):
        """Test wallet creation."""
        with app.app_context():
            wallet = Wallet(
                user_id=test_user.id,
                name='My Wallet',
                balance=500.00,
                currency='USD'
            )
            db.session.add(wallet)
            db.session.commit()
            
            assert wallet.id is not None
            assert wallet.name == 'My Wallet'
            assert wallet.balance == 500.00
            assert wallet.currency == 'USD'
    
    def test_wallet_default_balance(self, app, test_user, db):
        """Test wallet default balance is 0."""
        with app.app_context():
            wallet = Wallet(
                user_id=test_user.id,
                name='Empty Wallet'
            )
            db.session.add(wallet)
            db.session.commit()
            
            assert wallet.balance == 0.0


class TestCategoryModel:
    """Tests for Category model."""
    
    def test_create_category(self, app, test_user, db):
        """Test category creation."""
        with app.app_context():
            category = Category(
                user_id=test_user.id,
                name='Food & Dining',
                icon='🍕',
                is_custom=True
            )
            db.session.add(category)
            db.session.commit()
            
            assert category.id is not None
            assert category.name == 'Food & Dining'
            assert category.icon == '🍕'
            assert category.is_custom is True
    
    def test_default_category(self, app, db):
        """Test creating a default (non-custom) category."""
        with app.app_context():
            category = Category(
                name='General',
                icon='📁',
                is_custom=False
            )
            db.session.add(category)
            db.session.commit()
            
            assert category.user_id is None
            assert category.is_custom is False


class TestExpenseModel:
    """Tests for Expense model."""
    
    def test_create_expense(self, app, test_user, test_wallet, test_category, db):
        """Test expense creation."""
        with app.app_context():
            from datetime import datetime
            
            expense = Expense(
                user_id=test_user.id,
                description='Lunch',
                amount=25.50,
                transaction_type='expense',
                category_id=test_category.id,
                wallet_id=test_wallet.id,
                date=datetime.utcnow()
            )
            db.session.add(expense)
            db.session.commit()
            
            assert expense.id is not None
            assert expense.description == 'Lunch'
            assert expense.amount == 25.50
            assert expense.transaction_type == 'expense'
    
    def test_income_transaction(self, app, test_user, test_wallet, test_category, db):
        """Test income transaction type."""
        with app.app_context():
            from datetime import datetime
            
            income = Expense(
                user_id=test_user.id,
                description='Salary',
                amount=5000.00,
                transaction_type='income',
                category_id=test_category.id,
                wallet_id=test_wallet.id,
                date=datetime.utcnow()
            )
            db.session.add(income)
            db.session.commit()
            
            assert income.transaction_type == 'income'
    
    def test_expense_with_tags(self, app, test_user, test_wallet, test_category, db):
        """Test expense with tags."""
        with app.app_context():
            from datetime import datetime
            
            expense = Expense(
                user_id=test_user.id,
                description='Groceries',
                amount=75.00,
                transaction_type='expense',
                category_id=test_category.id,
                wallet_id=test_wallet.id,
                tags='food,weekly',
                date=datetime.utcnow()
            )
            db.session.add(expense)
            db.session.commit()
            
            assert expense.tags == 'food,weekly'


class TestBudgetModel:
    """Tests for Budget model."""
    
    def test_create_budget(self, app, test_user, test_category, db):
        """Test budget creation."""
        with app.app_context():
            budget = Budget(
                user_id=test_user.id,
                category_id=test_category.id,
                amount=500.00,
                period='monthly'
            )
            db.session.add(budget)
            db.session.commit()
            
            assert budget.id is not None
            assert budget.amount == 500.00
            assert budget.period == 'monthly'
            assert budget.spent == 0.0
    
    def test_budget_periods(self, app, test_user, test_category, db):
        """Test different budget periods."""
        with app.app_context():
            # Weekly budget
            weekly = Budget(
                user_id=test_user.id,
                category_id=test_category.id,
                amount=100.00,
                period='weekly'
            )
            db.session.add(weekly)
            db.session.commit()
            
            assert weekly.period == 'weekly'
            
            # Yearly budget
            yearly = Budget(
                user_id=test_user.id,
                category_id=test_category.id,
                amount=6000.00,
                period='yearly'
            )
            db.session.add(yearly)
            db.session.commit()
            
            assert yearly.period == 'yearly'


class TestInvestmentModel:
    """Tests for Investment model."""
    
    def test_create_investment(self, app, test_user, db):
        """Test investment creation and ROI calculation."""
        with app.app_context():
            from datetime import datetime
            
            investment = Investment(
                user_id=test_user.id,
                name='AAPL Stock',
                investment_type='Stocks',
                amount_invested=1000.00,
                current_value=1200.00,
                purchase_date=datetime.utcnow()
            )
            db.session.add(investment)
            db.session.commit()
            
            assert investment.id is not None
            assert investment.roi == 20.0  # 20% ROI
    
    def test_roi_zero_when_no_investment(self, app, test_user, db):
        """Test ROI is 0 when amount invested is 0."""
        with app.app_context():
            investment = Investment(
                user_id=test_user.id,
                name='New Investment',
                investment_type='Bonds',
                amount_invested=0.00,
                current_value=100.00
            )
            db.session.add(investment)
            db.session.commit()
            
            assert investment.roi == 0
    
    def test_negative_roi(self, app, test_user, db):
        """Test negative ROI calculation."""
        with app.app_context():
            investment = Investment(
                user_id=test_user.id,
                name='Losing Stock',
                investment_type='Stocks',
                amount_invested=1000.00,
                current_value=800.00
            )
            db.session.add(investment)
            db.session.commit()
            
            assert investment.roi == -20.0


class TestCreditorModel:
    """Tests for Creditor model."""
    
    def test_create_creditor(self, app, test_user, db):
        """Test creditor creation."""
        with app.app_context():
            from datetime import datetime
            
            creditor = Creditor(
                user_id=test_user.id,
                name='Bank ABC',
                amount=10000.00,
                interest_rate=5.5,
                debt_type='loan',
                due_date=datetime(2025, 12, 31)
            )
            db.session.add(creditor)
            db.session.commit()
            
            assert creditor.id is not None
            assert creditor.name == 'Bank ABC'
            assert creditor.amount == 10000.00
            assert creditor.status == 'active'


class TestDebtorModel:
    """Tests for Debtor model."""
    
    def test_create_debtor(self, app, test_user, db):
        """Test debtor creation."""
        with app.app_context():
            from datetime import datetime
            
            debtor = Debtor(
                user_id=test_user.id,
                name='John Doe',
                amount=500.00,
                due_date=datetime(2025, 6, 30)
            )
            db.session.add(debtor)
            db.session.commit()
            
            assert debtor.id is not None
            assert debtor.name == 'John Doe'
            assert debtor.amount == 500.00
            assert debtor.status == 'active'
