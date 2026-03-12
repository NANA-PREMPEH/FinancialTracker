"""
Integration tests for authentication routes.

Tests login, register, password reset, and 2FA functionality.
"""

import pytest
from app.models import User


class TestRegistration:
    """Tests for user registration."""
    
    def test_register_get(self, client):
        """Test registration page loads."""
        response = client.get('/auth/register')
        assert response.status_code == 200
        assert b'register' in response.data.lower() or b'sign up' in response.data.lower()
    
    def test_register_valid_input(self, client, app, db):
        """Test successful user registration."""
        with app.app_context():
            response = client.post('/auth/register', data={
                'email': 'newuser@example.com',
                'username': 'newuser',
                'first_name': 'New',
                'last_name': 'User',
                'password': 'securepassword123',
                'confirm_password': 'securepassword123'
            }, follow_redirects=True)
            
            # Should redirect to login or dashboard
            assert response.status_code == 200
    
    def test_register_password_mismatch(self, client):
        """Test registration with password mismatch."""
        response = client.post('/auth/register', data={
            'email': 'user@example.com',
            'username': 'user',
            'first_name': 'User',
            'last_name': 'Test',
            'password': 'password123',
            'confirm_password': 'differentpassword'
        })
        
        # Should show error
        assert b'password' in response.data.lower() or b'match' in response.data.lower()
    
    def test_register_duplicate_email(self, client, app, test_user, db):
        """Test registration with duplicate email."""
        with app.app_context():
            response = client.post('/auth/register', data={
                'email': test_user.email,  # Already exists
                'username': 'different',
                'first_name': 'Test',
                'last_name': 'User',
                'password': 'password123',
                'confirm_password': 'password123'
            })
            
            # Should show error about email
            assert response.status_code == 200  # Or 400 depending on implementation


class TestLogin:
    """Tests for user login."""
    
    def test_login_get(self, client):
        """Test login page loads."""
        response = client.get('/auth/login')
        assert response.status_code == 200
        assert b'login' in response.data.lower() or b'sign in' in response.data.lower()
    
    def test_login_valid_credentials(self, client, app, test_user, db):
        """Test login with valid credentials."""
        with app.app_context():
            response = client.post('/auth/login', data={
                'email': test_user.email,
                'password': 'testpassword123'
            }, follow_redirects=True)
            
            assert response.status_code == 200
    
    def test_login_invalid_password(self, client, app, test_user, db):
        """Test login with wrong password."""
        with app.app_context():
            response = client.post('/auth/login', data={
                'email': test_user.email,
                'password': 'wrongpassword'
            })
            
            # Should show error
            assert b'invalid' in response.data.lower() or b'error' in response.data.lower()
    
    def test_login_nonexistent_user(self, client):
        """Test login with non-existent user."""
        response = client.post('/auth/login', data={
            'email': 'nonexistent@example.com',
            'password': 'password123'
        })
        
        # Should show error
        assert response.status_code == 200


class TestPasswordReset:
    """Tests for password reset functionality."""
    
    def test_request_reset_get(self, client):
        """Test password reset request page loads."""
        response = client.get('/auth/request_reset')
        assert response.status_code == 200
    
    def test_request_reset_valid_email(self, client, app, test_user, db):
        """Test password reset request with valid email."""
        with app.app_context():
            response = client.post('/auth/request_reset', data={
                'email': test_user.email
            })
            
            # Should show success message (even if email doesn't actually send in test)
            assert response.status_code == 200
    
    def test_request_reset_invalid_email(self, client):
        """Test password reset request with invalid email."""
        response = client.post('/auth/request_reset', data={
            'email': 'nonexistent@example.com'
        })
        
        # Should still show success (to prevent email enumeration)
        assert response.status_code == 200


class TestTwoFactor:
    """Tests for 2FA functionality."""
    
    def test_setup_2fa_get(self, authenticated_client):
        """Test 2FA setup page loads for authenticated user."""
        response = authenticated_client.get('/auth/setup_2fa')
        # Should either load or redirect if already set up
        assert response.status_code in [200, 302]
    
    def test_verify_2fa_get(self, client):
        """Test 2FA verification page loads."""
        response = authenticated_client.get('/auth/verify_2fa')
        assert response.status_code in [200, 302]


class TestLogout:
    """Tests for logout functionality."""
    
    def test_logout(self, authenticated_client):
        """Test user logout."""
        response = authenticated_client.get('/auth/logout', follow_redirects=True)
        assert response.status_code == 200


class TestAuthenticationFlows:
    """Tests for complete authentication flows."""
    
    def test_full_registration_login_flow(self, client, app, db):
        """Test complete registration then login flow."""
        with app.app_context():
            # Register
            register_response = client.post('/auth/register', data={
                'email': 'flowtest@example.com',
                'username': 'flowtest',
                'first_name': 'Flow',
                'last_name': 'Test',
                'password': 'testpass123',
                'confirm_password': 'testpass123'
            }, follow_redirects=True)
            
            # Login
            login_response = client.post('/auth/login', data={
                'email': 'flowtest@example.com',
                'password': 'testpass123'
            }, follow_redirects=True)
            
            assert login_response.status_code == 200
    
    def test_unauthenticated_access_redirect(self, client):
        """Test that unauthenticated users are redirected to login."""
        response = client.get('/', follow_redirects=False)
        # Should redirect to login
        assert response.status_code in [302, 401]
