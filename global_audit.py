from app import create_app, db
from sqlalchemy import inspect

app = create_app()
with app.app_context():
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    
    print(f"{'Table':<30} | {'Total':<10} | {'Missing UserID':<15}")
    print("-" * 60)
    
    for table_name in tables:
        # Get columns for this table
        columns = [c['name'] for c in inspector.get_columns(table_name)]
        if 'user_id' in columns:
            total = db.session.execute(db.text(f"SELECT COUNT(*) FROM `{table_name}`")).scalar()
            missing = db.session.execute(db.text(f"SELECT COUNT(*) FROM `{table_name}` WHERE user_id IS NULL")).scalar()
            print(f"{table_name:<30} | {total:<10} | {missing:<15}")
        elif table_name == 'user':
             total = db.session.execute(db.text(f"SELECT COUNT(*) FROM `user`")).scalar()
             print(f"{table_name:<30} | {total:<10} | N/A")
