from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from . import db
from .models import User, Expense, Wallet, Goal, Investment, Budget
from sqlalchemy import func
from functools import wraps

admin_bp = Blueprint('admin', __name__)


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Admin access required.', 'error')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function


@admin_bp.route('/admin')
@login_required
@admin_required
def admin_panel():
    users = User.query.order_by(User.created_at.desc()).all()
    total_users = len(users)
    total_transactions = Expense.query.count()
    total_wallets = Wallet.query.count()

    return render_template('admin.html', users=users, total_users=total_users,
                           total_transactions=total_transactions, total_wallets=total_wallets)


@admin_bp.route('/admin/users/<int:id>/role', methods=['POST'])
@login_required
@admin_required
def change_role(id):
    user = User.query.get_or_404(id)
    if user.id == current_user.id:
        flash('Cannot change your own role.', 'error')
        return redirect(url_for('admin.admin_panel'))
    new_role = request.form.get('role', 'user')
    user.role = new_role
    db.session.commit()
    flash(f'Updated {user.name} role to {new_role}.', 'success')
    return redirect(url_for('admin.admin_panel'))


@admin_bp.route('/admin/users/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(id):
    user = User.query.get_or_404(id)
    if user.id == current_user.id:
        flash('Cannot delete your own account.', 'error')
        return redirect(url_for('admin.admin_panel'))
    db.session.delete(user)
    db.session.commit()
    flash(f'User {user.name} deleted.', 'success')
    return redirect(url_for('admin.admin_panel'))
