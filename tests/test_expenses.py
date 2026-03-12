"""
Integration tests for expense CRUD operations.

Tests creating, reading, updating, and deleting expenses.
"""

import pytest
from app.models import Expense, Wallet, Category


class TestExpenseCreation:
    """Tests for expense creation."""
    
    def test_add_expense_page_loads(self, authenticated_client):
        """Test add expense page loads."""
        response = authenticated_client.get('/add_expense')
        assert response.status_code == 200
    
    def test_create_expense_valid_data(self, authenticated_client, app, test_user, test_wallet, test_category, db):
        """Test creating an expense with valid data."""
        with app.app_context():
            response = authenticated_client.post('/add_expense', data={
                'description': 'Lunch',
                'amount': '25.50',
                'category_id': str(test_category.id),
                'wallet_id': str(test_wallet.id),
                'transaction_type': 'expense'
            }, follow_redirects=True)
            
            assert response.status_code == 200
    
    def test_create_expense_updates_wallet_balance(self, authenticated_client, app, test_user, test_wallet, test_category, db):
        """Test that creating an expense updates wallet balance."""
        with app.app_context():
            initial_balance = test_wallet.balance
            
            authenticated_client.post('/add_expense', data={
                'description': 'Test Expense',
                'amount': '50.00',
                'category_id': str(test_category.id),
                'wallet_id': str(test_wallet.id),
                'transaction_type': 'expense'
            })
            
            db.session.refresh(test_wallet)
            assert test_wallet.balance == initial_balance - 50.00
    
    def test_create_income_updates_wallet_balance(self, authenticated_client, app, test_user, test_wallet, test_category, db):
        """Test that creating income updates wallet balance."""
        with app.app_context():
            initial_balance = test_wallet.balance
            
            authenticated_client.post('/add_expense', data={
                'description': 'Salary',
                'amount': '1000.00',
                'category_id': str(test_category.id),
                'wallet_id': str(test_wallet.id),
                'transaction_type': 'income'
            })
            
            db.session.refresh(test_wallet)
            assert test_wallet.balance == initial_balance + 1000.00
    
    def test_create_expense_missing_required_fields(self, authenticated_client):
        """Test creating expense with missing required fields."""
        response = authenticated_client.post('/add_expense', data={
            'description': 'Test'
        })
        
        # Should show validation error
        assert response.status_code == 200


class TestExpenseReading:
    """Tests for viewing expenses."""
    
    def test_all_expenses_page_loads(self, authenticated_client):
        """Test all expenses page loads."""
        response = authenticated_client.get('/all_expenses')
        assert response.status_code == 200
    
    def test_expenses_list_shows_expenses(self, authenticated_client, app, test_user, test_wallet, test_category, db):
        """Test that expenses are displayed in list."""
        with app.app_context():
            expense = Expense(
                user_id=test_user.id,
                description='Test Expense',
                amount=50.00,
                transaction_type='expense',
                category_id=test_category.id,
                wallet_id=test_wallet.id
            )
            db.session.add(expense)
            db.session.commit()
            
            response = authenticated_client.get('/all_expenses')
            assert response.status_code == 200
            data_lower = response.data.lower()
            assert b'test expense' in data_lower or b'50' in data_lower


class TestExpenseUpdate:
    """Tests for updating expenses."""
    
    def test_edit_expense_page_loads(self, authenticated_client, app, test_user, test_wallet, test_category, db):
        """Test edit expense page loads."""
        with app.app_context():
            expense = Expense(
                user_id=test_user.id,
                description='Original',
                amount=50.00,
                transaction_type='expense',
                category_id=test_category.id,
                wallet_id=test_wallet.id
            )
            db.session.add(expense)
            db.session.commit()
            
            response = authenticated_client.get(f'/edit_expense/{expense.id}')
            assert response.status_code == 200
    
    def test_update_expense(self, authenticated_client, app, test_user, test_wallet, test_category, db):
        """Test updating an expense."""
        with app.app_context():
            expense = Expense(
                user_id=test_user.id,
                description='Original',
                amount=50.00,
                transaction_type='expense',
                category_id=test_category.id,
                wallet_id=test_wallet.id
            )
            db.session.add(expense)
            db.session.commit()
            expense_id = expense.id
            
            response = authenticated_client.post(f'/edit_expense/{expense_id}', data={
                'description': 'Updated',
                'amount': '75.00',
                'category_id': str(test_category.id),
                'wallet_id': str(test_wallet.id),
                'transaction_type': 'expense'
            }, follow_redirects=True)
            
            assert response.status_code == 200


class TestExpenseDelete:
    """Tests for deleting expenses."""
    
    def test_delete_expense(self, authenticated_client, app, test_user, test_wallet, test_category, db):
        """Test deleting an expense."""
        with app.app_context():
            expense = Expense(
                user_id=test_user.id,
                description='To Delete',
                amount=50.00,
                transaction_type='expense',
                category_id=test_category.id,
                wallet_id=test_wallet.id
            )
            db.session.add(expense)
            db.session.commit()
            expense_id = expense.id
            
            response = authenticated_client.post(f'/delete_expense/{expense_id}', follow_redirects=True)
            assert response.status_code == 200
            
            deleted = Expense.query.get(expense_id)
            assert deleted is None
    
    def test_delete_expense_restores_wallet_balance(self, authenticated_client, app, test_user, test_wallet, test_category, db):
        """Test that deleting an expense restores wallet balance."""
        with app.app_context():
            initial_balance = test_wallet.balance
            
            expense = Expense(
                user_id=test_user.id,
                description='Test',
                amount=50.00,
                transaction_type='expense',
                category_id=test_category.id,
                wallet_id=test_wallet.id
            )
            db.session.add(expense)
            db.session.commit()
            
            db.session.refresh(test_wallet)
            assert test_wallet.balance == initial_balance - 50.00
            
            authenticated_client.post(f'/delete_expense/{expense.id}')
            
            db.session.refresh(test_wallet)
            assert test_wallet.balance == initial_balance
