"""
Automation Rule Execution Engine

Evaluates user-defined automation rules against triggers (transaction_created,
budget_exceeded, goal_progress, recurring_processed) and executes actions
(send_notification, add_tags, auto_categorize, call_webhook).
"""

import hashlib
import hmac
import json
import logging
import re
from datetime import datetime

import requests as http_requests

from . import db
from .models import AutomationRule, Category, Notification, WebhookEndpoint

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Condition evaluator
# ---------------------------------------------------------------------------

def _safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _evaluate_condition(condition_str, context):
    """
    Evaluate a simple condition string against a context dict.

    Supported formats:
        amount > 500
        amount >= 100.50
        amount < 20
        category == 'Food'
        category != 'Transport'
        description contains 'grocery'
        description startswith 'ATM'
        type == 'expense'
        any  (always true)
        (empty string → always true)

    Returns True if the condition matches, False otherwise.
    """
    condition_str = (condition_str or '').strip()
    if not condition_str or condition_str.lower() == 'any':
        return True

    # Normalize multiple conditions separated by AND
    parts = re.split(r'\s+and\s+', condition_str, flags=re.IGNORECASE)
    for part in parts:
        if not _evaluate_single(part.strip(), context):
            return False
    return True


def _evaluate_single(expr, context):
    """Evaluate a single condition expression."""
    # Pattern: field operator value
    # Operators: ==, !=, >, >=, <, <=, contains, startswith, endswith
    patterns = [
        (r'^(\w+)\s+(contains)\s+["\'](.+?)["\']$', 'contains'),
        (r'^(\w+)\s+(startswith)\s+["\'](.+?)["\']$', 'startswith'),
        (r'^(\w+)\s+(endswith)\s+["\'](.+?)["\']$', 'endswith'),
        (r'^(\w+)\s*(==|!=)\s*["\'](.+?)["\']$', 'str_compare'),
        (r'^(\w+)\s*(==|!=|>=|<=|>|<)\s*([0-9.]+)$', 'num_compare'),
    ]

    for pattern, kind in patterns:
        m = re.match(pattern, expr, re.IGNORECASE)
        if not m:
            continue
        field, op, value = m.group(1), m.group(2), m.group(3)
        ctx_value = context.get(field)

        if kind == 'contains':
            return value.lower() in str(ctx_value or '').lower()
        elif kind == 'startswith':
            return str(ctx_value or '').lower().startswith(value.lower())
        elif kind == 'endswith':
            return str(ctx_value or '').lower().endswith(value.lower())
        elif kind == 'str_compare':
            ctx_str = str(ctx_value or '').lower()
            val_str = value.lower()
            if op == '==':
                return ctx_str == val_str
            elif op == '!=':
                return ctx_str != val_str
        elif kind == 'num_compare':
            ctx_num = _safe_float(ctx_value)
            val_num = _safe_float(value)
            if ctx_num is None or val_num is None:
                return False
            ops = {
                '==': lambda a, b: a == b,
                '!=': lambda a, b: a != b,
                '>': lambda a, b: a > b,
                '>=': lambda a, b: a >= b,
                '<': lambda a, b: a < b,
                '<=': lambda a, b: a <= b,
            }
            return ops.get(op, lambda a, b: False)(ctx_num, val_num)

    # If no pattern matched, treat as always-false
    logger.warning("Could not parse automation condition: %s", expr)
    return False


# ---------------------------------------------------------------------------
# Action handlers
# ---------------------------------------------------------------------------

def _action_send_notification(user_id, params, context):
    """Create an in-app notification."""
    title = params.get('title', 'Automation Alert')
    message = params.get('message', '')
    # Allow template variables in message
    for key, val in context.items():
        message = message.replace(f'{{{key}}}', str(val))
        title = title.replace(f'{{{key}}}', str(val))

    if not message:
        message = f"Rule triggered: {context.get('rule_name', 'Unknown')} — {context.get('description', '')}"

    notif = Notification(
        user_id=user_id,
        title=title[:150],
        message=message[:1000],
        notification_type=params.get('type', 'info'),
    )
    db.session.add(notif)

    # Attempt push notification (non-blocking)
    try:
        from .routes_push import send_push_to_user
        send_push_to_user(user_id, title[:100], message[:200])
    except Exception:
        pass

    return f'Notification created: {title}'


def _action_add_tags(user_id, params, context):
    """Append tags to the triggering transaction."""
    expense = context.get('_expense_obj')
    if not expense:
        return 'No transaction object — skipped'

    new_tags = params.get('tags', '')
    if not new_tags:
        return 'No tags specified'

    existing = expense.tags or ''
    existing_set = set(t.strip().lower() for t in existing.split(',') if t.strip())
    for tag in new_tags.split(','):
        tag = tag.strip()
        if tag and tag.lower() not in existing_set:
            existing = f'{existing},{tag}' if existing else tag
            existing_set.add(tag.lower())
    expense.tags = existing
    return f'Tags updated: {existing}'


def _action_auto_categorize(user_id, params, context):
    """Reassign the transaction's category."""
    expense = context.get('_expense_obj')
    if not expense:
        return 'No transaction object — skipped'

    cat_name = params.get('category', '').strip()
    if not cat_name:
        return 'No category specified'

    category = Category.query.filter(
        Category.user_id == user_id,
        db.func.lower(Category.name) == cat_name.lower()
    ).first()
    if not category:
        return f'Category "{cat_name}" not found'

    old_name = expense.category.name if expense.category else 'None'
    expense.category_id = category.id
    return f'Re-categorized from "{old_name}" to "{cat_name}"'


def _action_call_webhook(user_id, params, context):
    """POST event data to user's configured webhook endpoint."""
    webhook_name = params.get('webhook', '')
    webhook_url = params.get('url', '')

    endpoint = None
    if webhook_name:
        endpoint = WebhookEndpoint.query.filter_by(
            user_id=user_id, name=webhook_name, is_active=True
        ).first()
    elif webhook_url:
        endpoint = WebhookEndpoint.query.filter_by(
            user_id=user_id, url=webhook_url, is_active=True
        ).first()
    else:
        endpoint = WebhookEndpoint.query.filter_by(
            user_id=user_id, is_active=True
        ).first()

    if not endpoint:
        return 'No active webhook endpoint found'

    # Build payload (exclude internal objects)
    payload = {k: v for k, v in context.items() if not k.startswith('_')}
    payload['timestamp'] = datetime.utcnow().isoformat()
    payload['event'] = context.get('trigger_type', 'automation')

    headers = {'Content-Type': 'application/json'}

    # Sign with HMAC if secret configured
    body = json.dumps(payload, default=str)
    if endpoint.secret:
        sig = hmac.new(endpoint.secret.encode(), body.encode(), hashlib.sha256).hexdigest()
        headers['X-Webhook-Signature'] = sig

    try:
        resp = http_requests.post(endpoint.url, data=body, headers=headers, timeout=10)
        return f'Webhook {endpoint.name}: HTTP {resp.status_code}'
    except Exception as e:
        return f'Webhook {endpoint.name} failed: {str(e)[:100]}'


ACTION_HANDLERS = {
    'send_notification': _action_send_notification,
    'add_tags': _action_add_tags,
    'auto_categorize': _action_auto_categorize,
    'call_webhook': _action_call_webhook,
}


# ---------------------------------------------------------------------------
# Main execution entry point
# ---------------------------------------------------------------------------

def execute_rules(trigger_type, context, user_id):
    """
    Query active automation rules matching the trigger type,
    evaluate conditions, and execute actions.

    Args:
        trigger_type: One of 'transaction_created', 'budget_exceeded',
                      'goal_progress', 'recurring_processed'
        context: dict with fields like amount, description, category, type, etc.
        user_id: The user whose rules to evaluate.

    Returns:
        List of execution results (dicts with rule_name, action, result, success).
    """
    rules = AutomationRule.query.filter_by(
        user_id=user_id,
        trigger_type=trigger_type,
        is_active=True,
    ).all()

    results = []
    for rule in rules:
        context['rule_name'] = rule.name
        context['trigger_type'] = trigger_type

        # Evaluate condition
        try:
            matched = _evaluate_condition(rule.condition, context)
        except Exception as e:
            logger.error("Condition eval error for rule %s: %s", rule.name, e)
            results.append({
                'rule_name': rule.name,
                'action': rule.action_type,
                'result': f'Condition error: {str(e)[:100]}',
                'success': False,
            })
            continue

        if not matched:
            continue

        # Parse action params
        try:
            params = json.loads(rule.action_params) if rule.action_params else {}
        except json.JSONDecodeError:
            params = {'raw': rule.action_params}

        # Execute action
        handler = ACTION_HANDLERS.get(rule.action_type)
        if not handler:
            results.append({
                'rule_name': rule.name,
                'action': rule.action_type,
                'result': f'Unknown action type: {rule.action_type}',
                'success': False,
            })
            continue

        try:
            result = handler(user_id, params, context)
            results.append({
                'rule_name': rule.name,
                'action': rule.action_type,
                'result': result,
                'success': True,
            })
        except Exception as e:
            logger.error("Action error for rule %s: %s", rule.name, e)
            results.append({
                'rule_name': rule.name,
                'action': rule.action_type,
                'result': f'Error: {str(e)[:100]}',
                'success': False,
            })

    # Commit any DB changes from actions (tags, categories, notifications)
    if results:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

    # Log execution results
    _log_executions(user_id, results)

    return results


def _log_executions(user_id, results):
    """Store execution results in the session for display (lightweight logging)."""
    if not results:
        return
    from flask import session
    logs = session.get('automation_logs', [])
    for r in results:
        logs.append({
            'rule_name': r['rule_name'],
            'action': r['action'],
            'result': r['result'],
            'success': r['success'],
            'time': datetime.utcnow().strftime('%d %b %H:%M'),
        })
    # Keep last 50 entries
    session['automation_logs'] = logs[-50:]
