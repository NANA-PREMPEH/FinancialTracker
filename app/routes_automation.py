from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_required, current_user
from . import db
from .models import AutomationRule, WebhookEndpoint
from .automation_engine import execute_rules
import json

automation_bp = Blueprint('automation', __name__)

TRIGGER_TYPES = ['transaction_created', 'budget_exceeded', 'goal_progress', 'recurring_processed']
ACTION_TYPES = ['send_notification', 'add_tags', 'auto_categorize', 'call_webhook']


@automation_bp.route('/automation')
@login_required
def automation_list():
    rules = AutomationRule.query.filter_by(user_id=current_user.id).order_by(AutomationRule.created_at.desc()).all()
    webhooks = WebhookEndpoint.query.filter_by(user_id=current_user.id).order_by(WebhookEndpoint.created_at.desc()).all()
    execution_logs = session.get('automation_logs', [])
    # Show most recent first
    execution_logs = list(reversed(execution_logs[-30:]))
    return render_template('automation.html', rules=rules, webhooks=webhooks,
                           trigger_types=TRIGGER_TYPES, action_types=ACTION_TYPES,
                           execution_logs=execution_logs)


@automation_bp.route('/automation/add', methods=['POST'])
@login_required
def add_rule():
    name = request.form.get('name', '').strip()
    if not name:
        flash('Rule name is required.', 'error')
        return redirect(url_for('automation.automation_list'))

    rule = AutomationRule(
        user_id=current_user.id,
        name=name,
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
    rule = AutomationRule.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    rule.is_active = not rule.is_active
    db.session.commit()
    flash(f'Rule {"activated" if rule.is_active else "deactivated"}.', 'success')
    return redirect(url_for('automation.automation_list'))


@automation_bp.route('/automation/delete/<int:id>', methods=['POST'])
@login_required
def delete_rule(id):
    rule = AutomationRule.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    db.session.delete(rule)
    db.session.commit()
    flash('Rule deleted.', 'success')
    return redirect(url_for('automation.automation_list'))


@automation_bp.route('/automation/test/<int:id>', methods=['POST'])
@login_required
def test_rule(id):
    """Dry-run a rule with sample context to verify it works."""
    rule = AutomationRule.query.filter_by(id=id, user_id=current_user.id).first_or_404()

    # Build a sample context
    sample_context = {
        'amount': 100.0,
        'description': 'Test transaction',
        'category': 'Other',
        'type': 'expense',
        'trigger_type': rule.trigger_type,
    }

    results = execute_rules(rule.trigger_type, sample_context, current_user.id)
    if results:
        for r in results:
            if r['success']:
                flash(f'Test "{r["rule_name"]}": {r["result"]}', 'success')
            else:
                flash(f'Test "{r["rule_name"]}": {r["result"]}', 'error')
    else:
        flash('No rules matched the test context. Check your condition.', 'warning')
    return redirect(url_for('automation.automation_list'))


@automation_bp.route('/automation/clear-logs', methods=['POST'])
@login_required
def clear_logs():
    session.pop('automation_logs', None)
    flash('Execution logs cleared.', 'success')
    return redirect(url_for('automation.automation_list'))


# --- Webhooks ---

@automation_bp.route('/automation/webhooks/add', methods=['POST'])
@login_required
def add_webhook():
    name = request.form.get('name', '').strip()
    url = request.form.get('url', '').strip()
    if not name or not url:
        flash('Webhook name and URL are required.', 'error')
        return redirect(url_for('automation.automation_list'))

    webhook = WebhookEndpoint(
        user_id=current_user.id,
        name=name,
        url=url,
        events=request.form.get('events', ''),
        secret=request.form.get('secret', '').strip() or None,
    )
    db.session.add(webhook)
    db.session.commit()
    flash('Webhook created.', 'success')
    return redirect(url_for('automation.automation_list'))


@automation_bp.route('/automation/webhooks/toggle/<int:id>', methods=['POST'])
@login_required
def toggle_webhook(id):
    wh = WebhookEndpoint.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    wh.is_active = not wh.is_active
    db.session.commit()
    flash(f'Webhook {"activated" if wh.is_active else "deactivated"}.', 'success')
    return redirect(url_for('automation.automation_list'))


@automation_bp.route('/automation/webhooks/delete/<int:id>', methods=['POST'])
@login_required
def delete_webhook(id):
    wh = WebhookEndpoint.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    db.session.delete(wh)
    db.session.commit()
    flash('Webhook deleted.', 'success')
    return redirect(url_for('automation.automation_list'))
