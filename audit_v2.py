from app import create_app, db
from app.models import User, Creditor, Commitment

def audit_everything():
    app = create_app()
    with app.app_context():
        user = User.query.filter_by(email='oseiprempehwilliams@gmail.com').first()
        if not user:
            print("User not found.")
            return
            
        print(f"Audit for {user.email}:")
        print("-" * 50)
        
        # 1. Creditors
        creditors = Creditor.query.filter_by(user_id=user.id).all()
        print("Creditors:")
        for c in creditors:
            print(f"  - {c.name}: {c.amount} GHS")
        
        # 2. Commitments
        commitments = Commitment.query.filter_by(user_id=user.id).all()
        print("\nCommitments:")
        for com in commitments:
            print(f"  - {com.name}: {com.amount} GHS (Category: {com.commitment_category}, Status: {com.status})")
        
        # 3. Summing them up
        total_creditor = sum(c.amount for c in creditors)
        total_commitment = sum(com.amount for com in commitments if com.status != 'paid')
        
        print("-" * 50)
        print(f"Total Creditors: {total_creditor:.2f}")
        print(f"Total Unpaid Commitments: {total_commitment:.2f}")
        print(f"Combined Liability: {total_creditor + total_commitment:.2f}")

if __name__ == "__main__":
    audit_everything()
