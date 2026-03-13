from app import create_app, db
from sqlalchemy import inspect
from app.models import User

app = create_app()
with app.app_context():
    user = User.query.first()
    if not user:
        print("No user found. Create a user first.")
        exit(1)
    
    target_user_id = user.id
    print(f"Target User: {user.email} (ID: {target_user_id})")
    
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    
    for table_name in tables:
        columns = [c['name'] for c in inspector.get_columns(table_name)]
        if 'user_id' in columns:
            missing = db.session.execute(db.text(f"SELECT COUNT(*) FROM `{table_name}` WHERE user_id IS NULL")).scalar()
            if missing > 0:
                print(f"Migrating {missing} records in {table_name}...")
                db.session.execute(db.text(f"UPDATE `{table_name}` SET user_id = :uid WHERE user_id IS NULL"), {'uid': target_user_id})
    
    db.session.commit()
    print("Migration complete.")
