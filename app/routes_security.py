from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from . import db
from .models import SecurityEvent, AuditLog

security_bp = Blueprint('security', __name__)


@security_bp.route('/security')
@login_required
def security_dashboard():
    events = SecurityEvent.query.filter_by(user_id=current_user.id).order_by(SecurityEvent.created_at.desc()).limit(50).all()
    audit_logs = AuditLog.query.filter_by(user_id=current_user.id).order_by(AuditLog.created_at.desc()).limit(50).all()

    # Security score calculation
    score = 100
    has_recent_password_change = any(e.event_type == 'password_change' for e in events[:20])
    failed_logins = sum(1 for e in events if e.event_type == 'failed_login')
    if not has_recent_password_change:
        score -= 15
    if failed_logins > 5:
        score -= 15
    if not current_user.totp_enabled:
        score -= 20
    if not current_user.email_verified:
        score -= 15
    score = max(score, 0)

    return render_template('security.html', events=events, audit_logs=audit_logs, security_score=score)


@security_bp.route('/security/clear-logs', methods=['POST'])
@login_required
def clear_logs():
    if current_user.role != 'admin':
        flash('Admin access required.', 'error')
        return redirect(url_for('security.security_dashboard'))
    AuditLog.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    flash('Audit logs cleared.', 'success')
    return redirect(url_for('security.security_dashboard'))
