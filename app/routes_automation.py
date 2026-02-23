from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from . import db
from .models import AutomationRule, WebhookEndpoint
import json

automation_bp = Blueprint('automation', __name__)

TRIGGER_TYPES = ['transaction_created', 'budget_exceeded', 'goal_progress', 'recurring_processed']
ACTION_TYPES = ['send_notification', 'add_tags', 'auto_categorize', 'call_webhook']


@automation_bp.route('/automation')
@login_required
def automation_list():
    rules = AutomationRule.query.filter_by(user_id=current_user.id).order_by(AutomationRule.created_at.desc()).all()
    webhooks = WebhookEndpoint.query.filter_by(user_id=current_user.id).order_by(WebhookEndpoint.created_at.desc()).all()
    return render_template('automation.html', rules=rules, webhooks=webhooks,
                           trigger_types=TRIGGER_TYPES, action_types=ACTION_TYPES)


@automation_bp.route('/automation/add', methods=['POST'])
@login_required
def add_rule():
    rule = AutomationRule(
        user_id=current_user.id,
        name=request.form.get('name', '').strip(),
        trigger_type=request.form.get('trigger_type', 'transaction_created'),
        condition=request.form.get('condition', ''),
        action_type=request.form.get('action_type', 'send_notification'),
        action_params=request.form.get('action_params', ''),
    )
    db.session.add(rule)
    db.session.commit()
    flash('Automation rule created.', 'success')
    return redirect(url_for('automation.automation_list'))


@automation_bp.route('/automation/toggle/<int:id>', methods=['POST'])
@login_required
def toggle_rule(id):
    rule = AutomationRule.query.get_or_404(id)
    rule.is_active = not rule.is_active
    db.session.commit()
    flash(f'Rule {"activated" if rule.is_active else "deactivated"}.', 'success')
    return redirect(url_for('automation.automation_list'))


@automation_bp.route('/automation/delete/<int:id>', methods=['POST'])
@login_required
def delete_rule(id):
    rule = AutomationRule.query.get_or_404(id)
    db.session.delete(rule)
    db.session.commit()
    flash('Rule deleted.', 'success')
    return redirect(url_for('automation.automation_list'))


@automation_bp.route('/automation/webhooks/add', methods=['POST'])
@login_required
def add_webhook():
    webhook = WebhookEndpoint(
        user_id=current_user.id,
        name=request.form.get('name', '').strip(),
        url=request.form.get('url', '').strip(),
        events=request.form.get('events', ''),
        secret=request.form.get('secret', '').strip() or None,
    )
    db.session.add(webhook)
    db.session.commit()
    flash('Webhook created.', 'success')
    return redirect(url_for('automation.automation_list'))


@automation_bp.route('/automation/webhooks/delete/<int:id>', methods=['POST'])
@login_required
def delete_webhook(id):
    wh = WebhookEndpoint.query.get_or_404(id)
    db.session.delete(wh)
    db.session.commit()
    flash('Webhook deleted.', 'success')
    return redirect(url_for('automation.automation_list'))
