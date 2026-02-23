from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from . import db
from .models import Notification, NotificationPreference

notifications_bp = Blueprint('notifications', __name__)

NOTIFICATION_TYPES = [
    {'key': 'budget_alert', 'label': 'Budget Alerts', 'description': 'Get notified when you exceed or approach your budget limits.'},
    {'key': 'goal_milestone', 'label': 'Goal Milestones', 'description': 'Celebrate when you reach saving milestones.'},
    {'key': 'bill_reminder', 'label': 'Bill Reminders', 'description': 'Reminders for upcoming bills and debts.'},
    {'key': 'spending_alert', 'label': 'Spending Alerts', 'description': 'Alerts for large or unusual transactions.'},
    {'key': 'cash_flow_warning', 'label': 'Cash Flow Warnings', 'description': 'Warnings about potential cash flow issues.'},
    {'key': 'info', 'label': 'General Information', 'description': 'General updates and tips.'}
]


@notifications_bp.route('/notifications')
@login_required
def notifications_list():
    notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).limit(50).all()
    unread_count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    return render_template('notifications.html', notifications=notifications, unread_count=unread_count)


@notifications_bp.route('/notifications/mark-read/<int:id>', methods=['POST'])
@login_required
def mark_read(id):
    n = Notification.query.get_or_404(id)
    n.is_read = True
    db.session.commit()
    return jsonify({'status': 'ok'})


@notifications_bp.route('/notifications/mark-all-read', methods=['POST'])
@login_required
def mark_all_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    flash('All notifications marked as read.', 'success')
    return redirect(url_for('notifications.notifications_list'))


@notifications_bp.route('/notifications/delete/<int:id>', methods=['POST'])
@login_required
def delete_notification(id):
    n = Notification.query.get_or_404(id)
    db.session.delete(n)
    db.session.commit()
    flash('Notification deleted.', 'success')
    return redirect(url_for('notifications.notifications_list'))


@notifications_bp.route('/notifications/preferences', methods=['GET', 'POST'])
@login_required
def preferences():
    if request.method == 'POST':
        for ntype_obj in NOTIFICATION_TYPES:
            ntype = ntype_obj['key']
            pref = NotificationPreference.query.filter_by(user_id=current_user.id, notification_type=ntype).first()
            enabled = bool(request.form.get(ntype))
            if pref:
                pref.enabled = enabled
            else:
                pref = NotificationPreference(user_id=current_user.id, notification_type=ntype, enabled=enabled)
                db.session.add(pref)
        db.session.commit()
        flash('Notification preferences saved.', 'success')
        return redirect(url_for('notifications.preferences'))

    prefs = {p.notification_type: p.enabled for p in
             NotificationPreference.query.filter_by(user_id=current_user.id).all()}
    # Default all to True if not set
    for ntype_obj in NOTIFICATION_TYPES:
        ntype = ntype_obj['key']
        if ntype not in prefs:
            prefs[ntype] = True
    return render_template('notification_preferences.html', prefs=prefs, types=NOTIFICATION_TYPES)


@notifications_bp.app_context_processor
def inject_notification_count():
    """Make unread notification count available in all templates."""
    if current_user.is_authenticated:
        count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
        return {'unread_notification_count': count}
    return {'unread_notification_count': 0}
