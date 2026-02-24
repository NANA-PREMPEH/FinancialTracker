from app import create_app, db
from app.models import User, Creditor

def fix_and_audit():
    app = create_app()
    with app.app_context():
        user = User.query.filter_by(email='oseiprempehwilliams@gmail.com').first()
        if not user:
            print("User not found.")
            return

        # Orphaned record
        orphaned = Creditor.query.filter(Creditor.user_id == None, Creditor.amount == 10000.0).first()
        if orphaned:
            print(f"Found orphaned record: ID {orphaned.id}, Name: {orphaned.name}, Amount: {orphaned.amount}")
            orphaned.user_id = user.id
            db.session.commit()
            print(f"Successfully assigned record {orphaned.id} to User {user.id}")
        else:
            print("No orphaned record found.")

        # Re-audit
        print("\nUpdated Audit for oseiprempehwilliams@gmail.com:")
        creditors = Creditor.query.filter_by(user_id=user.id).all()
        total = 0
        for c in creditors:
            print(f"  - ID: {c.id}, Name: {c.name}, Amount: {c.amount} GHS")
            total += c.amount
        print(f"Total Liabilities: {total:.2f} GHS")

if __name__ == "__main__":
    fix_and_audit()
