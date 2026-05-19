from dotenv import load_dotenv
load_dotenv()

from app import create_app, db
from run import init_db
import os

from sqlalchemy import inspect
from flask_migrate import upgrade, stamp

# Create the Flask application instance
app = create_app()

# Initialize the database and tables if they don't exist
with app.app_context():
    # First, create tables if they do not exist
    db.create_all()
    
    # Check database migration status programmatically
    try:
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        
        # Check if 'alembic_version' exists
        if 'alembic_version' not in tables:
            # If the database was initialized without Alembic (e.g. via db.create_all()),
            # but tables exist, we need to stamp the migration history.
            if 'expense' in tables:
                columns = [c['name'] for c in inspector.get_columns('expense')]
                if 'income_source' not in columns:
                    # 'expense' table exists but is missing 'income_source'.
                    # Stamp to the revision right before it: '566f01fc9d16'
                    print("Tables exist but 'income_source' is missing. Stamping to '566f01fc9d16'...")
                    stamp(revision='566f01fc9d16')
                else:
                    # 'expense' table exists and already has 'income_source'.
                    # Stamp to the latest revision: 'c9f4a8b2e1d7'
                    print("Tables exist and 'income_source' is present. Stamping to 'c9f4a8b2e1d7'...")
                    stamp(revision='c9f4a8b2e1d7')
        
        # Run upgrade to apply any pending migrations
        print("Running database upgrade...")
        upgrade()
        print("Database upgrade completed successfully.")
    except Exception as e:
        print(f"Database migration/upgrade failed: {e}")

if __name__ == '__main__':
    # This block is for local development only
    app.run(debug=True, port=int(os.environ.get('PORT', 5001)))
