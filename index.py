from app import create_app
import os

# Create the Flask application instance
# Vercel's Python runtime searches for an 'app' or 'application' object
app = create_app()

if __name__ == '__main__':
    # This block is for local development only
    app.run(debug=True, port=int(os.environ.get('PORT', 5001)))
