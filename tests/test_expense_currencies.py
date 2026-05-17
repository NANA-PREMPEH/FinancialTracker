from datetime import UTC, datetime

import pytest

from app import create_app, db
from app.models import Category, ExchangeRate, Expense, User, Wallet


@pytest.fixture
def app():
    app = create_app('testing')
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def user(app):
    with app.app_context():
        user = User(
            email='currency@example.com',
            name='Currency Tester'
        )
        user.set_password('secret123')
        db.session.add(user)
        db.session.commit()
        return user


@pytest.fixture
def authenticated_client(client, user):
    with client.session_transaction() as session:
        session['_user_id'] = str(user.id)
        session['_fresh'] = True
    return client


@pytest.fixture
def ghs_wallet(app, user):
    with app.app_context():
        wallet = Wallet(
            user_id=user.id,
            name='Main Wallet',
            balance=2000.0,
            currency='GHS'
        )
        db.session.add(wallet)
        db.session.commit()
        return wallet


@pytest.fixture
def food_category(app, user):
    with app.app_context():
        category = Category(
            user_id=user.id,
            name='Food',
            icon='F'
        )
        db.session.add(category)
        db.session.commit()
        return category


@pytest.fixture
def usd_wallet(app, user):
    with app.app_context():
        wallet = Wallet(
            user_id=user.id,
            name='USD Wallet',
            balance=500.0,
            currency='USD'
        )
        db.session.add(wallet)
        db.session.commit()
        return wallet


def add_exchange_rate(from_currency, to_currency, rate):
    exchange_rate = ExchangeRate(
        from_currency=from_currency,
        to_currency=to_currency,
        rate=rate,
        date=datetime.now(UTC)
    )
    db.session.add(exchange_rate)
    db.session.commit()


def test_add_expense_preserves_selected_currency(authenticated_client, app, ghs_wallet, food_category):
    with app.app_context():
        add_exchange_rate('USD', 'GHS', 15.0)

        response = authenticated_client.post(
            '/add',
            data={
                'description': 'Cloud subscription',
                'amount': '100',
                'category': str(food_category.id),
                'wallet': str(ghs_wallet.id),
                'transaction_type': 'expense',
                'currency': 'USD',
                'date': '2026-05-07'
            },
            follow_redirects=True
        )

        assert response.status_code == 200

        expense = Expense.query.filter_by(description='Cloud subscription').one()
        wallet = db.session.get(Wallet, ghs_wallet.id)

        assert expense.original_amount == pytest.approx(100.0)
        assert expense.original_currency == 'USD'
        assert expense.amount == pytest.approx(1500.0)
        assert float(wallet.balance) == pytest.approx(500.0)

        history = authenticated_client.get('/expenses')
        assert b'Cloud subscription' in history.data
        assert b'USD' in history.data
        assert b'Stored as GHS 1500.00' in history.data


def test_add_income_requires_source_of_income(authenticated_client, app, ghs_wallet, food_category):
    with app.app_context():
        response = authenticated_client.post(
            '/add',
            data={
                'description': 'Monthly pay',
                'amount': '2500',
                'category': str(food_category.id),
                'wallet': str(ghs_wallet.id),
                'transaction_type': 'income',
                'currency': 'GHS',
                'date': '2026-05-07'
            },
            follow_redirects=True
        )

        assert response.status_code == 200
        assert b'Please provide the source of income.' in response.data
        assert Expense.query.filter_by(description='Monthly pay').count() == 0


def test_add_income_persists_source_of_income(authenticated_client, app, ghs_wallet, food_category):
    with app.app_context():
        response = authenticated_client.post(
            '/add',
            data={
                'description': 'Monthly pay',
                'income_source': 'Salary',
                'amount': '2500',
                'category': str(food_category.id),
                'wallet': str(ghs_wallet.id),
                'transaction_type': 'income',
                'currency': 'GHS',
                'date': '2026-05-07'
            },
            follow_redirects=True
        )

        assert response.status_code == 200

        income = Expense.query.filter_by(description='Monthly pay').one()
        assert income.income_source == 'Salary'

        history = authenticated_client.get('/expenses')
        assert b'Source: Salary' in history.data


def test_edit_expense_supports_currency_selection_and_conversion(authenticated_client, app, user, ghs_wallet, food_category):
    with app.app_context():
        expense = Expense(
            user_id=user.id,
            amount=120.0,
            original_amount=120.0,
            original_currency='GHS',
            description='Office supplies',
            transaction_type='expense',
            category_id=food_category.id,
            wallet_id=ghs_wallet.id,
            date=datetime(2026, 5, 6)
        )
        db.session.add(expense)
        ghs_wallet.balance = 1880.0
        db.session.commit()

        edit_page = authenticated_client.get(f'/edit/{expense.id}')
        assert edit_page.status_code == 200
        assert b'name="currency"' in edit_page.data
        assert b'value="GHS" selected' in edit_page.data

        add_exchange_rate('EUR', 'GHS', 18.0)

        response = authenticated_client.post(
            f'/edit/{expense.id}',
            data={
                'description': 'Office supplies',
                'amount': '50',
                'currency': 'EUR',
                'category': str(food_category.id),
                'wallet': str(ghs_wallet.id),
                'transaction_type': 'expense',
                'date': '2026-05-06'
            },
            follow_redirects=True
        )

        assert response.status_code == 200

        expense = db.session.get(Expense, expense.id)
        wallet = db.session.get(Wallet, ghs_wallet.id)

        assert expense.original_amount == pytest.approx(50.0)
        assert expense.original_currency == 'EUR'
        assert expense.amount == pytest.approx(900.0)
        assert float(wallet.balance) == pytest.approx(1100.0)


def test_edit_income_updates_and_clears_income_source(authenticated_client, app, user, ghs_wallet, food_category):
    with app.app_context():
        income = Expense(
            user_id=user.id,
            amount=1000.0,
            original_amount=1000.0,
            original_currency='GHS',
            description='Client payment',
            transaction_type='income',
            income_source='Freelance',
            category_id=food_category.id,
            wallet_id=ghs_wallet.id,
            date=datetime(2026, 5, 6)
        )
        db.session.add(income)
        ghs_wallet.balance = 3000.0
        db.session.commit()

        response = authenticated_client.post(
            f'/edit/{income.id}',
            data={
                'description': 'Client payment',
                'income_source': 'Consulting',
                'amount': '1000',
                'currency': 'GHS',
                'category': str(food_category.id),
                'wallet': str(ghs_wallet.id),
                'transaction_type': 'income',
                'date': '2026-05-06'
            },
            follow_redirects=True
        )

        assert response.status_code == 200

        income = db.session.get(Expense, income.id)
        assert income.income_source == 'Consulting'

        response = authenticated_client.post(
            f'/edit/{income.id}',
            data={
                'description': 'Client payment',
                'amount': '1000',
                'currency': 'GHS',
                'category': str(food_category.id),
                'wallet': str(ghs_wallet.id),
                'transaction_type': 'expense',
                'date': '2026-05-06'
            },
            follow_redirects=True
        )

        assert response.status_code == 200

        income = db.session.get(Expense, income.id)
        assert income.income_source is None


def test_analytics_converts_legacy_foreign_transactions_to_ghs(authenticated_client, app, user, ghs_wallet, food_category):
    with app.app_context():
        add_exchange_rate('USD', 'GHS', 15.0)

        expense = Expense(
            user_id=user.id,
            amount=100.0,
            original_amount=100.0,
            original_currency='USD',
            description='Legacy USD expense',
            transaction_type='expense',
            category_id=food_category.id,
            wallet_id=ghs_wallet.id,
            date=datetime(2026, 5, 7)
        )
        db.session.add(expense)
        db.session.commit()

        response = authenticated_client.get('/analytics')

        assert response.status_code == 200
        assert b'All live analytics amounts on this page are shown in GHS equivalent' in response.data
        assert b'GHS 1500.00' in response.data


def test_analytics_converts_foreign_wallet_transactions_to_ghs(authenticated_client, app, user, usd_wallet, food_category):
    with app.app_context():
        add_exchange_rate('USD', 'GHS', 15.0)

        expense = Expense(
            user_id=user.id,
            amount=50.0,
            original_amount=50.0,
            original_currency='USD',
            description='USD wallet expense',
            transaction_type='expense',
            category_id=food_category.id,
            wallet_id=usd_wallet.id,
            date=datetime(2026, 5, 7)
        )
        db.session.add(expense)
        db.session.commit()

        response = authenticated_client.get('/analytics')

        assert response.status_code == 200
        assert b'GHS 750.00' in response.data


def test_transactions_page_shows_filtered_total_in_default_currency(authenticated_client, app, user, ghs_wallet, usd_wallet, food_category):
    with app.app_context():
        add_exchange_rate('USD', 'GHS', 15.0)

        local_expense = Expense(
            user_id=user.id,
            amount=100.0,
            original_amount=100.0,
            original_currency='GHS',
            description='Lunch',
            transaction_type='expense',
            category_id=food_category.id,
            wallet_id=ghs_wallet.id,
            date=datetime(2026, 5, 7)
        )
        foreign_expense = Expense(
            user_id=user.id,
            amount=10.0,
            original_amount=10.0,
            original_currency='USD',
            description='Hosting',
            transaction_type='expense',
            category_id=food_category.id,
            wallet_id=usd_wallet.id,
            date=datetime(2026, 5, 8)
        )
        db.session.add_all([local_expense, foreign_expense])
        db.session.commit()

        response = authenticated_client.get('/transactions')

        assert response.status_code == 200
        assert b'Total:' in response.data
        assert b'GHS 250.00' in response.data
        assert b'Filtered total shown in GHS equivalent.' in response.data


def test_transactions_ajax_returns_filtered_total(authenticated_client, app, user, ghs_wallet, usd_wallet, food_category):
    with app.app_context():
        add_exchange_rate('USD', 'GHS', 15.0)

        lunch = Expense(
            user_id=user.id,
            amount=100.0,
            original_amount=100.0,
            original_currency='GHS',
            description='Lunch',
            transaction_type='expense',
            category_id=food_category.id,
            wallet_id=ghs_wallet.id,
            date=datetime(2026, 5, 7)
        )
        hosting = Expense(
            user_id=user.id,
            amount=10.0,
            original_amount=10.0,
            original_currency='USD',
            description='Hosting',
            transaction_type='expense',
            category_id=food_category.id,
            wallet_id=usd_wallet.id,
            date=datetime(2026, 5, 8)
        )
        db.session.add_all([lunch, hosting])
        db.session.commit()

        response = authenticated_client.get('/transactions?search=Lunch&ajax=1')

        assert response.status_code == 200
        data = response.get_json()
        assert data['count'] == 1
        assert data['total_currency'] == 'GHS'
        assert data['total_display'] == 'GHS 100.00'
        assert 'Lunch' in data['html']
