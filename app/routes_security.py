import csv
import io
from collections import Counter
from datetime import datetime, timedelta

from flask import Blueprint, Response, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from . import db
from .models import ApiKey, AuditLog, SecurityEvent

security_bp = Blueprint('security', __name__)


def _parse_login_sessions(events):
    """Extract active login sessions from security events (last 30 days)."""
    sessions = []
    seen_ips = set()
    for e in events:
        if e.event_type in ('login_success', 'login') and e.ip_address:
            key = (e.ip_address, (e.details or '')[:60])
            if key not in seen_ips:
                seen_ips.add(key)
                # Parse user-agent from details if available
                ua = ''
                if e.details:
                    for part in e.details.split('|'):
                        part = part.strip()
                        if 'Mozilla' in part or 'Chrome' in part or 'Safari' in part or 'Firefox' in part:
                            ua = part
                            break
                    if not ua:
                        ua = e.details[:80]
                sessions.append({
                    'ip': e.ip_address,
                    'user_agent': ua or 'Unknown',
                    'last_active': e.created_at,
                    'event_id': e.id,
                })
    return sessions[:10]


def _detect_suspicious(events):
    """Flag suspicious activity from security events."""
    alerts = []
    if not events:
        return alerts

    # Count failed logins in last 24h
    now = datetime.utcnow()
    day_ago = now - timedelta(hours=24)
    recent_failed = [e for e in events if e.event_type in ('failed_login', 'login_failed') and e.created_at >= day_ago]
    if len(recent_failed) >= 3:
        alerts.append({
            'severity': 'high',
            'icon': 'alert-octagon',
            'title': f'{len(recent_failed)} failed login attempts in 24h',
            'message': f'Multiple failed login attempts detected from IP(s): {", ".join(set(e.ip_address or "unknown" for e in recent_failed[:5]))}.',
            'time': recent_failed[0].created_at,
        })

    # New IP detection — check if any login came from an IP not seen in older events
    login_events = [e for e in events if e.event_type in ('login_success', 'login')]
    if len(login_events) >= 2:
        old_ips = set()
        new_ips = set()
        week_ago = now - timedelta(days=7)
        for e in login_events:
            if e.ip_address:
                if e.created_at < week_ago:
                    old_ips.add(e.ip_address)
                else:
                    new_ips.add(e.ip_address)
        fresh_ips = new_ips - old_ips
        if fresh_ips and old_ips:
            for ip in list(fresh_ips)[:3]:
                alerts.append({
                    'severity': 'medium',
                    'icon': 'globe',
                    'title': f'Login from new IP: {ip}',
                    'message': 'This IP address has not been seen in your login history before last week.',
                    'time': next((e.created_at for e in login_events if e.ip_address == ip), now),
                })

    # Password change without recent login
    pw_changes = [e for e in events if e.event_type == 'password_change' and e.created_at >= day_ago]
    if pw_changes:
        alerts.append({
            'severity': 'info',
            'icon': 'key',
            'title': 'Password changed recently',
            'message': f'Your password was changed on {pw_changes[0].created_at.strftime("%d %b %Y at %H:%M")}.',
            'time': pw_changes[0].created_at,
        })

    return alerts


def _build_recommendations(user, events):
    """Dynamic security recommendations checklist."""
    recs = []

    recs.append({
        'label': 'Enable Two-Factor Authentication',
        'done': user.totp_enabled,
        'icon': 'shield-check',
        'description': 'Add TOTP-based 2FA for an extra layer of login security.',
        'action_url': url_for('auth.setup_2fa') if not user.totp_enabled else None,
    })

    recs.append({
        'label': 'Verify Email Address',
        'done': user.email_verified,
        'icon': 'mail-check',
        'description': 'Confirm your email to enable password recovery and notifications.',
        'action_url': None,
    })

    has_pw_change = any(e.event_type == 'password_change' for e in events[:50])
    recs.append({
        'label': 'Change Password Regularly',
        'done': has_pw_change,
        'icon': 'key-round',
        'description': 'Update your password periodically. No recent change detected.' if not has_pw_change else 'Password was changed recently.',
        'action_url': url_for('settings.settings') if not has_pw_change else None,
    })

    api_keys = ApiKey.query.filter_by(user_id=user.id).count()
    recs.append({
        'label': 'Review API Keys',
        'done': api_keys == 0,
        'icon': 'key',
        'description': f'You have {api_keys} active API key(s). Review and revoke unused keys.' if api_keys else 'No API keys active.',
        'action_url': None,
    })

    return recs


@security_bp.route('/security')
@login_required
def security_dashboard():
    tab = (request.args.get('tab') or 'overview').lower()
    if tab not in ('overview', 'sessions', 'events', 'audit', 'alerts'):
        tab = 'overview'

    events = SecurityEvent.query.filter_by(
        user_id=current_user.id
    ).order_by(SecurityEvent.created_at.desc()).limit(100).all()

    audit_logs = AuditLog.query.filter_by(
        user_id=current_user.id
    ).order_by(AuditLog.created_at.desc()).limit(100).all()

    # Security score
    score = 100
    has_recent_password_change = any(e.event_type == 'password_change' for e in events[:20])
    failed_logins = sum(1 for e in events if e.event_type in ('failed_login', 'login_failed'))
    if not has_recent_password_change:
        score -= 15
    if failed_logins > 5:
        score -= 15
    if not current_user.totp_enabled:
        score -= 20
    if not current_user.email_verified:
        score -= 15
    score = max(score, 0)

    # Derived data
    sessions = _parse_login_sessions(events)
    suspicious = _detect_suspicious(events)
    recommendations = _build_recommendations(current_user, events)

    # Login history stats
    login_count = sum(1 for e in events if e.event_type in ('login_success', 'login'))
    failed_count = sum(1 for e in events if e.event_type in ('failed_login', 'login_failed'))
    unique_ips = len(set(e.ip_address for e in events if e.ip_address))

    # Event type distribution
    type_counts = Counter(e.event_type for e in events)

    return render_template('security.html',
        tab=tab, events=events, audit_logs=audit_logs,
        security_score=score, sessions=sessions,
        suspicious=suspicious, recommendations=recommendations,
        login_count=login_count, failed_count=failed_count,
        unique_ips=unique_ips, type_counts=dict(type_counts),
    )


@security_bp.route('/security/export-csv')
@login_required
def export_security_csv():
    """Export all security events and audit logs as CSV."""
    events = SecurityEvent.query.filter_by(
        user_id=current_user.id
    ).order_by(SecurityEvent.created_at.desc()).all()

    audit_logs = AuditLog.query.filter_by(
        user_id=current_user.id
    ).order_by(AuditLog.created_at.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)

    # Security Events
    writer.writerow(['=== Security Events ==='])
    writer.writerow(['Date', 'Event Type', 'IP Address', 'Details'])
    for e in events:
        writer.writerow([
            e.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            e.event_type,
            e.ip_address or '',
            e.details or '',
        ])

    writer.writerow([])
    writer.writerow(['=== Audit Logs ==='])
    writer.writerow(['Date', 'Action', 'Table', 'Record ID', 'Details'])
    for log in audit_logs:
        writer.writerow([
            log.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            log.action,
            log.table_name or '',
            log.record_id or '',
            log.details or '',
        ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=security_logs_{datetime.utcnow().strftime("%Y%m%d")}.csv'}
    )


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
