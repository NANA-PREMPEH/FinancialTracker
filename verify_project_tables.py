from app import create_app, db
from sqlalchemy import text

app = create_app()

def verify_tables():
    with app.app_context():
        try:
            with db.engine.connect() as conn:
                # Check project table
                result = conn.execute(text("DESCRIBE project"))
                print("Project table structure:")
                print("-" * 80)
                for row in result:
                    print(f"{row[0]:30} {row[1]:20} NULL:{row[2]:5} Key:{row[3]:5} Default:{row[4]}")
                
                print("\n")
                
                # Check project_item table
                result = conn.execute(text("DESCRIBE project_item"))
                print("Project_item table structure:")
                print("-" * 80)
                for row in result:
                    print(f"{row[0]:30} {row[1]:20} NULL:{row[2]:5} Key:{row[3]:5} Default:{row[4]}")
                
                print("\n✅ All tables verified successfully!")
                    
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    verify_tables()
