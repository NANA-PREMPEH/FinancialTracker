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
