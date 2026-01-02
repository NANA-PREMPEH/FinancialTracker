
from app import create_app, db
from sqlalchemy import text

app = create_app()

def upgrade_db_mysql():
    with app.app_context():
        print("Connecting to database...")
        # Use raw connection to avoid transaction block issues if any, though SQLAlchemy text() is usually fine
        with db.engine.connect() as conn:
            # Check if columns exist first to avoid error? Or just try/except
            
            print("Adding original_amount column...")
            try:
                conn.execute(text("ALTER TABLE expense ADD COLUMN original_amount FLOAT"))
                print("original_amount added.")
            except Exception as e:
                print(f"Skipping original_amount: {e}")

            print("Adding original_currency column...")
            try:
                conn.execute(text("ALTER TABLE expense ADD COLUMN original_currency VARCHAR(10)"))
                print("original_currency added.")
            except Exception as e:
                print(f"Skipping original_currency: {e}")
                
            conn.commit()
            print("Migration complete.")

if __name__ == "__main__":
    upgrade_db_mysql()
