def test_creditors_list_shows_received_date():
    """Creditor cards should show the date the borrowed money was received."""
    from app import create_app, db
    from app.models import Creditor, User, Wallet

    app = create_app('testing')

    with app.app_context():
        db.create_all()
        try:
            user = User(
                email='creditor-test@example.com',
                name='Creditor Tester',
            )
            user.set_password('testpassword123')
            db.session.add(user)
            db.session.commit()
            wallet = Wallet(
                user_id=user.id,
                name='Cash Wallet',
                balance=1000.00,
                currency='GHS',
            )
            db.session.add(wallet)
            db.session.commit()
            user_id = user.id

            client = app.test_client()
            with client.session_transaction() as sess:
                sess['_user_id'] = str(user_id)
                sess['_fresh'] = True

            response = client.post('/creditors/add', data={
                'name': 'Family Loan',
                'amount': '500.00',
                'date': '2026-03-05',
            }, follow_redirects=True)
            response = client.post('/creditors/add', data={
                'name': 'Family Loan',
                'amount': '250.00',
                'date': '2026-03-08',
            }, follow_redirects=True)
            creditors = Creditor.query.filter_by(
                user_id=user_id,
                name='Family Loan',
            ).all()

            assert response.status_code == 200
            assert len(creditors) == 2
            assert any(creditor.created_at.strftime('%Y-%m-%d') == '2026-03-05' for creditor in creditors)
            assert b'Hide Amounts' in response.data
            assert b'data-creditor-figure' in response.data
            assert b'data-creditor-wallet-option' in response.data
            assert b'Totals by Creditor' in response.data
            assert b'2 debt records' in response.data
            assert b'GHS 750.00' in response.data
            assert b'Received Date' in response.data
            assert b'Mar 05, 2026' in response.data
        finally:
            db.session.remove()
            db.drop_all()


def test_creditor_edit_and_delete_reconcile_linked_wallet_transaction(app, db, authenticated_client):
    """A wallet-funded creditor must not leave a ghost transaction behind."""
    from app import db as database
    from app.models import Creditor, Expense, User, Wallet

    with app.app_context():
        user = User.query.filter_by(email='test@example.com').one()
        wallet = Wallet(user_id=user.id, name='Cash', balance=100.0, currency='GHS')
        database.session.add(wallet)
        database.session.commit()

        response = authenticated_client.post('/creditors/add', data={
            'name': 'Linked loan', 'amount': '50', 'wallet_id': str(wallet.id),
            'date': '2026-08-01',
        })
        assert response.status_code == 302
        creditor = Creditor.query.filter_by(user_id=user.id, name='Linked loan').one()
        transaction = Expense.query.filter_by(creditor_id=creditor.id).one()
        assert float(Wallet.query.get(wallet.id).balance) == 150.0

        response = authenticated_client.post(f'/creditors/edit/{creditor.id}', data={
            'name': 'Renamed loan', 'amount': '75', 'original_amount': '75',
            'date': '2026-08-02',
        })
        assert response.status_code == 302
        database.session.refresh(transaction)
        assert transaction.description == 'Loan from Renamed loan'
        assert transaction.amount == 75.0
        assert transaction.transaction_type == 'liability'
        assert float(Wallet.query.get(wallet.id).balance) == 175.0

        response = authenticated_client.post(f'/creditors/delete/{creditor.id}')
        assert response.status_code == 302
        assert Expense.query.filter_by(id=transaction.id).first() is None
        assert float(Wallet.query.get(wallet.id).balance) == 100.0


def test_deleting_creditor_payment_transaction_restores_debt(app, db, authenticated_client):
    """Deleting a payment on the transactions page reverses its creditor effect."""
    from app import db as database
    from app.models import Creditor, DebtPayment, Expense, User, Wallet

    with app.app_context():
        user = User.query.filter_by(email='test@example.com').one()
        wallet = Wallet(user_id=user.id, name='Cash', balance=100.0, currency='GHS')
        creditor = Creditor(user_id=user.id, name='Card', amount=80.0, original_amount=80.0)
        database.session.add_all([wallet, creditor])
        database.session.commit()

        response = authenticated_client.post(f'/creditors/pay/{creditor.id}', data={
            'wallet_id': str(wallet.id), 'amount': '30', 'date': '2026-08-03',
        })
        assert response.status_code == 302
        payment = DebtPayment.query.filter_by(creditor_id=creditor.id).one()
        assert payment.expense_id is not None
        payment_expense_id = payment.expense_id
        assert float(Creditor.query.get(creditor.id).amount) == 50.0
        assert float(Wallet.query.get(wallet.id).balance) == 70.0

        response = authenticated_client.post(f'/delete/{payment_expense_id}')
        assert response.status_code == 302
        assert DebtPayment.query.filter_by(id=payment.id).first() is None
        assert float(Creditor.query.get(creditor.id).amount) == 80.0
        assert float(Wallet.query.get(wallet.id).balance) == 100.0
        assert Expense.query.filter_by(id=payment_expense_id).first() is None


def test_deleting_creditor_never_matches_transactions_by_name_and_amount(app, db, authenticated_client):
    """Same-name, same-value records must remain independent."""
    from app import db as database
    from app.models import Category, Creditor, Expense, User, Wallet

    with app.app_context():
        user = User.query.filter_by(email='test@example.com').one()
        wallet = Wallet(user_id=user.id, name='Cash', balance=15000.0, currency='GHS')
        category = Category(user_id=user.id, name='Loan Received', is_custom=True)
        target = Creditor(user_id=user.id, name='Ata', amount=5000.0, original_amount=5000.0)
        other = Creditor(user_id=user.id, name='Ata', amount=5000.0, original_amount=5000.0)
        database.session.add_all([wallet, category, target, other])
        database.session.flush()
        target_transaction = Expense(
            user_id=user.id, amount=5000.0, description='Loan from Ata',
            category_id=category.id, wallet_id=wallet.id, transaction_type='liability',
            tags='loan_received', creditor_id=target.id,
        )
        unrelated_transaction = Expense(
            user_id=user.id, amount=5000.0, description='Loan from Ata',
            category_id=category.id, wallet_id=wallet.id, transaction_type='liability',
            tags='loan_received', creditor_id=other.id,
        )
        database.session.add_all([target_transaction, unrelated_transaction])
        database.session.commit()

        response = authenticated_client.post(f'/creditors/delete/{target.id}')
        assert response.status_code == 302
        assert Expense.query.filter_by(id=target_transaction.id).first() is None
        assert Expense.query.filter_by(id=unrelated_transaction.id).first() is not None


def test_creditor_edit_syncs_the_linked_transaction_details(app, db, authenticated_client):
    """Creditor details must be reflected in its linked loan receipt."""
    from app import db as database
    from app.models import Category, Creditor, Expense, User, Wallet

    with app.app_context():
        user = User.query.filter_by(email='test@example.com').one()
        wallet = Wallet(user_id=user.id, name='Cash', balance=0.0, currency='GHS')
        category = Category(user_id=user.id, name='Loan Received', is_custom=True)
        creditor = Creditor(user_id=user.id, name='Ata', amount=5000.0, original_amount=5000.0)
        database.session.add_all([wallet, category, creditor])
        database.session.flush()
        transaction = Expense(
            user_id=user.id, amount=5000.0, description='Loan from Ata',
            category_id=category.id, wallet_id=wallet.id, transaction_type='expense',
            tags='loan_received', creditor_id=creditor.id,
        )
        database.session.add(transaction)
        database.session.commit()

        response = authenticated_client.post(f'/creditors/edit/{creditor.id}', data={
            'name': 'Ata', 'amount': '5000', 'original_amount': '5000',
            'description': '13th payment by his wife', 'date': '2026-08-06',
        })
        assert response.status_code == 302
        database.session.refresh(transaction)
        assert transaction.description == '13th payment by his wife'
        assert transaction.transaction_type == 'liability'
        assert transaction.date.strftime('%Y-%m-%d') == '2026-08-06'
