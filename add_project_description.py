from app import create_app, db
from sqlalchemy import text

app = create_app()

def add_description_column():
    with app.app_context():
        try:
            with db.engine.connect() as conn:
                # Add description column to project table
                conn.execute(text("""
                    ALTER TABLE project 
                    ADD COLUMN description TEXT NULL
                """))
                
                print("Successfully added description column to project table.")
        except Exception as e:
            print(f"Error adding column: {e}")

if __name__ == "__main__":
    add_description_column()
