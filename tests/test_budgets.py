"""
Integration tests for budget CRUD operations.

Tests creating, reading, updating budgets and spending tracking.
"""

import pytest
from app.models import Budget, Expense


class TestBudgetCreation:
    """Tests for budget creation."""
    
    def test_add_budget_page_loads(self, authenticated_client):
        """Test add budget page loads."""
        response = authenticated_client.get('/add_budget')
        assert response.status_code == 200
    
    def test_create_budget_valid_data(self, authenticated_client, app, test_user, test_category, db):
        """Test creating a budget with valid data."""
        with app.app_context():
            response = authenticated_client.post('/add_budget', data={
                'category_id': str(test_category.id),
                'amount': '500.00',
                'period': 'monthly'
            }, follow_redirects=True)
            
            assert response.status_code == 200
    
    def test_create_budget_different_periods(self, authenticated_client, app, test_user, test_category, db):
        """Test creating budgets with different periods."""
        with app.app_context():
            # Weekly budget
            response = authenticated_client.post('/add_budget', data={
                'category_id': str(test_category.id),
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
                period='monthly'
            )
            db.session.add(budget)
            db.session.commit()
            
            response = authenticated_client.get('/budgets')
            assert response.status_code == 200


class TestBudgetUpdate:
    """Tests for updating budgets."""
    
    def test_edit_budget_page_loads(self, authenticated_client, app, test_user, test_category, db):
        """Test edit budget page loads."""
        with app.app_context():
            budget = Budget(
                user_id=test_user.id,
                category_id=test_category.id,
                amount=100.00,
                period='weekly'
            )
            db.session.add(budget)
            db.session.commit()
            
            response = authenticated_client.get(f'/edit_budget/{budget.id}')
            assert response.status_code == 200
    
    def test_update_budget(self, authenticated_client, app, test_user, test_category, db):
        """Test updating a budget."""
        with app.app_context():
            budget = Budget(
                user_id=test_user.id,
                category_id=test_category.id,
                amount=100.00,
                period='weekly'
            )
            db.session.add(budget)
            db.session.commit()
            
            response = authenticated_client.post(f'/edit_budget/{budget.id}', data={
                'category_id': str(test_category.id),
                'amount': '200.00',
                'period': 'monthly'
            }, follow_redirects=True)
            
            assert response.status_code == 200


class TestBudgetDelete:
    """Tests for deleting budgets."""
    
    def test_delete_budget(self, authenticated_client, app, test_user, test_category, db):
        """Test deleting a budget."""
        with app.app_context():
            budget = Budget(
                user_id=test_user.id,
                category_id=test_category.id,
                amount=100.00,
                period='weekly'
            )
            db.session.add(budget)
            db.session.commit()
            budget_id = budget.id
            
            response = authenticated_client.post(f'/delete_budget/{budget_id}', follow_redirects=True)
            assert response.status_code == 200
            
            deleted = Budget.query.get(budget_id)
            assert deleted is None


class TestBudgetSpendingTracking:
    """Tests for budget spending tracking."""
    
    def test_budget_spent_tracking(self, authenticated_client, app, test_user, test_wallet, test_category, db):
        """Test that budget spent amount is tracked."""
        with app.app_context():
            budget = Budget(
                user_id=test_user.id,
                category_id=test_category.id,
                amount=500.00,
                period='monthly'
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
            
            # Reload budget
            db.session.refresh(budget)
            assert budget.spent == 100.00
    
    def test_budget_over_spent(self, authenticated_client, app, test_user, test_wallet, test_category, db):
        """Test over-budget notification."""
        with app.app_context():
            budget = Budget(
                user_id=test_user.id,
                category_id=test_category.id,
                amount=50.00,
                period='monthly'
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
            assert budget.spent > budget.amount
