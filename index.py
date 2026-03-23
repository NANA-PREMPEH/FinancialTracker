from dotenv import load_dotenv
load_dotenv()

from app import create_app, db
from run import init_db
import os

# Create the Flask application instance
app = create_app()

# Initialize the database and tables if they don't exist
with app.app_context():
    db.create_all()
    init_db(app)

if __name__ == '__main__':
    # This block is for local development only
    app.run(debug=True, port=int(os.environ.get('PORT', 5001)))
