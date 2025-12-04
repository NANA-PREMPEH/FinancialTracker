"""
This script creates the project_item_payment table directly in the database
"""

from app import create_app, db

app = create_app()

with app.app_context():
    # Create the project_item_payment table using raw SQL
    sql = """
    CREATE TABLE IF NOT EXISTS project_item_payment (
        id INT AUTO_INCREMENT PRIMARY KEY,
        project_item_id INT NOT NULL,
        amount FLOAT NOT NULL,
        description VARCHAR(200),
        is_paid BOOLEAN DEFAULT FALSE,
        payment_date DATETIME,
        created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (project_item_id) REFERENCES project_item(id) ON DELETE CASCADE,
        CHECK (is_paid IN (0, 1))
    )
    """
    
    try:
        db.session.execute(db.text(sql))
        db.session.commit()
        print("SUCCESS: Created project_item_payment table!")
    except Exception as e:
        db.session.rollback()
        print(f"Error: {e}")
        print("The table might already exist or there's a different issue.")
