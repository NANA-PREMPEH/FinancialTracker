from app import create_app, db
from sqlalchemy import text

app = create_app()

def check_and_fix_project_table():
    with app.app_context():
        try:
            with db.engine.connect() as conn:
                # Check if table exists and what columns it has
                result = conn.execute(text("DESCRIBE project"))
                print("Current project table structure:")
                for row in result:
                    print(row)
                
                print("\n" + "="*50 + "\n")
                
                # Drop and recreate the tables
                print("Dropping existing tables...")
                conn.execute(text("DROP TABLE IF EXISTS project_item"))
                conn.execute(text("DROP TABLE IF EXISTS project"))
                
                print("Creating project table...")
                conn.execute(text("""
                    CREATE TABLE project (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        name VARCHAR(200) NOT NULL,
                        funding_source VARCHAR(100) NOT NULL,
                        wallet_id INT,
                        custom_funding_source VARCHAR(200),
                        created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                        is_completed TINYINT(1) DEFAULT 0,
                        FOREIGN KEY (wallet_id) REFERENCES wallet (id)
                    )
                """))
                
                print("Creating project_item table...")
                conn.execute(text("""
                    CREATE TABLE project_item (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        project_id INT NOT NULL,
                        item_name VARCHAR(200) NOT NULL,
                        cost FLOAT NOT NULL DEFAULT 0.0,
                        is_completed TINYINT(1) DEFAULT 0,
                        created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (project_id) REFERENCES project (id) ON DELETE CASCADE
                    )
                """))
                
                print("\nTables recreated successfully!")
                
                # Verify the new structure
                result = conn.execute(text("DESCRIBE project"))
                print("\nNew project table structure:")
                for row in result:
                    print(row)
                    
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    check_and_fix_project_table()
