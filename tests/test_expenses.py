"""
Integration tests for expense CRUD operations.

Tests creating, reading, updating, and deleting expenses.
"""

import pytest
from app.models import Expense, Wallet, Category, User


class TestExpenseCreation:
    """Tests for expense creation."""

    def test_add_expense_page_loads(self, authenticated_client):
        """Test add expense page loads."""
        response = authenticated_client.get('/add')
        assert response.status_code == 200

    def test_create_expense_valid_data(self, authenticated_client, app, db):
        """Test creating an expense with valid data."""
        with app.app_context():
            auth_user = User.query.filter_by(email='authuser@example.com').first()
            wallet = Wallet(user_id=auth_user.id, name='Expense Wallet', balance=1000.00, currency='USD')
            category = Category(user_id=auth_user.id, name='Food', icon='🍔')
            db.session.add_all([wallet, category])
            db.session.commit()

            response = authenticated_client.post('/add', data={
                'description': 'Lunch',
                'amount': '25.50',
                'category': str(category.id),
                'wallet': str(wallet.id),
                'transaction_type': 'expense'
            }, follow_redirects=True)

            assert response.status_code == 200

    def test_create_expense_updates_wallet_balance(self, authenticated_client, app, db):
        """Test that creating an expense updates wallet balance."""
        with app.app_context():
            auth_user = User.query.filter_by(email='authuser@example.com').first()
            wallet = Wallet(user_id=auth_user.id, name='Balance Wallet', balance=1000.00, currency='USD')
            category = Category(user_id=auth_user.id, name='TestCat', icon='💰')
            db.session.add_all([wallet, category])
            db.session.commit()
            wallet_id = wallet.id

            authenticated_client.post('/add', data={
                'description': 'Test Expense',
                'amount': '50.00',
                'category': str(category.id),
                'wallet': str(wallet.id),
                'transaction_type': 'expense',
                'currency': 'USD'
            })

            updated_wallet = Wallet.query.get(wallet_id)
            assert updated_wallet.balance == 950.00

    def test_create_income_updates_wallet_balance(self, authenticated_client, app, db):
        """Test that creating income updates wallet balance."""
        with app.app_context():
            auth_user = User.query.filter_by(email='authuser@example.com').first()
            wallet = Wallet(user_id=auth_user.id, name='Income Wallet', balance=1000.00, currency='USD')
            category = Category(user_id=auth_user.id, name='Salary Cat', icon='💰')
            db.session.add_all([wallet, category])
            db.session.commit()
            wallet_id = wallet.id

            authenticated_client.post('/add', data={
                'description': 'Salary',
                'amount': '1000.00',
                'category': str(category.id),
                'wallet': str(wallet.id),
                'transaction_type': 'income',
                'currency': 'USD'
            })

            updated_wallet = Wallet.query.get(wallet_id)
            assert updated_wallet.balance == 2000.00

    def test_create_expense_missing_required_fields(self, authenticated_client):
        """Test creating expense with missing required fields."""
        response = authenticated_client.post('/add', data={
            'description': 'Test'
        })

        # Should show validation error or redirect
        assert response.status_code in [200, 302]


class TestExpenseReading:
    """Tests for viewing expenses."""

    def test_all_expenses_page_loads(self, authenticated_client):
        """Test all expenses page loads."""
        response = authenticated_client.get('/expenses')
        assert response.status_code == 200

    def test_expenses_list_shows_expenses(self, authenticated_client, app, db):
        """Test that expenses are displayed in list."""
        with app.app_context():
            auth_user = User.query.filter_by(email='authuser@example.com').first()
            wallet = Wallet(user_id=auth_user.id, name='List Wallet', balance=1000.00, currency='USD')
            category = Category(user_id=auth_user.id, name='ListCat', icon='💰')
            db.session.add_all([wallet, category])
            db.session.commit()

            expense = Expense(
                user_id=auth_user.id,
                description='Test Expense',
                amount=50.00,
                transaction_type='expense',
                category_id=category.id,
                wallet_id=wallet.id
            )
            db.session.add(expense)
            db.session.commit()

            response = authenticated_client.get('/expenses')
            assert response.status_code == 200


class TestExpenseUpdate:
    """Tests for updating expenses."""

    def test_edit_expense_page_loads(self, authenticated_client, app, db):
        """Test edit expense page loads."""
        with app.app_context():
            auth_user = User.query.filter_by(email='authuser@example.com').first()
            wallet = Wallet(user_id=auth_user.id, name='Edit Wallet', balance=1000.00, currency='USD')
            category = Category(user_id=auth_user.id, name='EditCat', icon='💰')
            db.session.add_all([wallet, category])
            db.session.commit()

            expense = Expense(
                user_id=auth_user.id,
                description='Original',
                amount=50.00,
                transaction_type='expense',
                category_id=category.id,
                wallet_id=wallet.id
            )
            db.session.add(expense)
            db.session.commit()

            response = authenticated_client.get(f'/edit/{expense.id}')
            assert response.status_code == 200

    def test_update_expense(self, authenticated_client, app, db):
        """Test updating an expense."""
        with app.app_context():
            auth_user = User.query.filter_by(email='authuser@example.com').first()
            wallet = Wallet(user_id=auth_user.id, name='Update Wallet', balance=1000.00, currency='USD')
            category = Category(user_id=auth_user.id, name='UpdateCat', icon='💰')
            db.session.add_all([wallet, category])
            db.session.commit()

            expense = Expense(
                user_id=auth_user.id,
                description='Original',
                amount=50.00,
                transaction_type='expense',
                category_id=category.id,
                wallet_id=wallet.id
            )
            db.session.add(expense)
            db.session.commit()
            expense_id = expense.id

            response = authenticated_client.post(f'/edit/{expense_id}', data={
                'description': 'Updated',
                'amount': '75.00',
                'category': str(category.id),
                'wallet': str(wallet.id),
                'transaction_type': 'expense'
            }, follow_redirects=True)

            assert response.status_code == 200


class TestExpenseDelete:
    """Tests for deleting expenses."""

    def test_delete_expense(self, authenticated_client, app, db):
        """Test deleting an expense."""
        with app.app_context():
            auth_user = User.query.filter_by(email='authuser@example.com').first()
            wallet = Wallet(user_id=auth_user.id, name='Del Wallet', balance=1000.00, currency='USD')
            category = Category(user_id=auth_user.id, name='DelCat', icon='💰')
            db.session.add_all([wallet, category])
            db.session.commit()

            expense = Expense(
                user_id=auth_user.id,
                description='To Delete',
                amount=50.00,
                transaction_type='expense',
                category_id=category.id,
                wallet_id=wallet.id
            )
            db.session.add(expense)
            db.session.commit()
            expense_id = expense.id

            response = authenticated_client.post(f'/delete/{expense_id}', follow_redirects=True)
            assert response.status_code == 200

            deleted = Expense.query.get(expense_id)
            assert deleted is None

    def test_delete_expense_restores_wallet_balance(self, authenticated_client, app, db):
        """Test that deleting an expense restores wallet balance."""
        with app.app_context():
            auth_user = User.query.filter_by(email='authuser@example.com').first()
            wallet = Wallet(user_id=auth_user.id, name='Restore Wallet', balance=1000.00, currency='USD')
            category = Category(user_id=auth_user.id, name='RestoreCat', icon='💰')
            db.session.add_all([wallet, category])
            db.session.commit()
            wallet_id = wallet.id
            cat_id = category.id

            # Create expense through the route so balance is properly deducted
            authenticated_client.post('/add', data={
                'description': 'Test Expense',
                'amount': '50.00',
                'category': str(cat_id),
                'wallet': str(wallet_id),
                'transaction_type': 'expense',
                'currency': 'USD'
            })

            # Verify balance was deducted
            w = Wallet.query.get(wallet_id)
            assert w.balance == 950.00

            # Find the expense that was created
            expense = Expense.query.filter_by(user_id=auth_user.id, description='Test Expense').first()
            assert expense is not None

            # Delete the expense
            authenticated_client.post(f'/delete/{expense.id}')

            restored_wallet = Wallet.query.get(wallet_id)
            assert restored_wallet.balance == 1000.00
