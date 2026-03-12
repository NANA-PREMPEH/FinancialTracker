"""
Integration tests for REST API endpoints.

Tests API key authentication and CRUD operations via REST API.
"""

import pytest
from app.models import ApiKey, Wallet, Category, Expense
from werkzeug.security import generate_password_hash


class TestAPIKeyAuthentication:
    """Tests for API key authentication."""
    
    def test_api_requires_key(self, client):
        """Test that API endpoints require authentication."""
        response = client.get('/api/v1/wallets')
        assert response.status_code == 401
    
    def test_api_valid_key(self, client, app, test_user, db):
        """Test API with valid key."""
        with app.app_context():
            # Create API key
            api_key = ApiKey(
                user_id=test_user.id,
                name='Test Key',
                permissions='read,write',
                is_active=True
            )
            api_key.set_key('test-api-key-123')
            db.session.add(api_key)
            db.session.commit()
            
            # Make request with valid key
            response = client.get(
                '/api/v1/wallets',
                headers={'X-API-Key': 'test-api-key-123'}
            )
            
            assert response.status_code == 200
    
    def test_api_invalid_key(self, client):
        """Test API with invalid key."""
        response = client.get(
            '/api/v1/wallets',
            headers={'X-API-Key': 'invalid-key'}
        )
        
        assert response.status_code == 401
    
    def test_api_query_param_key(self, client, app, test_user, db):
        """Test API key as query parameter."""
        with app.app_context():
            api_key = ApiKey(
                user_id=test_user.id,
                name='Test Key',
                permissions='read',
                is_active=True
            )
            api_key.set_key('query-test-key')
            db.session.add(api_key)
            db.session.commit()
            
            response = client.get(
                '/api/v1/wallets?api_key=query-test-key'
            )
            
            assert response.status_code == 200


class TestAPIWallets:
    """Tests for wallet API endpoints."""
    
    def test_list_wallets_api(self, client, app, test_user, db):
        """Test listing wallets via API."""
        with app.app_context():
            api_key = ApiKey(
                user_id=test_user.id,
                name='Test Key',
                permissions='read',
                is_active=True
            )
            api_key.set_key('wallets-test-key')
            db.session.add(api_key)
            
            wallet = Wallet(
                user_id=test_user.id,
                name='API Wallet',
                balance=1000.00
            )
            db.session.add(wallet)
            db.session.commit()
            
            response = client.get(
                '/api/v1/wallets',
                headers={'X-API-Key': 'wallets-test-key'}
            )
            
            assert response.status_code == 200
            data = response.get_json()
            assert 'data' in data
    
    def test_create_wallet_api(self, client, app, test_user, db):
        """Test creating wallet via API."""
        with app.app_context():
            api_key = ApiKey(
                user_id=test_user.id,
                name='Test Key',
                permissions='write',
                is_active=True
            )
            api_key.set_key('create-wallet-key')
            db.session.add(api_key)
            db.session.commit()
            
            response = client.post(
                '/api/v1/wallets',
                headers={'X-API-Key': 'create-wallet-key'},
                json={
                    'name': 'API Created Wallet',
                    'balance': 500.00,
                    'currency': 'USD'
                }
            )
            
            assert response.status_code == 201


class TestAPITransactions:
    """Tests for transactions API endpoints."""
    
    def test_list_transactions_api(self, client, app, test_user, test_wallet, test_category, db):
        """Test listing transactions via API."""
        with app.app_context():
            api_key = ApiKey(
                user_id=test_user.id,
                name='Test Key',
                permissions='read',
                is_active=True
            )
            api_key.set_key('transactions-test-key')
            db.session.add(api_key)
            
            expense = Expense(
                user_id=test_user.id,
                description='API Test',
                amount=50.00,
                transaction_type='expense',
                category_id=test_category.id,
                wallet_id=test_wallet.id
            )
            db.session.add(expense)
            db.session.commit()
            
            response = client.get(
                '/api/v1/transactions',
                headers={'X-API-Key': 'transactions-test-key'}
            )
            
            assert response.status_code == 200
    
    def test_create_transaction_api(self, client, app, test_user, test_wallet, test_category, db):
        """Test creating transaction via API."""
        with app.app_context():
            api_key = ApiKey(
                user_id=test_user.id,
                name='Test Key',
                permissions='write_transactions',
                is_active=True
            )
            api_key.set_key('create-tx-key')
            db.session.add(api_key)
            db.session.commit()
            
            response = client.post(
                '/api/v1/transactions',
                headers={'X-API-Key': 'create-tx-key'},
                json={
                    'description': 'API Income',
                    'amount': 1000.00,
                    'transaction_type': 'income',
                    'category_id': test_category.id,
                    'wallet_id': test_wallet.id
                }
            )
            
            assert response.status_code == 201


class TestAPIBulkOperations:
    """Tests for bulk API operations."""
    
    def test_bulk_create_transactions(self, client, app, test_user, test_wallet, test_category, db):
        """Test bulk creating transactions."""
        with app.app_context():
            api_key = ApiKey(
                user_id=test_user.id,
                name='Test Key',
                permissions='write_transactions',
                is_active=True
            )
            api_key.set_key('bulk-tx-key')
            db.session.add(api_key)
            db.session.commit()
            
            response = client.post(
                '/api/v1/transactions/bulk',
                headers={'X-API-Key': 'bulk-tx-key'},
                json=[
                    {'description': 'Tx 1', 'amount': 10.00, 'category_id': test_category.id, 'wallet_id': test_wallet.id},
                    {'description': 'Tx 2', 'amount': 20.00, 'category_id': test_category.id, 'wallet_id': test_wallet.id},
                    {'description': 'Tx 3', 'amount': 30.00, 'category_id': test_category.id, 'wallet_id': test_wallet.id},
                ]
            )
            
            assert response.status_code == 201
            data = response.get_json()
            assert data['message'] == '3 transactions created'


class TestAPIRateLimiting:
    """Tests for API rate limiting."""
    
    def test_rate_limit_headers(self, client, app, test_user, db):
        """Test rate limit headers are present."""
        with app.app_context():
            api_key = ApiKey(
                user_id=test_user.id,
                name='Test Key',
                permissions='read',
                is_active=True
            )
            api_key.set_key('rate-test-key')
            db.session.add(api_key)
            db.session.commit()
            
            response = client.get(
                '/api/v1/wallets',
                headers={'X-API-Key': 'rate-test-key'}
            )
            
            assert 'X-RateLimit-Limit' in response.headers
            assert 'X-RateLimit-Remaining' in response.headers
