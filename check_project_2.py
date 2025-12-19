from app import create_app, db
from app.models import Project

app = create_app()

with app.app_context():
    p = Project.query.get(2)
    if p:
        print(f"Name: {p.name}")
        print(f"Description: {p.description}")
        print(f"Funding: {p.funding_source}")
        print(f"Items Count: {len(p.items)}")
        for i in p.items:
            print(f" - {i.item_name} ({i.cost})")
    else:
        print("Project 2 not found.")
