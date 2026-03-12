"""
Integration tests for wallet CRUD operations.

Tests creating, reading, updating wallets and transfers.
"""

import pytest
from app.models import Wallet, Expense


class TestWalletCreation:
    """Tests for wallet creation."""
    
    def test_add_wallet_page_loads(self, authenticated_client):
        """Test add wallet page loads."""
        response = authenticated_client.get('/add_wallet')
        assert response.status_code == 200
    
    def test_create_wallet_valid_data(self, authenticated_client, app, test_user, db):
        """Test creating a wallet with valid data."""
        with app.app_context():
            response = authenticated_client.post('/add_wallet', data={
                'name': 'Test Wallet',
                'balance': '1000.00',
                'currency': 'USD'
            }, follow_redirects=True)
            
            assert response.status_code == 200
    
    def test_create_wallet_default_balance(self, authenticated_client, app, test_user, db):
        """Test creating wallet with default balance."""
        with app.app_context():
            response = authenticated_client.post('/add_wallet', data={
                'name': 'Empty Wallet',
                'currency': 'USD'
            }, follow_redirects=True)
            
            assert response.status_code == 200


class TestWalletReading:
    """Tests for viewing wallets."""
    
    def test_wallets_page_loads(self, authenticated_client):
        """Test wallets page loads."""
        response = authenticated_client.get('/wallets')
        assert response.status_code == 200
    
    def test_wallets_list_shows_wallets(self, authenticated_client, app, test_user, db):
        """Test that wallets are displayed in list."""
        with app.app_context():
            wallet = Wallet(
                user_id=test_user.id,
                name='My Wallet',
                balance=500.00
            )
            db.session.add(wallet)
            db.session.commit()
            
            response = authenticated_client.get('/wallets')
            assert response.status_code == 200
            assert b'My Wallet' in response.data or b'my wallet' in response.data.lower()


class TestWalletUpdate:
    """Tests for updating wallets."""
    
    def test_edit_wallet_page_loads(self, authenticated_client, app, test_user, db):
        """Test edit wallet page loads."""
        with app.app_context():
            wallet = Wallet(
                user_id=test_user.id,
                name='Original',
                balance=100.00
            )
            db.session.add(wallet)
            db.session.commit()
            
            response = authenticated_client.get(f'/edit_wallet/{wallet.id}')
            assert response.status_code == 200
    
    def test_update_wallet(self, authenticated_client, app, test_user, db):
        """Test updating a wallet."""
        with app.app_context():
            wallet = Wallet(
                user_id=test_user.id,
                name='Original',
                balance=100.00
            )
            db.session.add(wallet)
            db.session.commit()
            
            response = authenticated_client.post(f'/edit_wallet/{wallet.id}', data={
                'name': 'Updated',
                'balance': '200.00',
                'currency': 'USD'
            }, follow_redirects=True)
            
            assert response.status_code == 200


class TestWalletDelete:
    """Tests for deleting wallets."""
    
    def test_delete_wallet(self, authenticated_client, app, test_user, db):
        """Test deleting a wallet."""
        with app.app_context():
            wallet = Wallet(
                user_id=test_user.id,
                name='To Delete',
                balance=50.00
            )
            db.session.add(wallet)
            db.session.commit()
            wallet_id = wallet.id
            
            response = authenticated_client.post(f'/delete_wallet/{wallet_id}', follow_redirects=True)
            assert response.status_code == 200
            
            deleted = Wallet.query.get(wallet_id)
            assert deleted is None


class TestWalletTransfers:
    """Tests for wallet transfers."""
    
    def test_transfer_between_wallets(self, authenticated_client, app, test_user, db):
        """Test transferring between wallets."""
        with app.app_context():
            wallet1 = Wallet(user_id=test_user.id, name='Wallet 1', balance=500.00)
            wallet2 = Wallet(user_id=test_user.id, name='Wallet 2', balance=100.00)
            db.session.add_all([wallet1, wallet2])
            db.session.commit()
            
            # Transfer 100 from wallet1 to wallet2
            response = authenticated_client.post('/transfer', data={
                'from_wallet': str(wallet1.id),
                'to_wallet': str(wallet2.id),
                'amount': '100.00'
            }, follow_redirects=True)
            
            assert response.status_code == 200
            
            db.session.refresh(wallet1)
            db.session.refresh(wallet2)
            assert wallet1.balance == 400.00
            assert wallet2.balance == 200.00
