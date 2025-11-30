from app import create_app, db
from sqlalchemy import text

app = create_app()

def add_project_tables():
    with app.app_context():
        try:
            with db.engine.connect() as conn:
                # Create Project table
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS project (
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
                
                # Create ProjectItem table
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS project_item (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        project_id INT NOT NULL,
                        item_name VARCHAR(200) NOT NULL,
                        cost FLOAT NOT NULL DEFAULT 0.0,
                        is_completed TINYINT(1) DEFAULT 0,
                        created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (project_id) REFERENCES project (id) ON DELETE CASCADE
                    )
                """))
                
            print("Successfully created project and project_item tables.")
        except Exception as e:
            print(f"Error creating tables: {e}")

if __name__ == "__main__":
    add_project_tables()
