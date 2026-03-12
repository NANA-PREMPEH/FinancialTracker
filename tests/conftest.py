"""
Pytest configuration and fixtures for FinancialTracker tests.

Provides:
- Flask test client
- Test database setup (SQLite in-memory)
- Authentication fixtures
- Common test utilities
"""

import pytest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(scope='session')
def app():
    """Create and configure a test Flask application."""
    from app import create_app
    from app.config import TestingConfig
    
    app = create_app(TestingConfig)
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    
    return app


@pytest.fixture(scope='function')
def client(app):
    """Create a test client for the Flask application."""
    return app.test_client()


@pytest.fixture(scope='function')
def db(app):
    """Create a fresh database for each test."""
    from app import db as db_instance
    
    with app.app_context():
        db_instance.create_all()
        yield db_instance
        db_instance.session.remove()
        db_instance.drop_all()


@pytest.fixture(scope='function')
def session(db):
    """Provide a database session for tests."""
    return db.session


@pytest.fixture
def authenticated_client(client, app):
    """Create an authenticated test client with a logged-in user."""
    from app.models import User
    from app import db
    
    with app.app_context():
        # Create test user
        user = User(
            email='test@example.com',
            username='testuser',
            first_name='Test',
            last_name='User'
        )
        user.set_password('testpassword123')
        db.session.add(user)
        db.session.commit()
        
        # Login the user
        with client.session_transaction() as sess:
            sess['_user_id'] = str(user.id)
            sess['_fresh'] = True
        
        return client


@pytest.fixture
def test_user(app, db):
    """Create a test user and return it."""
    from app.models import User
    
    with app.app_context():
        user = User(
            email='test@example.com',
            username='testuser',
            first_name='Test',
            last_name='User'
        )
        user.set_password('testpassword123')
        db.session.add(user)
        db.session.commit()
        
        # Refresh to get the ID
        db.session.refresh(user)
        
        return user


@pytest.fixture
def test_wallet(app, test_user):
    """Create a test wallet for the test user."""
    from app.models import Wallet
    
    with app.app_context():
        wallet = Wallet(
            user_id=test_user.id,
            name='Test Wallet',
            balance=1000.00,
            currency='USD'
        )
        app.db.session.add(wallet)
        app.db.session.commit()
        
        return wallet


@pytest.fixture
def test_category(app, test_user):
    """Create a test category for the test user."""
    from app.models import Category
    
    with app.app_context():
        category = Category(
            user_id=test_user.id,
            name='Test Category',
            icon='💰',
            is_custom=True
        )
        app.db.session.add(category)
        app.db.session.commit()
        
        return category


@pytest.fixture
def test_expense(app, test_user, test_wallet, test_category):
    """Create a test expense."""
    from app.models import Expense
    from datetime import datetime
    
    with app.app_context():
        expense = Expense(
            user_id=test_user.id,
            description='Test Expense',
            amount=50.00,
            transaction_type='expense',
            category_id=test_category.id,
            wallet_id=test_wallet.id,
            date=datetime.utcnow()
        )
        app.db.session.add(expense)
        app.db.session.commit()
        
        return expense


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "unit: mark test as unit test")
    config.addinivalue_line("markers", "slow: mark test as slow running")
