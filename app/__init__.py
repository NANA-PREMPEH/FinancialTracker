from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from .mail import mail
import os

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'fintracker-secret-key-2026')
    app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:root@localhost/fintrackdb'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Flask-Mail configuration
    app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
    app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
    app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@fintracker.app')

    # VAPID keys for Web Push notifications
    app.config['VAPID_PRIVATE_KEY'] = os.environ.get('VAPID_PRIVATE_KEY')
    app.config['VAPID_PUBLIC_KEY'] = os.environ.get('VAPID_PUBLIC_KEY', '')
    app.config['VAPID_CLAIMS_EMAIL'] = os.environ.get('VAPID_CLAIMS_EMAIL', 'mailto:admin@fintracker.app')

    # Google OAuth configuration
    app.config['GOOGLE_CLIENT_ID'] = os.environ.get('GOOGLE_CLIENT_ID')
    app.config['GOOGLE_CLIENT_SECRET'] = os.environ.get('GOOGLE_CLIENT_SECRET')

    db.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)

    from .oauth import init_oauth
    init_oauth(app)

    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'error'

    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register all blueprints
    from .routes import main
    from .auth import auth
    from .routes_settings import settings_bp
    from .routes_goals import goals_bp
    from .routes_calendar import calendar_bp
    from .routes_investments import investments_bp
    from .routes_networth import networth_bp
    from .routes_cashflow import cashflow_bp
    from .routes_commitments import commitments_bp
    from .routes_notifications import notifications_bp
    from .routes_ai_insights import ai_insights_bp
    from .routes_automation import automation_bp
    from .routes_banking import banking_bp
    from .routes_accounting import accounting_bp
    from .routes_security import security_bp
    from .routes_backup import backup_bp
    from .routes_admin import admin_bp
    from .routes_fixed_assets import fixed_assets_bp
    from .routes_budget_planning import budget_planning_bp
    from .routes_newsletter import newsletter_bp
    from .routes_api_keys import api_keys_bp
    from .routes_domain import domain_bp
    from .routes_advanced import advanced_bp
    from .api import api_bp
    from .routes_push import push_bp

    app.register_blueprint(main)
    app.register_blueprint(auth)
    app.register_blueprint(settings_bp)
    app.register_blueprint(goals_bp)
    app.register_blueprint(calendar_bp)
    app.register_blueprint(investments_bp)
    app.register_blueprint(networth_bp)
    app.register_blueprint(cashflow_bp)
    app.register_blueprint(commitments_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(ai_insights_bp)
    app.register_blueprint(automation_bp)
    app.register_blueprint(banking_bp)
    app.register_blueprint(accounting_bp)
    app.register_blueprint(security_bp)
    app.register_blueprint(backup_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(fixed_assets_bp)
    app.register_blueprint(budget_planning_bp)
    app.register_blueprint(newsletter_bp)
    app.register_blueprint(api_keys_bp)
    app.register_blueprint(domain_bp)
    app.register_blueprint(advanced_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(push_bp)

    # Serve service worker from root scope
    @app.route('/sw.js')
    def service_worker():
        return app.send_static_file('sw.js'), 200, {
            'Content-Type': 'application/javascript',
            'Service-Worker-Allowed': '/'
        }

    return app
