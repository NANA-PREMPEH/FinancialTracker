"""
Integration tests for calculator functionality.

Tests calculator output validation and financial calculations.
"""

import pytest


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
        response = authenticated_client.post('/calculator/compound-interest', data={
            'principal': '1000',
            'rate': '5',
            'years': '10',
            'compounding': 'annually'
        })
        
        assert response.status_code == 200
    
    def test_compound_interest_monthly(self, authenticated_client):
        """Test monthly compounding."""
        response = authenticated_client.post('/calculator/compound-interest', data={
            'principal': '10000',
            'rate': '6',
            'years': '5',
            'compounding': 'monthly'
        })
        
        assert response.status_code == 200
    
    def test_compound_interest_zero_rate(self, authenticated_client):
        """Test with zero interest rate."""
        response = authenticated_client.post('/calculator/compound-interest', data={
            'principal': '1000',
            'rate': '0',
            'years': '10',
            'compounding': 'annually'
        })
        
        assert response.status_code == 200


class TestLoanCalculator:
    """Tests for loan calculations."""
    
    def test_loan_payment_calculation(self, authenticated_client):
        """Test loan payment calculation."""
        response = authenticated_client.post('/calculator/loan', data={
            'principal': '200000',
            'rate': '5',
            'years': '30'
        })
        
        assert response.status_code == 200
    
    def test_loan_zero_principal(self, authenticated_client):
        """Test with zero principal."""
        response = authenticated_client.post('/calculator/loan', data={
            'principal': '0',
            'rate': '5',
            'years': '30'
        })
        
        assert response.status_code == 200


class TestInvestmentReturn:
    """Tests for investment return calculations."""
    
    def test_simple_roi(self, authenticated_client):
        """Test simple ROI calculation."""
        response = authenticated_client.post('/calculator/roi', data={
            'initial': '1000',
            'final': '1500'
        })
        
        assert response.status_code == 200
    
    def test_roi_with_period(self, authenticated_client):
        """Test ROI with time period."""
        response = authenticated_client.post('/calculator/roi', data={
            'initial': '10000',
            'final': '12000',
            'years': '2'
        })
        
        assert response.status_code == 200
    
    def test_roi_negative_return(self, authenticated_client):
        """Test negative ROI."""
        response = authenticated_client.post('/calculator/roi', data={
            'initial': '1000',
            'final': '800'
        })
        
        assert response.status_code == 200


class TestSavingsGoal:
    """Tests for savings goal calculations."""
    
    def test_monthly_savings_needed(self, authenticated_client):
        """Test calculating monthly savings needed."""
        response = authenticated_client.post('/calculator/savings-goal', data={
            'goal': '10000',
            'years': '5',
            'rate': '4'
        })
        
        assert response.status_code == 200
    
    def test_goal_time_calculation(self, authenticated_client):
        """Test calculating time to reach goal."""
        response = authenticated_client.post('/calculator/savings-goal', data={
            'goal': '50000',
            'monthly': '500',
            'rate': '5'
        })
        
        assert response.status_code == 200


class TestInflation:
    """Tests for inflation calculations."""
    
    def test_inflation_adjusted_value(self, authenticated_client):
        """Test inflation adjustment."""
        response = authenticated_client.post('/calculator/inflation', data={
            'amount': '100000',
            'years': '20',
            'rate': '3'
        })
        
        assert response.status_code == 200


class TestCalculatorValidation:
    """Tests for calculator input validation."""
    
    def test_negative_principal(self, authenticated_client):
        """Test handling negative principal."""
        response = authenticated_client.post('/calculator/compound-interest', data={
            'principal': '-1000',
            'rate': '5',
            'years': '10',
            'compounding': 'annually'
        })
        
        # Should handle validation
        assert response.status_code in [200, 400]
    
    def test_negative_rate(self, authenticated_client):
        """Test handling negative rate."""
        response = authenticated_client.post('/calculator/compound-interest', data={
            'principal': '1000',
            'rate': '-5',
            'years': '10',
            'compounding': 'annually'
        })
        
        assert response.status_code in [200, 400]
    
    def test_zero_years(self, authenticated_client):
        """Test handling zero years."""
        response = authenticated_client.post('/calculator/compound-interest', data={
            'principal': '1000',
            'rate': '5',
            'years': '0',
            'compounding': 'annually'
        })
        
        assert response.status_code in [200, 400]
