import csv
import io
import json
from datetime import datetime

from flask import Blueprint, Response, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, logout_user

from . import db
from .models import (
    AuditLog, Budget, Category, Creditor, Expense, Goal,
    Investment, SecurityEvent, User, Wallet, ExchangeRate,
)
from .utils import get_exchange_rate

settings_bp = Blueprint('settings', __name__)

CURRENCIES = [
    ('GHS', 'Ghana Cedi'),
    ('USD', 'US Dollar'),
    ('EUR', 'Euro'),
    ('GBP', 'British Pound'),
    ('NGN', 'Nigerian Naira'),
    ('KES', 'Kenyan Shilling'),
    ('ZAR', 'South African Rand'),
    ('XOF', 'West African CFA'),
    ('CAD', 'Canadian Dollar'),
    ('AUD', 'Australian Dollar'),
]


def _get_notification_prefs():
    """Get notification preferences from session (no migration needed)."""
    return session.get('notification_prefs', {
        'budget_alerts': True,
        'goal_reminders': True,
        'login_alerts': True,
        'payment_due': True,
        'weekly_summary': False,
        'email_notifications': True,
        'push_notifications': False,
    })


@settings_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'update_profile':
            current_user.name = request.form.get('name', current_user.name).strip()
            new_email = request.form.get('email', '').strip().lower()
            if new_email and new_email != current_user.email:
                if User.query.filter_by(email=new_email).first():
                    flash('Email already in use.', 'error')
                    return redirect(url_for('settings.settings'))
                current_user.email = new_email
            current_user.default_currency = request.form.get('default_currency', 'GHS')
            current_user.theme_preference = request.form.get('theme_preference', 'system')
            db.session.commit()
            flash('Profile updated successfully.', 'success')

        elif action == 'change_password':
            current_password = request.form.get('current_password', '')
            new_password = request.form.get('new_password', '')
            confirm_password = request.form.get('confirm_password', '')

            if not current_user.check_password(current_password):
                flash('Current password is incorrect.', 'error')
            elif len(new_password) < 6:
                flash('New password must be at least 6 characters.', 'error')
            elif new_password != confirm_password:
                flash('New passwords do not match.', 'error')
            else:
                current_user.set_password(new_password)
                db.session.commit()
                flash('Password changed successfully.', 'success')

        elif action == 'update_notifications':
            prefs = {
                'budget_alerts': 'budget_alerts' in request.form,
                'goal_reminders': 'goal_reminders' in request.form,
                'login_alerts': 'login_alerts' in request.form,
                'payment_due': 'payment_due' in request.form,
                'weekly_summary': 'weekly_summary' in request.form,
                'email_notifications': 'email_notifications' in request.form,
                'push_notifications': 'push_notifications' in request.form,
            }
            session['notification_prefs'] = prefs
            flash('Notification preferences saved.', 'success')

        elif action == 'delete_account':
            password = request.form.get('delete_password', '')
            confirm_text = request.form.get('delete_confirm', '').strip()
            if not current_user.check_password(password):
                flash('Incorrect password.', 'error')
            elif confirm_text != 'DELETE':
                flash('Please type DELETE to confirm account deletion.', 'error')
            else:
                uid = current_user.id
                # Delete all user data in order
                for model in [SecurityEvent, AuditLog, Budget, Goal, Investment,
                              Creditor, Expense, Category, Wallet]:
                    model.query.filter_by(user_id=uid).delete()
                User.query.filter_by(id=uid).delete()
                db.session.commit()
                logout_user()
                flash('Your account and all data have been permanently deleted.', 'success')
                return redirect(url_for('auth.login'))

        return redirect(url_for('settings.settings'))

    notification_prefs = _get_notification_prefs()
    return render_template('settings.html',
                           currencies=CURRENCIES,
                           notification_prefs=notification_prefs)


@settings_bp.route('/settings/export-data')
@login_required
def export_data():
    """Export all user data as JSON (GDPR-style)."""
    uid = current_user.id

    expenses = Expense.query.filter_by(user_id=uid).all()
    wallets = Wallet.query.filter_by(user_id=uid).all()
    categories = Category.query.filter_by(user_id=uid).all()
    budgets = Budget.query.filter_by(user_id=uid).all()
    goals = Goal.query.filter_by(user_id=uid).all()
    creditors = Creditor.query.filter_by(user_id=uid).all()
    investments = Investment.query.filter_by(user_id=uid).all()

    data = {
        'exported_at': datetime.utcnow().isoformat(),
        'user': {
            'name': current_user.name,
            'email': current_user.email,
            'currency': current_user.default_currency,
            'created_at': current_user.created_at.isoformat() if current_user.created_at else None,
        },
        'wallets': [{
            'name': w.name, 'balance': w.balance, 'currency': w.currency,
        } for w in wallets],
        'categories': [{
            'name': c.name, 'type': c.type if hasattr(c, 'type') else None,
        } for c in categories],
        'transactions': [{
            'date': e.date.isoformat() if e.date else None,
            'description': e.description, 'amount': e.amount,
            'type': e.transaction_type,
            'category': e.category.name if e.category else None,
        } for e in expenses],
        'budgets': [{
            'category': b.category.name if b.category else None,
            'amount': b.amount, 'is_active': b.is_active,
        } for b in budgets],
        'goals': [{
            'name': g.name, 'target_amount': g.target_amount,
            'current_amount': g.current_amount, 'status': g.status,
        } for g in goals],
        'creditors': [{
            'name': c.name, 'amount': c.amount,
            'interest_rate': c.interest_rate, 'debt_type': c.debt_type,
        } for c in creditors],
        'investments': [{
            'name': i.name if hasattr(i, 'name') else None,
            'current_value': i.current_value,
        } for i in investments],
    }

    output = json.dumps(data, indent=2, default=str)
    return Response(
        output,
        mimetype='application/json',
        headers={'Content-Disposition': f'attachment; filename=fintracker_data_{datetime.utcnow().strftime("%Y%m%d")}.json'}
    )


@settings_bp.route('/settings/export-csv')
@login_required
def export_data_csv():
    """Export all transactions as CSV."""
    uid = current_user.id
    expenses = Expense.query.filter_by(user_id=uid).order_by(Expense.date.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Date', 'Description', 'Amount', 'Type', 'Category'])
    for e in expenses:
        writer.writerow([
            e.date.strftime('%Y-%m-%d') if e.date else '',
            e.description or '',
            e.amount,
            e.transaction_type,
            e.category.name if e.category else '',
        ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=transactions_{datetime.utcnow().strftime("%Y%m%d")}.csv'}
    )


@settings_bp.route('/settings/exchange-rates', methods=['GET', 'POST'])
@login_required
def exchange_rates():
    """Manage exchange rates - view, add manually, or auto-fetch."""
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add_manual':
            from_currency = request.form.get('from_currency', '').strip().upper()
            to_currency = request.form.get('to_currency', '').strip().upper()
            rate = request.form.get('rate')
            
            if not from_currency or not to_currency or not rate:
                flash('All fields are required.', 'error')
            else:
                try:
                    rate = float(rate)
                    if rate <= 0:
                        flash('Rate must be greater than 0.', 'error')
                    else:
                        # Check if rate already exists
                        existing = ExchangeRate.query.filter_by(
                            from_currency=from_currency,
                            to_currency=to_currency
                        ).first()
                        
                        if existing:
                            existing.rate = rate
                            existing.date = datetime.utcnow()
                            flash(f'Exchange rate {from_currency}/{to_currency} updated.', 'success')
                        else:
                            new_rate = ExchangeRate(
                                from_currency=from_currency,
                                to_currency=to_currency,
                                rate=rate
                            )
                            db.session.add(new_rate)
                            flash(f'Exchange rate {from_currency}/{to_currency} added.', 'success')
                        db.session.commit()
                except ValueError:
                    flash('Invalid rate value.', 'error')
        
        elif action == 'delete':
            rate_id = request.form.get('rate_id')
            rate = ExchangeRate.query.get(rate_id)
            if rate:
                db.session.delete(rate)
                db.session.commit()
                flash('Exchange rate deleted.', 'success')
        
        elif action == 'refresh_all':
            # Refresh all common currency rates to GHS
            currencies = ['USD', 'EUR', 'GBP', 'NGN', 'KES', 'ZAR']
            refreshed = 0
            for curr in currencies:
                try:
                    rate = get_exchange_rate(curr, 'GHS')
                    if rate > 0:
                        refreshed += 1
                except Exception:
                    pass
            flash(f'Refreshed {refreshed} exchange rates.', 'success')
        
        return redirect(url_for('settings.exchange_rates'))
    
    # Get all exchange rates
    rates = ExchangeRate.query.order_by(ExchangeRate.from_currency, ExchangeRate.to_currency).all()
    return render_template('exchange_rates.html', rates=rates, currencies=CURRENCIES)
