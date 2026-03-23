from dotenv import load_dotenv
load_dotenv()

from app import create_app, db
from app.models import Category, Wallet

def init_db(app):
    with app.app_context():
        # Create default wallet
        if not Wallet.query.first():
            default_wallet = Wallet(name='Cash', balance=0.0, icon='💵', wallet_type='cash')
            db.session.add(default_wallet)
            db.session.commit()
            print("Initialized default wallet.")
        
        # Create default categories if they don't exist
        if not Category.query.first():
            categories = [
                ('Food & Drink', '🍽️'),
                ('Transport', '🚗'),
                ('Utilities', '💡'),
                ('Entertainment', '🎬'),
                ('Health', '🏥'),
                ('Shopping', '🛍️'),
                ('Work', '👔'),
                ('Travel', '✈️'),
                ('Gifts', '🎁'),
                ('Home', '🏠'),
                ('Salary', '💵'),
                ('Allowance', '💰'),
                ('Other', '📝')
            ]
            for cat_name, icon in categories:
                db.session.add(Category(name=cat_name, icon=icon, is_custom=False))
            db.session.commit()
            print("Initialized default categories.")

if __name__ == '__main__':
    app = create_app()
    init_db(app)
    app.run(debug=True, port=int(os.environ.get('PORT', 5001)))

