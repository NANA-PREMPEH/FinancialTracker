from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from . import db
from .models import ApiKey
from werkzeug.security import generate_password_hash
from datetime import datetime
import secrets

api_keys_bp = Blueprint('api_keys', __name__)

PERMISSIONS = ['read', 'write_transactions', 'write_budgets', 'write_goals', 'write_reports']


@api_keys_bp.route('/api-keys')
@login_required
def api_keys_list():
    keys = ApiKey.query.filter_by(user_id=current_user.id).order_by(ApiKey.created_at.desc()).all()
    return render_template('api_keys.html', keys=keys, permissions=PERMISSIONS)


@api_keys_bp.route('/api-keys/create', methods=['POST'])
@login_required
def create_key():
    name = request.form.get('name', '').strip()
    perms = request.form.getlist('permissions')
    raw_key = secrets.token_urlsafe(32)

    key = ApiKey(
        user_id=current_user.id,
        name=name,
        key_hash=generate_password_hash(raw_key),
        permissions=','.join(perms) if perms else 'read',
    )
    db.session.add(key)
    db.session.commit()
    flash(f'API Key created. Save this key now (shown only once): {raw_key}', 'success')
    return redirect(url_for('api_keys.api_keys_list'))


@api_keys_bp.route('/api-keys/delete/<int:id>', methods=['POST'])
@login_required
def delete_key(id):
    key = ApiKey.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    db.session.delete(key)
    db.session.commit()
    flash('API key deleted.', 'success')
    return redirect(url_for('api_keys.api_keys_list'))


@api_keys_bp.route('/api-keys/toggle/<int:id>', methods=['POST'])
@login_required
def toggle_key(id):
    key = ApiKey.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    key.is_active = not key.is_active
    db.session.commit()
    flash(f'API key {"activated" if key.is_active else "deactivated"}.', 'success')
    return redirect(url_for('api_keys.api_keys_list'))
