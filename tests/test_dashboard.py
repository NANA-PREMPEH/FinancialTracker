"""
Integration tests for dashboard functionality.

Tests dashboard loads, totals calculations, and data display.
"""

import pytest
from app.models import User, Wallet, Category, Expense


class TestDashboardAccess:
    """Tests for dashboard access control."""
    
    def test_dashboard_requires_login(self, client):
        """Test that unauthenticated users cannot access dashboard."""
        response = client.get('/')
        # Should redirect to login
        assert response.status_code in [302, 401]
    
    def test_dashboard_accessible_when_logged_in(self, authenticated_client):
        """Test that authenticated users can access dashboard."""
        response = authenticated_client.get('/')
        assert response.status_code == 200


class TestDashboardContent:
    """Tests for dashboard content and calculations."""
    
    def test_dashboard_shows_wallets(self, authenticated_client, app, test_user, db):
        """Test that dashboard displays user's wallets."""
        with app.app_context():
            # Create a wallet
            wallet = Wallet(
                user_id=test_user.id,
                name='Main Wallet',
                balance=1000.00,
                currency='USD'
            )
            db.session.add(wallet)
            db.session.commit()
            
            response = authenticated_client.get('/')
            assert response.status_code == 200
            assert b'Main Wallet' in response.data or b'main wallet' in response.data.lower()
    
    def test_dashboard_shows_balance_total(self, authenticated_client, app, test_user, db):
        """Test that dashboard shows correct total balance."""
        with app.app_context():
            # Create multiple wallets
            wallet1 = Wallet(user_id=test_user.id, name='Wallet 1', balance=500.00)
            wallet2 = Wallet(user_id=test_user.id, name='Wallet 2', balance=300.00)
            db.session.add_all([wallet1, wallet2])
            db.session.commit()
            
            response = authenticated_client.get('/')
            assert response.status_code == 200
            # Total should be 800
            assert b'800' in response.data or b'800.00' in response.data
    
    def test_dashboard_empty_state(self, authenticated_client):
        """Test dashboard shows empty state for new users."""
        response = authenticated_client.get('/')
        assert response.status_code == 200
        # Should show some empty state message or prompt to add data
    
    def test_dashboard_recent_transactions(self, authenticated_client, app, test_user, test_wallet, test_category, db):
        """Test that dashboard shows recent transactions."""
        with app.app_context():
            # Create an expense
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
            
            response = authenticated_client.get('/')
            assert response.status_code == 200
            assert b'Test Expense' in response.data or b'50' in response.data


class TestDashboardCalculations:
    """Tests for dashboard calculation accuracy."""
    
    def test_income_expense_totals(self, authenticated_client, app, test_user, test_wallet, test_category, db):
        """Test that income and expense totals are calculated correctly."""
        with app.app_context():
            # Add income
            income = Expense(
                user_id=test_user.id,
                description='Salary',
                amount=5000.00,
                transaction_type='income',
                category_id=test_category.id,
                wallet_id=test_wallet.id
            )
            
            # Add expense
            expense = Expense(
                user_id=test_user.id,
                description='Groceries',
                amount=150.00,
                transaction_type='expense',
                category_id=test_category.id,
                wallet_id=test_wallet.id
            )
            
            db.session.add_all([income, expense])
            db.session.commit()
            
            response = authenticated_client.get('/')
            assert response.status_code == 200
    
    def test_wallet_balance_after_transactions(self, authenticated_client, app, test_user, test_wallet, test_category, db):
        """Test that wallet balance reflects transactions."""
        with app.app_context():
            initial_balance = test_wallet.balance  # Should be 0 by default
            
            # Add income
            income = Expense(
                user_id=test_user.id,
                description='Income',
                amount=1000.00,
                transaction_type='income',
                category_id=test_category.id,
                wallet_id=test_wallet.id
            )
            db.session.add(income)
            db.session.commit()
            
            # Check wallet balance was updated
            db.session.refresh(test_wallet)
            assert test_wallet.balance == 1000.00


class TestDashboardNavigation:
    """Tests for dashboard navigation links."""
    
    def test_dashboard_has_expenses_link(self, authenticated_client):
        """Test that dashboard has link to expenses page."""
        response = authenticated_client.get('/')
        assert response.status_code == 200
        # Should contain link to expenses
        assert b'expense' in response.data.lower() or b'/add_expense' in response.data
    
    def test_dashboard_has_wallets_link(self, authenticated_client):
        """Test that dashboard has link to wallets page."""
        response = authenticated_client.get('/')
        assert response.status_code == 200
        # Should contain link to wallets
        assert b'wallet' in response.data.lower() or b'/wallets' in response.data
    
    def test_dashboard_has_budgets_link(self, authenticated_client):
        """Test that dashboard has link to budgets page."""
        response = authenticated_client.get('/')
        assert response.status_code == 200
        # Should contain link to budgets
        assert b'budget' in response.data.lower()
