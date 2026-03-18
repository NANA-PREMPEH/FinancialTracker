"""
Integration tests for calculator functionality.

Tests calculator output validation and financial calculations.
"""

import pytest
import json


class TestCalculatorAccess:
    """Tests for calculator page access."""

    def test_calculator_page_loads(self, authenticated_client):
        """Test calculator page loads."""
        response = authenticated_client.get('/calculator')
        assert response.status_code == 200

    def test_calculator_requires_login(self, client):
        """Test that calculator requires login."""
        response = client.get('/calculator')
        assert response.status_code in [302, 401]


class TestCompoundInterest:
    """Tests for compound interest calculations."""

    def test_compound_interest_basic(self, authenticated_client):
        """Test basic compound interest calculation."""
        response = authenticated_client.post('/calculator/compute',
            data=json.dumps({
                'type': 'compound',
                'principal': 1000,
                'rate': 5,
                'years': 10,
                'monthly_contrib': 0
            }),
            content_type='application/json')

        assert response.status_code == 200

    def test_compound_interest_monthly(self, authenticated_client):
        """Test monthly compounding with contributions."""
        response = authenticated_client.post('/calculator/compute',
            data=json.dumps({
                'type': 'compound',
                'principal': 10000,
                'rate': 6,
                'years': 5,
                'monthly_contrib': 100
            }),
            content_type='application/json')

        assert response.status_code == 200

    def test_compound_interest_zero_rate(self, authenticated_client):
        """Test with zero interest rate."""
        response = authenticated_client.post('/calculator/compute',
            data=json.dumps({
                'type': 'compound',
                'principal': 1000,
                'rate': 0,
                'years': 10,
                'monthly_contrib': 0
            }),
            content_type='application/json')

        assert response.status_code == 200


class TestLoanCalculator:
    """Tests for loan calculations."""

    def test_loan_payment_calculation(self, authenticated_client):
        """Test loan payment calculation."""
        response = authenticated_client.post('/calculator/compute',
            data=json.dumps({
                'type': 'loan',
                'principal': 200000,
                'rate': 5,
                'years': 30
            }),
            content_type='application/json')

        assert response.status_code == 200

    def test_loan_zero_principal(self, authenticated_client):
        """Test with zero principal returns error."""
        response = authenticated_client.post('/calculator/compute',
            data=json.dumps({
                'type': 'loan',
                'principal': 0,
                'rate': 5,
                'years': 30
            }),
            content_type='application/json')

        # Function returns None for principal <= 0, so endpoint returns 400
        assert response.status_code == 400


class TestSavingsGoal:
    """Tests for savings goal calculations."""

    def test_savings_goal_basic(self, authenticated_client):
        """Test basic savings goal calculation."""
        response = authenticated_client.post('/calculator/compute',
            data=json.dumps({
                'type': 'savings',
                'target': 10000,
                'current': 1000,
                'rate': 4,
                'years': 5
            }),
            content_type='application/json')

        assert response.status_code == 200

    def test_savings_goal_no_current(self, authenticated_client):
        """Test savings goal starting from zero."""
        response = authenticated_client.post('/calculator/compute',
            data=json.dumps({
                'type': 'savings',
                'target': 50000,
                'current': 0,
                'rate': 5,
                'years': 10
            }),
            content_type='application/json')

        assert response.status_code == 200


class TestNetWorthProjection:
    """Tests for net worth projection calculations."""

    def test_net_worth_basic(self, authenticated_client):
        """Test basic net worth projection."""
        response = authenticated_client.post('/calculator/compute',
            data=json.dumps({
                'type': 'net_worth',
                'assets': 100000,
                'debts': 50000,
                'monthly_savings': 1000,
                'rate': 5,
                'years': 10
            }),
            content_type='application/json')

        assert response.status_code == 200


class TestCalculatorValidation:
    """Tests for calculator input validation."""

    def test_unknown_calculator_type(self, authenticated_client):
        """Test handling unknown calculator type."""
        response = authenticated_client.post('/calculator/compute',
            data=json.dumps({
                'type': 'nonexistent_type',
                'principal': 1000
            }),
            content_type='application/json')

        assert response.status_code == 400

    def test_loan_invalid_inputs(self, authenticated_client):
        """Test loan with invalid inputs returns error."""
        response = authenticated_client.post('/calculator/compute',
            data=json.dumps({
                'type': 'loan',
                'principal': -1000,
                'rate': 5,
                'years': 10
            }),
            content_type='application/json')

        assert response.status_code == 400
