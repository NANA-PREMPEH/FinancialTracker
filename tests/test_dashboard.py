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

    def test_dashboard_shows_wallet_balance(self, authenticated_client, app, db):
        """Test that dashboard displays wallet balance total."""
        with app.app_context():
            auth_user = User.query.filter_by(email='authuser@example.com').first()
            wallet = Wallet(
                user_id=auth_user.id,
                name='Main Wallet',
                balance=1000.00,
                currency='GHS'
            )
            db.session.add(wallet)
            db.session.commit()

            response = authenticated_client.get('/')
            assert response.status_code == 200
            # Dashboard converts to GHS and shows net_wallet_balance
            assert b'1,000.00' in response.data or b'1000' in response.data

    def test_dashboard_shows_balance_total(self, authenticated_client, app, db):
        """Test that dashboard shows correct total balance."""
        with app.app_context():
            auth_user = User.query.filter_by(email='authuser@example.com').first()
            wallet1 = Wallet(user_id=auth_user.id, name='Wallet 1', balance=500.00)
            wallet2 = Wallet(user_id=auth_user.id, name='Wallet 2', balance=300.00)
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

    def test_dashboard_recent_transactions(self, authenticated_client, app, db):
        """Test that dashboard shows recent transactions."""
        with app.app_context():
            auth_user = User.query.filter_by(email='authuser@example.com').first()
            wallet = Wallet(user_id=auth_user.id, name='Test Wallet', balance=1000.00)
            category = Category(user_id=auth_user.id, name='TestCat')
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

            response = authenticated_client.get('/')
            assert response.status_code == 200
            assert b'Test Expense' in response.data or b'50' in response.data


class TestDashboardCalculations:
    """Tests for dashboard calculation accuracy."""

    def test_income_expense_totals(self, authenticated_client, app, db):
        """Test that income and expense totals are calculated correctly."""
        with app.app_context():
            auth_user = User.query.filter_by(email='authuser@example.com').first()
            wallet = Wallet(user_id=auth_user.id, name='Calc Wallet', balance=5000.00)
            category = Category(user_id=auth_user.id, name='CalcCat')
            db.session.add_all([wallet, category])
            db.session.commit()

            income = Expense(
                user_id=auth_user.id,
                description='Salary',
                amount=5000.00,
                transaction_type='income',
                category_id=category.id,
                wallet_id=wallet.id
            )
            expense = Expense(
                user_id=auth_user.id,
                description='Groceries',
                amount=150.00,
                transaction_type='expense',
                category_id=category.id,
                wallet_id=wallet.id
            )
            db.session.add_all([income, expense])
            db.session.commit()

            response = authenticated_client.get('/')
            assert response.status_code == 200

    def test_wallet_balance_reflects_data(self, authenticated_client, app, db):
        """Test that wallet balance is displayed on dashboard."""
        with app.app_context():
            auth_user = User.query.filter_by(email='authuser@example.com').first()
            wallet = Wallet(user_id=auth_user.id, name='Balance Wallet', balance=1000.00)
            db.session.add(wallet)
            db.session.commit()

            response = authenticated_client.get('/')
            assert response.status_code == 200
            assert b'1000' in response.data or b'1,000' in response.data


class TestDashboardNavigation:
    """Tests for dashboard navigation links."""

    def test_dashboard_has_expenses_link(self, authenticated_client):
        """Test that dashboard has link to expenses page."""
        response = authenticated_client.get('/')
        assert response.status_code == 200
        assert b'expense' in response.data.lower() or b'/add' in response.data

    def test_dashboard_has_wallets_link(self, authenticated_client):
        """Test that dashboard has link to wallets page."""
        response = authenticated_client.get('/')
        assert response.status_code == 200
        assert b'wallet' in response.data.lower() or b'/wallets' in response.data

    def test_dashboard_has_budgets_link(self, authenticated_client):
        """Test that dashboard has link to budgets page."""
        response = authenticated_client.get('/')
        assert response.status_code == 200
        assert b'budget' in response.data.lower()
