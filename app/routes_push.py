from flask import Blueprint, request, jsonify, current_app, flash, redirect, render_template, session, url_for
from flask_login import login_required, current_user
from . import db
from .models import Notification, PushSubscription
import json

push_bp = Blueprint('push', __name__)

# Default push preferences — all enabled
DEFAULT_PUSH_PREFS = {
    'budget_alerts': True,
    'goal_milestones': True,
    'large_transactions': True,
    'payment_due': True,
    'recurring_processed': True,
}

PUSH_EVENT_LABELS = {
    'budget_alerts': ('Budget Alerts', 'When spending approaches or exceeds a budget limit.', 'pie-chart'),
    'goal_milestones': ('Goal Milestones', 'When you reach 25%, 50%, 75%, or 100% of a goal.', 'target'),
    'large_transactions': ('Large Transactions', 'When an expense is unusually large compared to your average.', 'alert-triangle'),
    'payment_due': ('Payment Due', 'Creditor payments approaching within 3 days.', 'calendar-clock'),
    'recurring_processed': ('Recurring Processed', 'When a recurring transaction is automatically applied.', 'repeat'),
}


@push_bp.route('/push/subscribe', methods=['POST'])
@login_required
def subscribe():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    endpoint = data.get('endpoint')
    keys = data.get('keys', {})
    p256dh = keys.get('p256dh')
    auth = keys.get('auth')

    if not endpoint or not p256dh or not auth:
        return jsonify({'error': 'Invalid subscription data'}), 400

    # Check for existing subscription
    existing = PushSubscription.query.filter_by(
        user_id=current_user.id, endpoint=endpoint
    ).first()

    if existing:
        existing.p256dh = p256dh
        existing.auth = auth
    else:
        sub = PushSubscription(
            user_id=current_user.id,
            endpoint=endpoint,
            p256dh=p256dh,
            auth=auth
        )
        db.session.add(sub)

    db.session.commit()
    return jsonify({'status': 'ok'})


@push_bp.route('/push/unsubscribe', methods=['POST'])
@login_required
def unsubscribe():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    endpoint = data.get('endpoint')
    PushSubscription.query.filter_by(
        user_id=current_user.id, endpoint=endpoint
    ).delete()
    db.session.commit()
    return jsonify({'status': 'ok'})


@push_bp.route('/push/test', methods=['POST'])
@login_required
def test_push():
    """Send a test push notification to the current user."""
    sub_count = PushSubscription.query.filter_by(user_id=current_user.id).count()
    if sub_count == 0:
        flash('No push subscriptions found. Enable push notifications in your browser first.', 'error')
        return redirect(url_for('push.push_preferences'))

    send_push_to_user(
        current_user.id,
        'Test Notification',
        'This is a test push notification from FinTracker. If you see this, push notifications are working!',
        url='/push/preferences'
    )
    flash(f'Test notification sent to {sub_count} device(s).', 'success')
    return redirect(url_for('push.push_preferences'))


@push_bp.route('/push/preferences', methods=['GET'])
@login_required
def push_preferences():
    """View and manage push notification preferences."""
    from .models import User
    
    # Load from database first, fallback to session
    user = User.query.get(current_user.id)
    if user and user.push_prefs:
        prefs = user.push_prefs
    else:
        prefs = session.get('push_prefs', DEFAULT_PUSH_PREFS.copy())
    
    sub_count = PushSubscription.query.filter_by(user_id=current_user.id).count()

    # Recent notifications for this user
    recent_notifs = Notification.query.filter_by(
        user_id=current_user.id
    ).order_by(Notification.created_at.desc()).limit(20).all()

    return render_template('push_preferences.html',
        prefs=prefs,
        event_labels=PUSH_EVENT_LABELS,
        sub_count=sub_count,
        recent_notifs=recent_notifs,
    )


@push_bp.route('/push/preferences', methods=['POST'])
@login_required
def save_push_preferences():
    """Save push notification preferences to database."""
    from .models import User
    
    prefs = {}
    for key in DEFAULT_PUSH_PREFS:
        prefs[key] = key in request.form
    
    # Save to database
    user = User.query.get(current_user.id)
    if user:
        user.push_prefs = prefs
        db.session.commit()
    
    # Also save to session for backwards compatibility
    session['push_prefs'] = prefs
    flash('Push notification preferences saved.', 'success')
    return redirect(url_for('push.push_preferences'))


@push_bp.route('/push/clear-notifications', methods=['POST'])
@login_required
def clear_notifications():
    """Mark all notifications as read."""
    Notification.query.filter_by(
        user_id=current_user.id, is_read=False
    ).update({'is_read': True})
    db.session.commit()
    flash('All notifications marked as read.', 'success')
    return redirect(url_for('push.push_preferences'))


def send_push_to_user(user_id, title, body, url='/'):
    """Send a web push notification to all subscriptions for a user."""
    try:
        from pywebpush import webpush, WebPushException

        vapid_private = current_app.config.get('VAPID_PRIVATE_KEY')
        vapid_email = current_app.config.get('VAPID_CLAIMS_EMAIL', 'mailto:admin@fintracker.app')

        if not vapid_private:
            return  # Push not configured

        subscriptions = PushSubscription.query.filter_by(user_id=user_id).all()
        payload = json.dumps({
            'title': title,
            'body': body,
            'url': url,
            'icon': '/static/icons/icon-192.png'
        })

        for sub in subscriptions:
            try:
                webpush(
                    subscription_info={
                        'endpoint': sub.endpoint,
                        'keys': {'p256dh': sub.p256dh, 'auth': sub.auth}
                    },
                    data=payload,
                    vapid_private_key=vapid_private,
                    vapid_claims={'sub': vapid_email}
                )
            except WebPushException as e:
                if e.response and e.response.status_code in (404, 410):
                    # Subscription expired, remove it
                    db.session.delete(sub)
                    db.session.commit()
    except Exception as e:
        current_app.logger.error(f'Push notification error: {e}')
