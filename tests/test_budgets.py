"""
Integration tests for budget CRUD operations.

Tests creating, reading, updating budgets and spending tracking.
"""

import pytest
from datetime import datetime
from app.models import Budget, Expense


class TestBudgetCreation:
    """Tests for budget creation."""

    def test_add_budget_page_loads(self, authenticated_client):
        """Test add budget page loads."""
        response = authenticated_client.get('/budgets/add')
        assert response.status_code == 200

    def test_create_budget_valid_data(self, authenticated_client, app, test_user, test_category, db):
        """Test creating a budget with valid data."""
        with app.app_context():
            response = authenticated_client.post('/budgets/add', data={
                'category': str(test_category.id),
                'amount': '500.00',
                'period': 'monthly'
            }, follow_redirects=True)

            assert response.status_code == 200

    def test_create_budget_different_periods(self, authenticated_client, app, test_user, test_category, db):
        """Test creating budgets with different periods."""
        with app.app_context():
            # Weekly budget
            response = authenticated_client.post('/budgets/add', data={
                'category': str(test_category.id),
                'amount': '100.00',
                'period': 'weekly'
            }, follow_redirects=True)

            assert response.status_code == 200


class TestBudgetReading:
    """Tests for viewing budgets."""

    def test_budgets_page_loads(self, authenticated_client):
        """Test budgets page loads."""
        response = authenticated_client.get('/budgets')
        assert response.status_code == 200

    def test_budgets_list_shows_budgets(self, authenticated_client, app, test_user, test_category, db):
        """Test that budgets are displayed in list."""
        with app.app_context():
            budget = Budget(
                user_id=test_user.id,
                category_id=test_category.id,
                amount=500.00,
                period='monthly',
                start_date=datetime.utcnow()
            )
            db.session.add(budget)
            db.session.commit()

            response = authenticated_client.get('/budgets')
            assert response.status_code == 200


class TestBudgetDelete:
    """Tests for deleting budgets."""

    def test_delete_budget(self, authenticated_client, app, db):
        """Test deleting a budget."""
        with app.app_context():
            from app.models import User, Category
            auth_user = User.query.filter_by(email='authuser@example.com').first()
            category = Category(user_id=auth_user.id, name='DelBudgetCat', icon='💰')
            db.session.add(category)
            db.session.commit()

            budget = Budget(
                user_id=auth_user.id,
                category_id=category.id,
                amount=100.00,
                period='weekly',
                start_date=datetime.utcnow()
            )
            db.session.add(budget)
            db.session.commit()
            budget_id = budget.id

            response = authenticated_client.post(f'/budgets/delete/{budget_id}', follow_redirects=True)
            assert response.status_code == 200

            deleted = Budget.query.get(budget_id)
            assert deleted is None


class TestBudgetSpendingTracking:
    """Tests for budget spending tracking."""

    def test_budget_with_expenses(self, authenticated_client, app, test_user, test_wallet, test_category, db):
        """Test that budgets work alongside expenses."""
        with app.app_context():
            budget = Budget(
                user_id=test_user.id,
                category_id=test_category.id,
                amount=500.00,
                period='monthly',
                start_date=datetime.utcnow()
            )
            db.session.add(budget)
            db.session.commit()

            # Create expense in the budget category
            expense = Expense(
                user_id=test_user.id,
                description='Test',
                amount=100.00,
                transaction_type='expense',
                category_id=test_category.id,
                wallet_id=test_wallet.id
            )
            db.session.add(expense)
            db.session.commit()

            # Budget should still exist and be active
            db.session.refresh(budget)
            assert budget.is_active is True
            assert budget.amount == 500.00

    def test_budget_over_limit_still_active(self, authenticated_client, app, test_user, test_wallet, test_category, db):
        """Test that budget remains active even when over-spent."""
        with app.app_context():
            budget = Budget(
                user_id=test_user.id,
                category_id=test_category.id,
                amount=50.00,
                period='monthly',
                start_date=datetime.utcnow()
            )
            db.session.add(budget)
            db.session.commit()

            # Create expense exceeding budget
            expense = Expense(
                user_id=test_user.id,
                description='Big Expense',
                amount=100.00,
                transaction_type='expense',
                category_id=test_category.id,
                wallet_id=test_wallet.id
            )
            db.session.add(expense)
            db.session.commit()

            db.session.refresh(budget)
            assert budget.is_active is True
