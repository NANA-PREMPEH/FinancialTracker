
from app import create_app, db
from app.models import Creditor

app = create_app()

with app.app_context():
    print("Creating Creditor table...")
    # This will create the table if it doesn't exist
    db.create_all()
    print("Database updated.")
