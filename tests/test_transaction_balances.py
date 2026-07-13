from datetime import datetime

from app import create_app, db
from app.models import Category, Expense, User, Wallet


def _login(client, user_id):
    with client.session_transaction() as session:
        session['_user_id'] = str(user_id)
        session['_fresh'] = True


def test_delete_transfer_out_restores_wallet_balance():
    app = create_app('testing')
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)

    with app.app_context():
        db.create_all()

        user = User(email='balances@example.com', name='Balance Tester')
        user.set_password('secret123')
        db.session.add(user)
        db.session.commit()

        wallet = Wallet(user_id=user.id, name='Merchant Line', balance=880.0, currency='GHS')
        category = Category(user_id=user.id, name='Transfer', icon='T')
        db.session.add_all([wallet, category])
        db.session.commit()

        expense = Expense(
            user_id=user.id,
            description='Transfer to Cash',
            amount=120.0,
            transaction_type='transfer_out',
            category_id=category.id,
            wallet_id=wallet.id,
            date=datetime(2026, 7, 13),
        )
        db.session.add(expense)
        db.session.commit()

        client = app.test_client()
        _login(client, user.id)

        response = client.post(f'/delete/{expense.id}', follow_redirects=True)

        db.session.refresh(wallet)

        assert response.status_code == 200
        assert db.session.get(Expense, expense.id) is None
        assert float(wallet.balance) == 1000.0

        db.session.remove()
        db.drop_all()


def test_delete_transfer_in_reverses_wallet_balance():
    app = create_app('testing')
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)

    with app.app_context():
        db.create_all()

        user = User(email='incoming@example.com', name='Incoming Tester')
        user.set_password('secret123')
        db.session.add(user)
        db.session.commit()

        wallet = Wallet(user_id=user.id, name='Merchant Line', balance=1610.0, currency='GHS')
        category = Category(user_id=user.id, name='Transfer', icon='T')
        db.session.add_all([wallet, category])
        db.session.commit()

        expense = Expense(
            user_id=user.id,
            description='Transfer from Osprem',
            amount=610.0,
            transaction_type='transfer_in',
            category_id=category.id,
            wallet_id=wallet.id,
            date=datetime(2026, 7, 13),
        )
        db.session.add(expense)
        db.session.commit()

        client = app.test_client()
        _login(client, user.id)

        response = client.post(f'/delete/{expense.id}', follow_redirects=True)

        db.session.refresh(wallet)

        assert response.status_code == 200
        assert db.session.get(Expense, expense.id) is None
        assert float(wallet.balance) == 1000.0

        db.session.remove()
        db.drop_all()


def test_edit_transfer_out_reapplies_wallet_balance():
    app = create_app('testing')
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)

    with app.app_context():
        db.create_all()

        user = User(email='edit-transfer@example.com', name='Edit Transfer Tester')
        user.set_password('secret123')
        db.session.add(user)
        db.session.commit()

        wallet = Wallet(user_id=user.id, name='Merchant Line', balance=880.0, currency='GHS')
        category = Category(user_id=user.id, name='Transfer', icon='T')
        db.session.add_all([wallet, category])
        db.session.commit()

        expense = Expense(
            user_id=user.id,
            description='Transfer to Cash',
            amount=120.0,
            transaction_type='transfer_out',
            category_id=category.id,
            wallet_id=wallet.id,
            date=datetime(2026, 7, 13),
        )
        db.session.add(expense)
        db.session.commit()

        client = app.test_client()
        _login(client, user.id)

        response = client.post(
            f'/edit/{expense.id}',
            data={
                'description': 'Transfer to Savings',
                'amount': '200',
                'category': str(category.id),
                'wallet': str(wallet.id),
                'transaction_type': 'transfer_out',
                'date': '2026-07-13',
                'currency': 'GHS',
            },
            follow_redirects=True,
        )

        db.session.refresh(wallet)
        db.session.refresh(expense)

        assert response.status_code == 200
        assert expense.description == 'Transfer to Savings'
        assert expense.amount == 200.0
        assert float(wallet.balance) == 800.0

        db.session.remove()
        db.drop_all()
