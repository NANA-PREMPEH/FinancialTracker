import os
from dotenv import load_dotenv
load_dotenv()

from app import create_app
from app.db_bootstrap import bootstrap_database

def init_db(app):
    """Initialize an empty configured database with the current schema."""
    with app.app_context():
        bootstrap_database()

if __name__ == '__main__':
    app = create_app()
    init_db(app)
    app.run(debug=True, port=int(os.environ.get('PORT', 5001)))

