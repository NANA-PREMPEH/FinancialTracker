from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from . import db
from .models import PushSubscription
import json

push_bp = Blueprint('push', __name__)


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
