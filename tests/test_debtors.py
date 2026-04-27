def test_debtors_list_shows_lent_date_privacy_toggle_and_group_totals():
    """Debtor cards should show lent dates and grouped debtor totals."""
    from app import create_app, db
    from app.models import Debtor, User, Wallet

    app = create_app('testing')

    with app.app_context():
        db.create_all()
        try:
            user = User(
                email='debtor-test@example.com',
                name='Debtor Tester',
            )
            user.set_password('testpassword123')
            db.session.add(user)
            db.session.commit()

            wallet = Wallet(
                user_id=user.id,
                name='Cash Wallet',
                balance=2000.00,
                currency='GHS',
            )
            db.session.add(wallet)
            db.session.commit()
            user_id = user.id
            wallet_id = wallet.id

            client = app.test_client()
            with client.session_transaction() as sess:
                sess['_user_id'] = str(user_id)
                sess['_fresh'] = True

            response = client.post('/debtors/add', data={
                'name': 'Client Loan',
                'amount': '500.00',
                'date': '2026-03-05',
                'wallet_id': str(wallet_id),
            }, follow_redirects=True)
            response = client.post('/debtors/add', data={
                'name': 'Client Loan',
                'amount': '250.00',
                'date': '2026-03-08',
                'wallet_id': str(wallet_id),
            }, follow_redirects=True)
            debtors = Debtor.query.filter_by(
                user_id=user_id,
                name='Client Loan',
            ).all()

            assert response.status_code == 200
            assert len(debtors) == 2
            assert any(debtor.created_at.strftime('%Y-%m-%d') == '2026-03-05' for debtor in debtors)
            assert b'Hide Amounts' in response.data
            assert b'data-debtor-figure' in response.data
            assert b'data-debtor-wallet-option' in response.data
            assert b'Totals by Debtor' in response.data
            assert b'2 debt records' in response.data
            assert b'GHS 750.00' in response.data
            assert b'Lent Date' in response.data
            assert b'Mar 05, 2026' in response.data
        finally:
            db.session.remove()
            db.drop_all()
