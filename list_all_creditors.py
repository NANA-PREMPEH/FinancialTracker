from app import create_app, db
from app.models import Creditor

def list_all():
    app = create_app()
    with app.app_context():
        cs = Creditor.query.all()
        for c in cs:
            print(f"ID: {c.id}, UserID: {c.user_id}, Name: {c.name}, Amount: {c.amount}")

if __name__ == "__main__":
    list_all()
