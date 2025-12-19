from app import create_app, db
from app.models import Wallet, Project

app = create_app()

with app.app_context():
    wallets = Wallet.query.all()
    print("Wallets:")
    for w in wallets:
        print(f"ID: {w.id}, Name: {w.name}, Currency: {w.currency}")

    projects = Project.query.all()
    print("\nProjects:")
    for p in projects:
        print(f"ID: {p.id}, Name: {p.name}")
