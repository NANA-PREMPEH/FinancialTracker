from flask import Blueprint, render_template
from flask_login import login_required, current_user
from . import db
from .models import Expense, Category, Budget, Creditor, Goal, Wallet
from datetime import datetime, timedelta
from sqlalchemy import func

ai_insights_bp = Blueprint('ai_insights', __name__)


def get_spending_insights(user_id):
    insights = []
    now = datetime.utcnow()
    month_ago = now - timedelta(days=30)
    two_months_ago = now - timedelta(days=60)

    # Category spending trends
    current_month = db.session.query(
        Category.name, func.sum(Expense.amount)
    ).join(Category).filter(
        Expense.user_id == user_id,
        Expense.transaction_type == 'expense',
        Expense.date >= month_ago
    ).group_by(Category.name).all()

    prev_month = db.session.query(
        Category.name, func.sum(Expense.amount)
    ).join(Category).filter(
        Expense.user_id == user_id,
        Expense.transaction_type == 'expense',
        Expense.date >= two_months_ago,
        Expense.date < month_ago
    ).group_by(Category.name).all()

    prev_dict = {name: amt for name, amt in prev_month}
    for name, amt in current_month:
        prev_amt = prev_dict.get(name, 0)
        if prev_amt > 0:
            change = ((amt - prev_amt) / prev_amt) * 100
            if change > 25:
                insights.append({
                    'type': 'warning',
                    'icon': '📈',
                    'title': f'{name} spending up {change:.0f}%',
                    'message': f'You spent GHS {amt:.2f} on {name} this month vs GHS {prev_amt:.2f} last month.'
                })
            elif change < -25:
                insights.append({
                    'type': 'success',
                    'icon': '📉',
                    'title': f'{name} spending down {abs(change):.0f}%',
                    'message': f'Great job! {name} spending decreased from GHS {prev_amt:.2f} to GHS {amt:.2f}.'
                })

    # Savings rate
    total_income = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == user_id, Expense.transaction_type == 'income',
        Expense.date >= month_ago
    ).scalar() or 0
    total_expenses = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == user_id, Expense.transaction_type == 'expense',
        Expense.date >= month_ago
    ).scalar() or 0

    if total_income > 0:
        savings_rate = ((total_income - total_expenses) / total_income) * 100
        if savings_rate < 10:
            insights.append({
                'type': 'warning', 'icon': '💰',
                'title': f'Low savings rate: {savings_rate:.1f}%',
                'message': 'Financial experts recommend saving at least 20% of income. Consider the Arkad 10% rule as a starting point.'
            })
        elif savings_rate >= 20:
            insights.append({
                'type': 'success', 'icon': '🎉',
                'title': f'Excellent savings rate: {savings_rate:.1f}%',
                'message': 'You are saving more than 20% of your income. Keep it up!'
            })

    # Budget alerts
    budgets = Budget.query.filter_by(user_id=user_id, is_active=True).all()
    for budget in budgets:
        spent = db.session.query(func.sum(Expense.amount)).filter(
            Expense.user_id == user_id, Expense.category_id == budget.category_id,
            Expense.transaction_type == 'expense', Expense.date >= budget.start_date
        ).scalar() or 0
        if budget.amount > 0:
            usage = (spent / budget.amount) * 100
            if usage >= 90:
                insights.append({
                    'type': 'danger', 'icon': '🚨',
                    'title': f'Budget near limit: {budget.category.name}',
                    'message': f'{usage:.0f}% used (GHS {spent:.2f} of GHS {budget.amount:.2f}). Consider reducing spending.'
                })

    # Debt insights
    total_debt = db.session.query(func.sum(Creditor.amount)).filter(
        Creditor.user_id == user_id
    ).scalar() or 0
    if total_debt > 0:
        total_balance = db.session.query(func.sum(Wallet.balance)).filter(
            Wallet.user_id == user_id
        ).scalar() or 0
        debt_ratio = (total_debt / max(total_balance, 1)) * 100
        if debt_ratio > 50:
            insights.append({
                'type': 'warning', 'icon': '⚠️',
                'title': f'High debt-to-asset ratio: {debt_ratio:.0f}%',
                'message': f'Your total debt (GHS {total_debt:.2f}) is {debt_ratio:.0f}% of your assets. Focus on debt reduction.'
            })

    # Unusual transactions
    avg_amounts = db.session.query(
        Category.name, func.avg(Expense.amount), func.max(Expense.amount)
    ).join(Category).filter(
        Expense.user_id == user_id, Expense.transaction_type == 'expense'
    ).group_by(Category.name).all()

    for name, avg_amt, max_amt in avg_amounts:
        if avg_amt and max_amt > avg_amt * 3:
            insights.append({
                'type': 'info', 'icon': '🔍',
                'title': f'Unusual transaction in {name}',
                'message': f'Highest transaction (GHS {max_amt:.2f}) is {max_amt/avg_amt:.1f}x the average (GHS {avg_amt:.2f}).'
            })

    if not insights:
        insights.append({
            'type': 'info', 'icon': '✅',
            'title': 'Looking good!',
            'message': 'No significant financial concerns detected. Keep tracking your finances consistently.'
        })

    return insights


@ai_insights_bp.route('/ai-insights')
@login_required
def ai_insights():
    insights = get_spending_insights(current_user.id)

    # Summary stats
    now = datetime.utcnow()
    month_ago = now - timedelta(days=30)
    monthly_income = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == current_user.id, Expense.transaction_type == 'income',
        Expense.date >= month_ago
    ).scalar() or 0
    monthly_expenses = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == current_user.id, Expense.transaction_type == 'expense',
        Expense.date >= month_ago
    ).scalar() or 0
    net_savings = monthly_income - monthly_expenses
    savings_rate = ((monthly_income - monthly_expenses) / monthly_income * 100) if monthly_income > 0 else 0

    return render_template('ai_insights.html', insights=insights,
                           monthly_income=monthly_income, monthly_expenses=monthly_expenses,
                           net_savings=net_savings, savings_rate=savings_rate)
