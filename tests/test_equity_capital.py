from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.models import (CapitalAllocation, Category, ChartOfAccount, EquityCapital, EquityTransaction, Expense,
                        JournalEntry, Project, ProjectCategory, ProjectItem, ProjectItemPayment, User, Wallet)


def _login(client, user):
    with client.session_transaction() as session:
        session['_user_id'] = str(user.id)
        session['_fresh'] = True


def _setup(app, db):
    user = User(email='equity@example.com', name='Equity Tester')
    user.set_password('test-password')
    db.session.add(user)
    db.session.flush()
    category = ProjectCategory(user_id=user.id, name='Trading')
    other_category = ProjectCategory(user_id=user.id, name='Services')
    wallet = Wallet(user_id=user.id, name='Cash', balance=Decimal('100.00'))
    db.session.add_all([category, other_category, wallet])
    db.session.flush()
    project = Project(user_id=user.id, category_id=category.id, name='Stock purchase', funding_source='other')
    other_project = Project(user_id=user.id, category_id=other_category.id, name='Other project', funding_source='other')
    capital = EquityCapital(user_id=user.id, category_id=category.id, initial_capital=1000)
    db.session.add_all([project, other_project, capital])
    db.session.commit()
    return user, wallet, capital, project, other_project


def test_equity_model_keeps_reinvestments_out_of_total_equity(app, db):
    with app.app_context():
        user, _, capital, project, _ = _setup(app, db)
        db.session.add(CapitalAllocation(user_id=user.id, equity_capital_id=capital.id,
                       allocation_type='reinvestment', funding_source='capital', amount=250, project_id=project.id))
        db.session.commit()
        assert capital.total_equity == 1000
        assert capital.available_contributed_capital == 750


def test_category_allows_only_one_equity_pool(app, db):
    with app.app_context():
        user, _, capital, _, _ = _setup(app, db)
        db.session.add(EquityCapital(user_id=user.id, category_id=capital.category_id, initial_capital=500))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


@pytest.mark.parametrize(
    ('funding_source', 'expected_type', 'partner_name'),
    [
        ('owner_injection', 'injection', ''),
        ('partner_contribution', 'partner_contribution', 'Ama Mensah'),
    ],
)
def test_project_expense_can_be_funded_by_new_equity_contribution(
    app, client, db, funding_source, expected_type, partner_name
):
    """New external capital reaches the wallet, then funds the linked expense atomically."""
    with app.app_context():
        user, wallet, capital, project, _ = _setup(app, db)
        transaction_category = Category(user_id=user.id, name='Project', icon='P')
        db.session.add(transaction_category)
        db.session.commit()
        _login(client, user)

        response = client.post('/add', data={
            'description': f'{expected_type} funded stock',
            'amount': '250',
            'category': str(transaction_category.id),
            'project_type': 'Business',
            'project_id': str(project.id),
            'business_category_id': str(project.category_id),
            'wallet': str(wallet.id),
            'transaction_type': 'expense',
            'currency': 'GHS',
            'date': '2026-10-04',
            'equity_funding_source': funding_source,
            'partner_name': partner_name,
        })

        assert response.status_code == 302
        expense = Expense.query.filter_by(description=f'{expected_type} funded stock').one()
        movement = EquityTransaction.query.filter_by(equity_capital_id=capital.id).one()
        allocation = CapitalAllocation.query.filter_by(expense_id=expense.id).one()
        db.session.refresh(wallet)

        assert movement.transaction_type == expected_type
        assert movement.partner_name == (partner_name or None)
        assert movement.journal_entry_id is not None
        assert allocation.project_id == project.id
        assert allocation.funding_source == 'capital'
        assert float(wallet.balance) == pytest.approx(100.0)


def test_add_project_transaction_funding_sources_preserve_expected_wallet_and_equity_effects(app, client, db):
    with app.app_context():
        user, wallet, capital, project, _ = _setup(app, db)
        transaction_category = Category(user_id=user.id, name='Project', icon='P')
        income = ProjectItem(user_id=user.id, project_id=project.id, item_name='Completed sale', cost=100, item_type='income')
        db.session.add_all([transaction_category, income])
        db.session.flush()
        db.session.add(ProjectItemPayment(user_id=user.id, project_item_id=income.id, amount=100, is_paid=True))
        db.session.commit()
        _login(client, user)
        equity_before_allocations = capital.total_equity

        def add_project_expense(description, amount, source='regular_wallet', target_project=project):
            return client.post('/add', data={
                'description': description, 'amount': str(amount), 'category': str(transaction_category.id),
                'project_type': 'Business', 'project_id': str(target_project.id),
                'business_category_id': str(target_project.category_id), 'wallet': str(wallet.id),
                'transaction_type': 'expense', 'currency': 'GHS', 'date': '2026-10-04',
                'equity_funding_source': source,
            })

        assert add_project_expense('Regular wallet expense', 20).status_code == 302
        assert CapitalAllocation.query.count() == 0
        assert float(db.session.get(Wallet, wallet.id).balance) == 80.0
        assert capital.total_equity == equity_before_allocations

        assert add_project_expense('Contributed capital expense', 30, 'capital').status_code == 302
        capital_allocation = CapitalAllocation.query.filter_by(expense_id=Expense.query.filter_by(
            description='Contributed capital expense').one().id).one()
        assert capital_allocation.funding_source == 'capital'
        assert capital.total_equity == equity_before_allocations

        assert add_project_expense('Retained earnings expense', 40, 'retained').status_code == 302
        retained_allocation = CapitalAllocation.query.filter_by(expense_id=Expense.query.filter_by(
            description='Retained earnings expense').one().id).one()
        assert retained_allocation.funding_source == 'retained'
        assert capital.total_equity == equity_before_allocations

        opening_category = ProjectCategory(user_id=user.id, name='Opening line')
        db.session.add(opening_category); db.session.flush()
        opening_project = Project(user_id=user.id, category_id=opening_category.id,
                                  name='Opening project', funding_source='other')
        db.session.add(opening_project); db.session.commit()
        wallet_before_opening = float(db.session.get(Wallet, wallet.id).balance)
        assert add_project_expense('Opening capital expense', 10, 'opening_capital', opening_project).status_code == 302
        opening_equity = EquityCapital.query.filter_by(user_id=user.id, category_id=opening_category.id).one()
        opening_allocation = CapitalAllocation.query.filter_by(expense_id=Expense.query.filter_by(
            description='Opening capital expense').one().id).one()
        assert opening_equity.initial_capital == 10
        assert opening_allocation.funding_source == 'capital'
        # Opening capital labels the source; it does not add another wallet inflow.
        assert float(db.session.get(Wallet, wallet.id).balance) == wallet_before_opening - 10


def test_project_equity_funding_rolls_back_every_related_change_on_commit_failure(app, client, db, monkeypatch):
    with app.app_context():
        user, wallet, capital, project, _ = _setup(app, db)
        transaction_category = Category(user_id=user.id, name='Project', icon='P')
        db.session.add(transaction_category)
        db.session.commit()
        _login(client, user)

        def failed_commit():
            raise SQLAlchemyError('simulated persistence failure')

        monkeypatch.setattr(db.session, 'commit', failed_commit)
        response = client.post('/add', data={
            'description': 'Failed capital-funded stock',
            'amount': '250',
            'category': str(transaction_category.id),
            'project_type': 'Business',
            'project_id': str(project.id),
            'business_category_id': str(project.category_id),
            'wallet': str(wallet.id),
            'transaction_type': 'expense',
            'currency': 'GHS',
            'date': '2026-10-04',
            'equity_funding_source': 'owner_injection',
        })

        assert response.status_code == 302
        assert Expense.query.filter_by(description='Failed capital-funded stock').count() == 0
        assert EquityTransaction.query.filter_by(equity_capital_id=capital.id).count() == 0
        assert CapitalAllocation.query.filter_by(equity_capital_id=capital.id).count() == 0
        assert float(db.session.get(Wallet, wallet.id).balance) == pytest.approx(100.0)


def test_historical_project_expense_reconciliation_preserves_cash_and_prevents_duplicates(app, client, db):
    with app.app_context():
        user, wallet, capital, project, other_project = _setup(app, db)
        transaction_category = Category(user_id=user.id, name='Project', icon='P')
        db.session.add(transaction_category)
        db.session.commit()
        historical_expense = Expense(
            user_id=user.id, amount=240, description='Prior stock purchase', transaction_type='expense',
            category_id=transaction_category.id, wallet_id=wallet.id, date=datetime(2026, 9, 15), project_id=project.id,
        )
        db.session.add(historical_expense)
        db.session.commit()
        _login(client, user)
        wallet_before = float(wallet.balance)

        response = client.post(f'/equity/reconcile/{capital.id}', data={
            'expense_id': str(historical_expense.id), 'funding_source': 'capital', 'notes': 'Imported history',
        })

        assert response.status_code == 302
        allocation = CapitalAllocation.query.filter_by(expense_id=historical_expense.id).one()
        assert allocation.amount == 240
        assert allocation.project_id == project.id
        assert allocation.funding_source == 'capital'
        assert allocation.notes == 'Imported history'
        assert float(db.session.get(Wallet, wallet.id).balance) == wallet_before
        assert Expense.query.get(historical_expense.id).amount == 240

        # The unique expense link and explicit validation keep a second reconciliation out.
        assert client.post(f'/equity/reconcile/{capital.id}', data={
            'expense_id': str(historical_expense.id), 'funding_source': 'capital',
        }).status_code == 302
        assert CapitalAllocation.query.filter_by(expense_id=historical_expense.id).count() == 1

        equity_page = client.get('/equity/')
        history_page = client.get('/expenses')
        project_page = client.get(f'/projects/{project.id}')
        assert b'Linked expense: Prior stock purchase' in equity_page.data
        assert b'Funded by Contributed capital' in history_page.data
        assert b'Prior stock purchase' in project_page.data
        assert capital.total_equity == 1000

        opening_expense = Expense(
            user_id=user.id, amount=150, description='Original setup cost', transaction_type='expense',
            category_id=transaction_category.id, wallet_id=wallet.id, date=datetime(2026, 8, 1), project_id=other_project.id,
        )
        opening_equity = EquityCapital.query.filter_by(user_id=user.id, category_id=other_project.category_id).one()
        db.session.add(opening_expense)
        db.session.commit()

        assert client.post(f'/equity/reconcile/{opening_equity.id}', data={
            'expense_id': str(opening_expense.id), 'funding_source': 'opening_capital',
        }).status_code == 302
        assert opening_equity.initial_capital == 150
        assert CapitalAllocation.query.filter_by(expense_id=opening_expense.id).one().funding_source == 'capital'
        assert float(db.session.get(Wallet, wallet.id).balance) == wallet_before


def test_historical_contribution_reconciliation_increases_equity_without_changing_wallet(app, client, db):
    with app.app_context():
        user, wallet, capital, project, _ = _setup(app, db)
        transaction_category = Category(user_id=user.id, name='Project', icon='P')
        expense = Expense(user_id=user.id, amount=2124, description='Launch Bowl 2: Lunch Box',
                          transaction_type='expense', category_id=1, wallet_id=wallet.id,
                          date=datetime(2026, 7, 17), project_id=project.id)
        db.session.add(transaction_category)
        db.session.flush()
        expense.category_id = transaction_category.id
        db.session.add(expense)
        db.session.commit()
        _login(client, user)
        wallet_before = float(wallet.balance)

        response = client.post(f'/equity/reconcile/{capital.id}', data={
            'expense_id': str(expense.id), 'funding_source': 'historical_contribution',
        })

        assert response.status_code == 302
        movement = EquityTransaction.query.filter_by(equity_capital_id=capital.id).one()
        allocation = CapitalAllocation.query.filter_by(expense_id=expense.id).one()
        assert movement.amount == 2124
        assert movement.affects_wallet is False
        assert movement.journal_entry_id is None
        assert allocation.amount == 2124
        assert allocation.equity_transaction_id == movement.id
        assert capital.contributed_capital == 3124
        assert float(db.session.get(Wallet, wallet.id).balance) == wallet_before


def test_historical_owner_injection_can_be_allocated_to_project_without_wallet_change(app, client, db):
    with app.app_context():
        user, wallet, capital, project, _ = _setup(app, db)
        _login(client, user)
        wallet_before = float(wallet.balance)

        response = client.post(f'/equity/historical-injection/{capital.id}', data={
            'amount': '2142', 'date': '2026-09-29', 'wallet_id': str(wallet.id),
            'project_id': str(project.id), 'description': 'Owner injection for Launch Bowl 2',
        })

        assert response.status_code == 302
        movement = EquityTransaction.query.filter_by(equity_capital_id=capital.id).one()
        allocation = CapitalAllocation.query.filter_by(equity_transaction_id=movement.id).one()
        assert movement.amount == 2142
        assert movement.affects_wallet is False
        assert allocation.project_id == project.id
        assert allocation.amount == 2142
        assert float(db.session.get(Wallet, wallet.id).balance) == wallet_before

        # The injection cannot be deleted while its funding allocation remains.
        assert client.post(f'/equity/transaction/delete/{movement.id}').status_code == 302
        assert EquityTransaction.query.filter_by(id=movement.id).count() == 1


def test_equity_overview_seeds_categories_and_is_scoped_to_current_user(app, client, db):
    with app.app_context():
        user, wallet, capital, project, _ = _setup(app, db)
        other_user = User(email='other-equity@example.com', name='Other User')
        other_user.set_password('test-password')
        db.session.add(other_user); db.session.flush()
        db.session.add_all([
            ProjectCategory(user_id=user.id, name='New category'),
            Wallet(user_id=other_user.id, name='Private wallet', balance=Decimal('500.00')),
            ProjectCategory(user_id=other_user.id, name='Private category'),
        ])
        db.session.commit()
        _login(client, user)

        response = client.get('/equity/')

        assert response.status_code == 200
        assert b'Equity Capital' in response.data
        assert b'Cash' in response.data
        assert b'Private wallet' not in response.data
        assert EquityCapital.query.filter_by(user_id=user.id).count() == 3
        assert EquityCapital.query.filter_by(user_id=other_user.id).count() == 0


def test_equity_page_renders_aggregate_cards_histories_and_empty_states(app, client, db):
    with app.app_context():
        user, wallet, capital, project, _ = _setup(app, db)
        db.session.add_all([
            EquityTransaction(user_id=user.id, equity_capital_id=capital.id, transaction_type='injection',
                amount=200, date=datetime(2026, 4, 1), description='Owner top-up', wallet_id=wallet.id),
            EquityTransaction(user_id=user.id, equity_capital_id=capital.id, transaction_type='partner_contribution',
                amount=50, date=datetime(2026, 4, 2), partner_name='Ama', wallet_id=wallet.id),
            CapitalAllocation(user_id=user.id, equity_capital_id=capital.id, allocation_type='project_funding',
                funding_source='capital', amount=300, date=datetime(2026, 4, 3), project_id=project.id),
        ])
        db.session.commit()
        _login(client, user)

        response = client.get('/equity/')

        assert response.status_code == 200
        for text in (b'Initial Capital', b'Additional Injections', b'Partner Contributions',
                     b'Owner Drawings', b'Contributed Capital', b'Retained Earnings', b'Total Equity',
                     b'Allocated', b'Unallocated', b'Owner top-up', b'Ama', b'Stock purchase',
                     b'No capital allocations yet.', b'No external capital movements yet.'):
            assert text in response.data
        for markup in (b'id="capitalSetupDialog"', b'name="initial_capital_date"',
                       b'id="movementDialog"', b'name="transaction_type"', b'name="wallet_id"',
                       b'id="partnerField"', b'id="allocationDialog"', b'name="funding_source"',
                       b'id="allocationProject"', b'togglePartnerField()',
                       b'toggleProjectRequirement()', b'window.lucide?.createIcons()',
                       b'if (e.target === dialog)', b'const projectIdsByCategory ='):
            assert markup in response.data
        assert response.data.count(b'data-currency-prefix') == 3
        assert b'bg-surface-active/70 border-r border-border' in response.data


def test_initial_capital_setup_saves_opening_balance_and_rejects_foreign_category(app, client, db):
    with app.app_context():
        user, wallet, _, _, _ = _setup(app, db)
        setup_category = ProjectCategory(user_id=user.id, name='New venture')
        other_user = User(email='foreign-setup@example.com', name='Foreign User')
        other_user.set_password('test-password')
        db.session.add_all([setup_category, other_user]); db.session.flush()
        foreign_category = ProjectCategory(user_id=other_user.id, name='Foreign category')
        db.session.add(foreign_category); db.session.commit()
        _login(client, user)

        response = client.post(f'/equity/setup/{setup_category.id}', data={
            'initial_capital': '1250.50',
            'initial_capital_date': '2026-01-15',
            'business_name': 'New Venture Ltd',
            'notes': 'Opening cash from the founder',
        })

        assert response.status_code == 302
        capital = EquityCapital.query.filter_by(category_id=setup_category.id).one()
        assert capital.initial_capital == 1250.50
        assert capital.initial_capital_date.date().isoformat() == '2026-01-15'
        assert capital.business_name == 'New Venture Ltd'
        assert capital.notes == 'Opening cash from the founder'
        assert float(db.session.get(Wallet, wallet.id).balance) == 100.0
        assert client.post(f'/equity/setup/{foreign_category.id}', data={'initial_capital': '10'}).status_code == 404


def test_initial_capital_setup_rolls_back_invalid_input(app, client, db):
    with app.app_context():
        user, _, capital, _, _ = _setup(app, db)
        _login(client, user)

        response = client.post(f'/equity/setup/{capital.category_id}', data={
            'initial_capital': '-50', 'initial_capital_date': 'not-a-date',
        })

        assert response.status_code == 302
        assert db.session.get(EquityCapital, capital.id).initial_capital == 1000


def test_external_transactions_validate_wallets_and_preserve_atomicity(app, client, db):
    with app.app_context():
        user, wallet, capital, _, _ = _setup(app, db)
        other_user = User(email='transaction-owner@example.com', name='Transaction Owner')
        other_user.set_password('test-password')
        db.session.add(other_user); db.session.flush()
        foreign_wallet = Wallet(user_id=other_user.id, name='Foreign cash', balance=Decimal('500.00'))
        db.session.add(foreign_wallet)
        foreign_category = ProjectCategory(user_id=other_user.id, name='Foreign equity category')
        db.session.add(foreign_category); db.session.flush()
        foreign_capital = EquityCapital(user_id=other_user.id, category_id=foreign_category.id, initial_capital=10)
        db.session.add(foreign_capital); db.session.commit()
        _login(client, user)

        invalid_requests = (
            {'transaction_type': 'invalid', 'amount': '20', 'wallet_id': str(wallet.id)},
            {'transaction_type': 'injection', 'amount': '0', 'wallet_id': str(wallet.id)},
            {'transaction_type': 'injection', 'amount': '20', 'wallet_id': str(foreign_wallet.id)},
            {'transaction_type': 'drawing', 'amount': '101', 'wallet_id': str(wallet.id)},
            {'transaction_type': 'injection', 'amount': '20', 'wallet_id': str(wallet.id), 'date': 'bad-date'},
        )
        for data in invalid_requests:
            assert client.post(f'/equity/transaction/add/{capital.id}', data=data).status_code == 302

        assert EquityTransaction.query.filter_by(user_id=user.id).count() == 0
        assert float(db.session.get(Wallet, wallet.id).balance) == 100.0
        assert client.post(f'/equity/transaction/add/{capital.id}', data={
            'transaction_type': 'partner_contribution', 'amount': '25', 'wallet_id': str(wallet.id),
            'date': '2026-02-05', 'partner_name': 'Ama', 'description': 'Seed funding', 'notes': 'Agreed share',
        }).status_code == 302
        transaction = EquityTransaction.query.filter_by(user_id=user.id).one()
        assert transaction.wallet_id == wallet.id
        assert transaction.partner_name == 'Ama'
        assert transaction.description == 'Seed funding'
        assert transaction.notes == 'Agreed share'
        assert transaction.date.date().isoformat() == '2026-02-05'
        assert float(db.session.get(Wallet, wallet.id).balance) == 125.0

        foreign_txn = EquityTransaction(user_id=other_user.id, equity_capital_id=foreign_capital.id,
            transaction_type='injection', amount=10, wallet_id=foreign_wallet.id)
        db.session.add(foreign_txn); db.session.commit()
        assert client.post(f'/equity/transaction/delete/{foreign_txn.id}').status_code == 404


def test_allocations_validate_sources_and_do_not_move_cash_or_equity(app, client, db):
    with app.app_context():
        user, wallet, capital, project, _ = _setup(app, db)
        other_user = User(email='allocation-owner@example.com', name='Allocation Owner')
        other_user.set_password('test-password')
        db.session.add(other_user); db.session.flush()
        foreign_category = ProjectCategory(user_id=other_user.id, name='Foreign allocation category')
        db.session.add(foreign_category); db.session.flush()
        foreign_project = Project(user_id=other_user.id, category_id=foreign_category.id,
                                  name='Foreign project', funding_source='other')
        foreign_capital = EquityCapital(user_id=other_user.id, category_id=foreign_category.id, initial_capital=100)
        db.session.add_all([foreign_project, foreign_capital]); db.session.commit()
        _login(client, user)

        invalid_requests = (
            {'allocation_type': 'invalid', 'funding_source': 'capital', 'amount': '10'},
            {'allocation_type': 'reinvestment', 'funding_source': 'invalid', 'amount': '10'},
            {'allocation_type': 'reinvestment', 'funding_source': 'capital', 'amount': '0'},
            {'allocation_type': 'project_funding', 'funding_source': 'capital', 'amount': '10'},
            {'allocation_type': 'project_funding', 'funding_source': 'capital', 'amount': '10',
             'project_id': str(foreign_project.id)},
            {'allocation_type': 'reinvestment', 'funding_source': 'capital', 'amount': '10', 'date': 'bad-date'},
        )
        for data in invalid_requests:
            assert client.post(f'/equity/allocate/{capital.id}', data=data).status_code == 302
        assert CapitalAllocation.query.filter_by(user_id=user.id).count() == 0

        before_wallet = float(db.session.get(Wallet, wallet.id).balance)
        before_equity = capital.total_equity
        assert client.post(f'/equity/allocate/{capital.id}', data={
            'allocation_type': 'reinvestment', 'funding_source': 'capital', 'amount': '200',
            'date': '2026-03-02', 'description': 'Next stock order', 'notes': 'No project selected',
        }).status_code == 302
        allocation = CapitalAllocation.query.filter_by(user_id=user.id).one()
        assert allocation.project_id is None
        assert allocation.date.date().isoformat() == '2026-03-02'
        assert allocation.description == 'Next stock order'
        assert allocation.notes == 'No project selected'
        assert float(db.session.get(Wallet, wallet.id).balance) == before_wallet
        assert capital.total_equity == before_equity
        assert capital.available_contributed_capital == 800
        assert client.post(f'/equity/allocation/delete/{allocation.id}').status_code == 302
        assert float(db.session.get(Wallet, wallet.id).balance) == before_wallet
        assert capital.total_equity == before_equity
        assert capital.available_contributed_capital == 1000

        foreign_allocation = CapitalAllocation(user_id=other_user.id, equity_capital_id=foreign_capital.id,
            allocation_type='reinvestment', funding_source='capital', amount=10)
        db.session.add(foreign_allocation); db.session.commit()
        assert client.post(f'/equity/allocation/delete/{foreign_allocation.id}').status_code == 404


def test_external_equity_movements_create_and_reverse_double_entry_journals(app, client, db):
    with app.app_context():
        user, wallet, capital, project, _ = _setup(app, db)
        _login(client, user)

        assert client.post(f'/equity/transaction/add/{capital.id}', data={
            'transaction_type': 'injection', 'amount': '200', 'wallet_id': str(wallet.id),
        }).status_code == 302
        injection = EquityTransaction.query.filter_by(transaction_type='injection').one()
        cash = ChartOfAccount.query.filter_by(user_id=user.id, code='1000', account_type='Asset').one()
        equity = ChartOfAccount.query.filter_by(user_id=user.id, code='3000', account_type='Equity').one()
        injection_entry = db.session.get(JournalEntry, injection.journal_entry_id)
        assert injection_entry.debit_account_id == cash.id
        assert injection_entry.credit_account_id == equity.id
        assert cash.balance == 200
        assert equity.balance == -200

        assert client.post(f'/equity/transaction/add/{capital.id}', data={
            'transaction_type': 'drawing', 'amount': '50', 'wallet_id': str(wallet.id),
        }).status_code == 302
        drawing = EquityTransaction.query.filter_by(transaction_type='drawing').one()
        drawing_entry = db.session.get(JournalEntry, drawing.journal_entry_id)
        assert drawing_entry.debit_account_id == equity.id
        assert drawing_entry.credit_account_id == cash.id
        assert cash.balance == 150
        assert equity.balance == -150
        assert client.post(f'/equity/transaction/delete/{drawing.id}').status_code == 302
        assert JournalEntry.query.filter_by(id=drawing_entry.id).count() == 0
        assert cash.balance == 200
        assert equity.balance == -200

        before_journals = JournalEntry.query.count()
        assert client.post(f'/equity/allocate/{capital.id}', data={
            'allocation_type': 'project_funding', 'funding_source': 'capital', 'amount': '100',
            'project_id': str(project.id),
        }).status_code == 302
        assert JournalEntry.query.count() == before_journals

        assert client.post(f'/equity/transaction/delete/{injection.id}').status_code == 302
        assert JournalEntry.query.count() == 0
        assert cash.balance == 0
        assert equity.balance == 0


def test_equity_routes_update_wallet_and_reject_cross_category_allocation(app, client, db):
    with app.app_context():
        user, wallet, capital, project, other_project = _setup(app, db)
        _login(client, user)
        response = client.post(f'/equity/transaction/add/{capital.id}', data={
            'transaction_type': 'injection', 'amount': '200', 'wallet_id': str(wallet.id),
        })
        assert response.status_code == 302
        assert float(db.session.get(Wallet, wallet.id).balance) == 300.0
        assert EquityTransaction.query.count() == 1
        assert client.post(f'/equity/transaction/add/{capital.id}', data={
            'transaction_type': 'partner_contribution', 'amount': '50', 'wallet_id': str(wallet.id), 'partner_name': 'Ama',
        }).status_code == 302
        assert float(db.session.get(Wallet, wallet.id).balance) == 350.0

        response = client.post(f'/equity/allocate/{capital.id}', data={
            'allocation_type': 'project_funding', 'funding_source': 'capital', 'amount': '300', 'project_id': str(project.id),
        })
        assert response.status_code == 302
        assert CapitalAllocation.query.count() == 1

        response = client.post(f'/equity/allocate/{capital.id}', data={
            'allocation_type': 'project_funding', 'funding_source': 'capital', 'amount': '951', 'project_id': str(project.id),
        })
        assert response.status_code == 302
        assert CapitalAllocation.query.count() == 1

        response = client.post(f'/equity/transaction/add/{capital.id}', data={
            'transaction_type': 'drawing', 'amount': '50', 'wallet_id': str(wallet.id),
        })
        drawing = EquityTransaction.query.filter_by(transaction_type='drawing').one()
        assert float(db.session.get(Wallet, wallet.id).balance) == 300.0
        assert client.post(f'/equity/transaction/delete/{drawing.id}').status_code == 302
        assert float(db.session.get(Wallet, wallet.id).balance) == 350.0
        response = client.post(f'/equity/allocate/{capital.id}', data={
            'allocation_type': 'project_funding', 'funding_source': 'capital', 'amount': '50', 'project_id': str(other_project.id),
        })
        assert response.status_code == 302
        assert CapitalAllocation.query.count() == 1


def test_retained_earnings_allocation_limit(app, client, db):
    with app.app_context():
        user, _, capital, project, _ = _setup(app, db)
        _login(client, user)
        income = ProjectItem(user_id=user.id, project_id=project.id, item_name='Sale', cost=300, item_type='income')
        db.session.add(income); db.session.flush()
        db.session.add(ProjectItemPayment(user_id=user.id, project_item_id=income.id, amount=300, is_paid=True))
        db.session.commit()
        assert capital.retained_earnings == 300
        assert client.post(f'/equity/allocate/{capital.id}', data={
            'allocation_type': 'reinvestment', 'funding_source': 'retained', 'amount': '301',
        }).status_code == 302
        assert CapitalAllocation.query.count() == 0
