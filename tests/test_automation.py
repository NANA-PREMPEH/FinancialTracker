"""
Integration tests for automation engine.

Tests rule execution, triggers, and automated actions.
"""

import pytest
from app.models import AutomationRule, RecurringTransaction, Wallet


class TestAutomationAccess:
    """Tests for automation page access."""
    
    def test_automation_page_loads(self, authenticated_client):
        """Test automation page loads."""
        response = authenticated_client.get('/automation')
        assert response.status_code == 200
    
    def test_automation_requires_login(self, client):
        """Test that automation requires login."""
        response = client.get('/automation')
        assert response.status_code in [302, 401]


class TestAutomationRules:
    """Tests for automation rules."""
    
    def test_list_automation_rules(self, authenticated_client, app, test_user, db):
        """Test listing automation rules."""
        with app.app_context():
            rule = AutomationRule(
                user_id=test_user.id,
                name='Test Rule',
                trigger_type='budget_threshold',
                action_type='notify',
                conditions={'threshold': 80},
                is_active=True
            )
            db.session.add(rule)
            db.session.commit()
            
            response = authenticated_client.get('/automation')
            assert response.status_code == 200
    
    def test_create_automation_rule(self, authenticated_client, app, test_user, db):
        """Test creating an automation rule."""
        with app.app_context():
            response = authenticated_client.post('/automation/add', data={
                'name': 'New Rule',
                'trigger_type': 'recurring_due',
                'action_type': 'create_expense',
                'is_active': 'true'
            }, follow_redirects=True)
            
            assert response.status_code == 200
    
    def test_toggle_rule_active(self, authenticated_client, app, test_user, db):
        """Test toggling rule active status."""
        with app.app_context():
            rule = AutomationRule(
                user_id=test_user.id,
                name='Toggle Test',
                trigger_type='budget_threshold',
                action_type='notify',
                is_active=False
            )
            db.session.add(rule)
            db.session.commit()
            rule_id = rule.id
            
            # Toggle on
            response = authenticated_client.post(f'/automation/toggle/{rule_id}', follow_redirects=True)
            assert response.status_code == 200
    
    def test_delete_automation_rule(self, authenticated_client, app, test_user, db):
        """Test deleting an automation rule."""
        with app.app_context():
            rule = AutomationRule(
                user_id=test_user.id,
                name='To Delete',
                trigger_type='budget_threshold',
                action_type='notify',
                is_active=True
            )
            db.session.add(rule)
            db.session.commit()
            rule_id = rule.id
            
            response = authenticated_client.post(f'/automation/delete/{rule_id}', follow_redirects=True)
            assert response.status_code == 200


class TestTriggerTypes:
    """Tests for different trigger types."""
    
    def test_budget_threshold_trigger(self, authenticated_client, app, test_user, test_category, db):
        """Test budget threshold trigger."""
        with app.app_context():
            response = authenticated_client.post('/automation/add', data={
                'name': 'Budget Alert',
                'trigger_type': 'budget_threshold',
                'action_type': 'notify',
                'conditions': {'threshold': 80},
                'is_active': 'true'
            }, follow_redirects=True)
            
            assert response.status_code == 200
    
    def test_recurring_due_trigger(self, authenticated_client, app, test_user, db):
        """Test recurring transaction due trigger."""
        with app.app_context():
            response = authenticated_client.post('/automation/add', data={
                'name': 'Recurring Alert',
                'trigger_type': 'recurring_due',
                'action_type': 'notify',
                'is_active': 'true'
            }, follow_redirects=True)
            
            assert response.status_code == 200
    
    def test_balance_low_trigger(self, authenticated_client, app, test_user, db):
        """Test low balance trigger."""
        with app.app_context():
            response = authenticated_client.post('/automation/add', data={
                'name': 'Low Balance Alert',
                'trigger_type': 'balance_low',
                'action_type': 'notify',
                'conditions': {'min_balance': 100},
                'is_active': 'true'
            }, follow_redirects=True)
            
            assert response.status_code == 200


class TestActionTypes:
    """Tests for different action types."""
    
    def test_notify_action(self, authenticated_client, app, test_user, db):
        """Test notify action."""
        with app.app_context():
            response = authenticated_client.post('/automation/add', data={
                'name': 'Notify Action',
                'trigger_type': 'balance_low',
                'action_type': 'notify',
                'is_active': 'true'
            }, follow_redirects=True)
            
            assert response.status_code == 200
    
    def test_create_expense_action(self, authenticated_client, app, test_user, db):
        """Test create expense action."""
        with app.app_context():
            response = authenticated_client.post('/automation/add', data={
                'name': 'Auto Expense',
                'trigger_type': 'recurring_due',
                'action_type': 'create_expense',
                'is_active': 'true'
            }, follow_redirects=True)
            
            assert response.status_code == 200
    
    def test_category_change_action(self, authenticated_client, app, test_user, db):
        """Test category change action."""
        with app.app_context():
            response = authenticated_client.post('/automation/add', data={
                'name': 'Change Category',
                'trigger_type': 'recurring_due',
                'action_type': 'change_category',
                'is_active': 'true'
            }, follow_redirects=True)
            
            assert response.status_code == 200


class TestRuleExecution:
    """Tests for rule execution engine."""
    
    def test_rule_conditions_evaluation(self, app, test_user, db):
        """Test rule conditions are evaluated correctly."""
        with app.app_context():
            from app.automation_engine import evaluate_conditions
            
            # Test budget threshold
            conditions = {'threshold': 80}
            context = {'spent': 80, 'budget': 100}
            result = evaluate_conditions(conditions, context)
            assert result is True
    
    def test_rule_execution_context(self, app, test_user, test_wallet, db):
        """Test rule execution provides correct context."""
        with app.app_context():
            from app.automation_engine import prepare_rule_context
            
            context = prepare_rule_context(test_user.id)
            assert 'wallets' in context
            assert 'budgets' in context


class TestRecurringTransactions:
    """Tests for recurring transaction automation."""
    
    def test_recurring_transactions_page(self, authenticated_client):
        """Test recurring transactions page loads."""
        response = authenticated_client.get('/recurring')
        assert response.status_code == 200
    
    def test_create_recurring_transaction(self, authenticated_client, app, test_user, test_wallet, test_category, db):
        """Test creating recurring transaction."""
        with app.app_context():
            response = authenticated_client.post('/recurring/add', data={
                'description': 'Monthly Rent',
                'amount': '1000.00',
                'frequency': 'monthly',
                'category_id': str(test_category.id),
                'wallet_id': str(test_wallet.id),
                'start_date': '2025-01-01'
            }, follow_redirects=True)
            
            assert response.status_code == 200
