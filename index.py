from dotenv import load_dotenv
load_dotenv()

import os

from app import create_app
from app.db_bootstrap import bootstrap_database


app = create_app()

with app.app_context():
    bootstrap_database()


if __name__ == '__main__':
    app.run(debug=True, port=int(os.environ.get('PORT', 5001)))
