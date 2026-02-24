from app import create_app, db
from app.models import User, Creditor, Project, ProjectItem
from sqlalchemy import func

def audit_liabilities():
    app = create_app()
    with app.app_context():
        users = User.query.all()
        print(f"Auditing {len(users)} user(s)...")
        
        for user in users:
            print(f"\nUser: {user.email} (ID: {user.id})")
            print("-" * 50)
            
            # 1. Creditors
            creditors = Creditor.query.filter_by(user_id=user.id).all()
            user_creditor_total = 0
            print("Creditors (Direct Debt):")
            for c in creditors:
                print(f"  - {c.name}: {c.amount} {c.currency} (Created: {c.created_at})")
                user_creditor_total += c.amount
            print(f"Total Creditor Debt: {user_creditor_total:.2f}")
            
            # 2. Unpaid Project Items
            print("\nProjects (Unpaid Items):")
            projects = Project.query.filter_by(user_id=user.id).all()
            unpaid_project_total = 0
            for p in projects:
                for item in p.items:
                    if item.item_type != 'income':
                        # cost - total_paid
                        paid = sum(pmt.amount for pmt in item.payments if pmt.is_paid)
                        unpaid = item.cost - paid
                        if unpaid > 0:
                            print(f"  - Project [{p.name}] Item [{item.item_name}]: {unpaid:.2f} unpaid (Cost: {item.cost})")
                            unpaid_project_total += unpaid
            print(f"Total Unpaid Project Costs: {unpaid_project_total:.2f}")
            
            print(f"\nCombined Potential Liabilities for {user.email}: {user_creditor_total + unpaid_project_total:.2f}")
            print("-" * 50)

if __name__ == "__main__":
    audit_liabilities()
