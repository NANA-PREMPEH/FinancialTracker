import os
from dotenv import load_dotenv
load_dotenv()

from app import create_app, db

def init_db(app):
    """Global database initialization (if any)."""
    with app.app_context():
        # Any truly global initialization can go here
        pass

if __name__ == '__main__':
    app = create_app()
    init_db(app)
    app.run(debug=True, port=int(os.environ.get('PORT', 5001)))

