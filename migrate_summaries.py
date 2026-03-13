from app import create_app, db
from app.models import FinancialSummary, User

app = create_app()
with app.app_context():
    users = User.query.all()
    print(f"Total users: {len(users)}")
    for u in users:
        print(f"User ID: {u.id}, Email: {u.email}")
    
    if len(users) == 1:
        target_user_id = users[0].id
        orphaned = FinancialSummary.query.filter_by(user_id=None).all()
        print(f"Migrating {len(orphaned)} records to User ID: {target_user_id}")
        for s in orphaned:
            s.user_id = target_user_id
        db.session.commit()
        print("Migration complete.")
    else:
        print("Multiple users found. Manual migration required or different logic needed.")
