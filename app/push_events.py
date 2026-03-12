"""
Push Notification Event Triggers

Utility functions that check conditions and fire push notifications
for key financial events. Each function is designed to be called
after a relevant action (transaction create, goal contribute, etc.).
"""

import logging
from datetime import datetime, timedelta

from flask import session
from sqlalchemy import func

from . import db
from .models import Budget, Creditor, Expense, Goal, Notification

logger = logging.getLogger(__name__)


def _user_wants_push(event_type, user_id=None):
    """Check if user has enabled push for this event type (database-based prefs)."""
    from flask_login import current_user
    from .models import User
    
    # Try to get user_id from current_user if not provided
    if user_id is None:
        if hasattr(current_user, 'id'):
            user_id = current_user.id
        else:
            # Fallback to session-based prefs
            prefs = session.get('push_prefs', {})
            return prefs.get(event_type, True)
    
    # Get preferences from database
    user = User.query.get(user_id)
    if user and user.push_prefs:
        return user.push_prefs.get(event_type, True)
    
    # Fallback to session-based prefs
    prefs = session.get('push_prefs', {})
    return prefs.get(event_type, True)


def _create_notification(user_id, title, message, ntype='info'):
    """Create in-app notification and attempt push delivery."""
    notif = Notification(
        user_id=user_id,
        title=title[:150],
        message=message[:1000],
        notification_type=ntype,
    )
    db.session.add(notif)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return

    try:
        from .routes_push import send_push_to_user
        send_push_to_user(user_id, title[:100], message[:200], url='/')
    except Exception as e:
        logger.debug("Push send failed (non-critical): %s", e)


# ---------------------------------------------------------------------------
# Budget alerts (>90% and >100%)
# ---------------------------------------------------------------------------

def check_budget_alerts(user_id, category_id, transaction_amount):
    """
    After adding/editing an expense, check if any budget for that category
    is now at >90% or >100%. Fires push if threshold just crossed.
    """
    if not _user_wants_push('budget_alerts', user_id):
        return

    budgets = Budget.query.filter_by(
        user_id=user_id, category_id=category_id, is_active=True
    ).all()

    now = datetime.utcnow()
    for budget in budgets:
        # Determine period start
        if budget.period == 'weekly':
            start = now - timedelta(days=now.weekday())
        elif budget.period == 'monthly':
            start = datetime(now.year, now.month, 1)
        elif budget.period == 'yearly':
            start = datetime(now.year, 1, 1)
        else:
            start = budget.start_date or datetime(now.year, now.month, 1)

        spent = db.session.query(func.sum(Expense.amount)).filter(
            Expense.user_id == user_id,
            Expense.category_id == category_id,
            Expense.transaction_type == 'expense',
            Expense.date >= start,
        ).scalar() or 0

        pct = (spent / budget.amount * 100) if budget.amount > 0 else 0
        cat_name = budget.category.name if budget.category else 'Unknown'

        # Check what the percentage was BEFORE this transaction
        prev_pct = ((spent - transaction_amount) / budget.amount * 100) if budget.amount > 0 else 0

        if pct >= 100 and prev_pct < 100:
            _create_notification(
                user_id,
                f'Budget Exceeded: {cat_name}',
                f'You have spent GHS {spent:,.2f} of your GHS {budget.amount:,.2f} {cat_name} budget ({pct:.0f}%). Consider reducing spending in this category.',
                'budget_alert',
            )
        elif pct >= 90 and prev_pct < 90:
            _create_notification(
                user_id,
                f'Budget Warning: {cat_name}',
                f'You\'ve used {pct:.0f}% of your {cat_name} budget (GHS {spent:,.2f} / GHS {budget.amount:,.2f}). Only GHS {max(budget.amount - spent, 0):,.2f} remaining.',
                'budget_alert',
            )


# ---------------------------------------------------------------------------
# Goal milestone reached
# ---------------------------------------------------------------------------

def check_goal_milestone(user_id, goal):
    """
    After contributing to a goal, check if milestones like 25%, 50%, 75%, 100%
    were just crossed.
    """
    if not _user_wants_push('goal_milestones', user_id):
        return

    if not goal or goal.target_amount <= 0:
        return

    progress = goal.progress  # uses the @property from model

    if goal.is_completed:
        _create_notification(
            user_id,
            f'Goal Achieved: {goal.name}!',
            f'Congratulations! You\'ve reached your target of GHS {goal.target_amount:,.2f} for "{goal.name}". Well done!',
            'goal_milestone',
        )
        return

    # Check milestone thresholds
    milestones = [75, 50, 25]
    for threshold in milestones:
        if progress >= threshold:
            # Check if we just crossed this threshold
            # Simple heuristic: only fire if progress is within 5% of threshold
            if progress - threshold < 5:
                _create_notification(
                    user_id,
                    f'Goal Progress: {goal.name} — {threshold}%',
                    f'You\'ve reached {progress:.0f}% of your "{goal.name}" goal (GHS {goal.current_amount:,.2f} / GHS {goal.target_amount:,.2f}). Keep it up!',
                    'goal_milestone',
                )
            break  # Only notify for the highest threshold crossed


# ---------------------------------------------------------------------------
# Large / unusual transaction detected
# ---------------------------------------------------------------------------

def check_large_transaction(user_id, amount, description, transaction_type):
    """
    Detect unusually large transactions by comparing to user's average.
    Fires if transaction is >3x the average expense amount.
    """
    if not _user_wants_push('large_transactions', user_id):
        return

    if transaction_type != 'expense':
        return

    # Calculate user's average expense over last 90 days
    ninety_days_ago = datetime.utcnow() - timedelta(days=90)
    avg_result = db.session.query(func.avg(Expense.amount)).filter(
        Expense.user_id == user_id,
        Expense.transaction_type == 'expense',
        Expense.date >= ninety_days_ago,
    ).scalar()

    avg_amount = float(avg_result) if avg_result else 0
    if avg_amount <= 0:
        return

    # Trigger if 3x average or above GHS 1000 (whichever is lower)
    threshold = min(avg_amount * 3, max(avg_amount * 3, 1000))
    if amount >= threshold:
        _create_notification(
            user_id,
            'Large Transaction Detected',
            f'A {"n" if description[0:1].lower() in "aeiou" else ""} expense of GHS {amount:,.2f} ("{description}") is significantly higher than your average of GHS {avg_amount:,.2f}.',
            'spending_alert',
        )


# ---------------------------------------------------------------------------
# Creditor payment due approaching
# ---------------------------------------------------------------------------

def check_creditor_due_dates(user_id):
    """
    Check if any creditor payments are due within the next 3 days.
    Call this periodically (e.g., on dashboard load or daily).
    """
    if not _user_wants_push('payment_due', user_id):
        return

    now = datetime.utcnow()
    three_days = now + timedelta(days=3)

    upcoming = Creditor.query.filter(
        Creditor.user_id == user_id,
        Creditor.status == 'active',
        Creditor.due_date.isnot(None),
        Creditor.due_date >= now,
        Creditor.due_date <= three_days,
    ).all()

    for creditor in upcoming:
        days_left = (creditor.due_date - now).days
        day_text = 'today' if days_left == 0 else f'in {days_left} day{"s" if days_left != 1 else ""}'

        # Avoid duplicate notifications — check if we already notified recently
        recent = Notification.query.filter(
            Notification.user_id == user_id,
            Notification.title.like(f'%{creditor.name}%due%'),
            Notification.created_at >= now - timedelta(days=1),
        ).first()
        if recent:
            continue

        _create_notification(
            user_id,
            f'Payment Due: {creditor.name}',
            f'Your payment of GHS {creditor.amount:,.2f} to "{creditor.name}" is due {day_text} ({creditor.due_date.strftime("%d %b %Y")}). Don\'t forget to make your payment.',
            'bill_reminder',
        )


# ---------------------------------------------------------------------------
# Recurring transaction processed
# ---------------------------------------------------------------------------

def notify_recurring_processed(user_id, description, amount, transaction_type):
    """Notify user when a recurring transaction has been automatically processed."""
    if not _user_wants_push('recurring_processed', user_id):
        return

    _create_notification(
        user_id,
        f'Recurring {"Income" if transaction_type == "income" else "Expense"} Processed',
        f'Your recurring transaction "{description}" of GHS {amount:,.2f} has been automatically processed.',
        'info',
    )
