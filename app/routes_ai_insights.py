from flask import Blueprint, render_template, jsonify
from flask_login import login_required, current_user
from . import db
from .models import Expense, Category, Budget, Creditor, Goal, Wallet
from datetime import datetime, timedelta
from sqlalchemy import func, extract
import statistics

ai_insights_bp = Blueprint('ai_insights', __name__)


def get_spending_forecast(user_id):
    """Project next month's expenses per category using 3-month rolling average."""
    now = datetime.utcnow()
    three_months_ago = now - timedelta(days=90)

    monthly_cat_spending = db.session.query(
        Category.name,
        extract('month', Expense.date).label('month'),
        func.sum(Expense.amount)
    ).join(Category).filter(
        Expense.user_id == user_id,
        Expense.transaction_type == 'expense',
        Expense.date >= three_months_ago
    ).group_by(Category.name, extract('month', Expense.date)).all()

    cat_monthly = {}
    for name, month, amt in monthly_cat_spending:
        cat_monthly.setdefault(name, []).append(float(amt))

    forecasts = []
    for name, amounts in sorted(cat_monthly.items(), key=lambda x: -sum(x[1])):
        avg = sum(amounts) / len(amounts)
        forecasts.append({'category': name, 'projected': round(avg, 2), 'months_data': len(amounts)})

    total_projected = sum(f['projected'] for f in forecasts)
    return {'categories': forecasts[:10], 'total_projected': round(total_projected, 2)}


def get_top_recommendations(user_id):
    """Generate prioritized action items based on user's financial data."""
    recommendations = []
    now = datetime.utcnow()
    month_ago = now - timedelta(days=30)

    # Check budget overruns and suggest reductions
    budgets = Budget.query.filter_by(user_id=user_id, is_active=True).all()
    for budget in budgets:
        spent = db.session.query(func.sum(Expense.amount)).filter(
            Expense.user_id == user_id, Expense.category_id == budget.category_id,
            Expense.transaction_type == 'expense', Expense.date >= budget.start_date
        ).scalar() or 0
        if budget.amount > 0 and spent > budget.amount:
            overage_pct = ((spent - budget.amount) / budget.amount) * 100
            recommendations.append({
                'priority': 'high',
                'icon': 'scissors',
                'text': f'Reduce {budget.category.name} spending by {overage_pct:.0f}% to meet your GHS {budget.amount:,.2f} budget.'
            })

    # Suggest paying off highest-interest creditor first
    creditors = Creditor.query.filter(
        Creditor.user_id == user_id, Creditor.amount > 0
    ).order_by(Creditor.amount.desc()).all()
    if creditors:
        top = creditors[0]
        recommendations.append({
            'priority': 'high',
            'icon': 'banknote',
            'text': f'Prioritize paying off "{top.name}" (GHS {top.amount:,.2f}) — your largest outstanding debt.'
        })

    # Savings recommendation
    total_income = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == user_id, Expense.transaction_type == 'income',
        Expense.date >= month_ago
    ).scalar() or 0
    total_expenses = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == user_id, Expense.transaction_type == 'expense',
        Expense.date >= month_ago
    ).scalar() or 0
    if total_income > 0:
        rate = (total_income - total_expenses) / total_income * 100
        if rate < 20:
            target = total_income * 0.20
            gap = target - (total_income - total_expenses)
            recommendations.append({
                'priority': 'medium',
                'icon': 'piggy-bank',
                'text': f'Save an extra GHS {gap:,.2f}/month to reach the recommended 20% savings rate.'
            })

    # Goal progress check
    active_goals = Goal.query.filter(
        Goal.user_id == user_id, Goal.is_completed == False
    ).all()
    for goal in active_goals[:3]:
        progress = (goal.current_amount / goal.target_amount * 100) if goal.target_amount > 0 else 0
        if progress < 25 and goal.deadline:
            # Handle both date and datetime types
            deadline_date = goal.deadline.date() if isinstance(goal.deadline, datetime) else goal.deadline
            days_left = (deadline_date - now.date()).days
            if 0 < days_left < 90:
                remaining = goal.target_amount - goal.current_amount
                monthly_needed = remaining / max(days_left / 30, 1)
                recommendations.append({
                    'priority': 'medium',
                    'icon': 'target',
                    'text': f'Save GHS {monthly_needed:,.2f}/month to reach your "{goal.name}" goal by deadline.'
                })

    if not recommendations:
        recommendations.append({
            'priority': 'low',
            'icon': 'check-circle',
            'text': 'You\'re on track! Keep maintaining your current financial habits.'
        })

    return recommendations[:8]


def get_weekly_heatmap(user_id):
    """Show which days of the week the user spends most."""
    now = datetime.utcnow()
    three_months_ago = now - timedelta(days=90)

    daily_spending = db.session.query(
        func.dayofweek(Expense.date).label('dow'),
        func.sum(Expense.amount),
        func.count(Expense.id)
    ).filter(
        Expense.user_id == user_id,
        Expense.transaction_type == 'expense',
        Expense.date >= three_months_ago
    ).group_by(func.dayofweek(Expense.date)).all()

    day_names = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    heatmap = []
    for i, name in enumerate(day_names):
        # MySQL DAYOFWEEK is 1 (Sun) - 7 (Sat)
        match = next((row for row in daily_spending if int(row[0]) == i + 1), None)
        heatmap.append({
            'day': name,
            'short': name[:3],
            'total': round(float(match[1]), 2) if match else 0,
            'count': int(match[2]) if match else 0
        })

    max_total = max((d['total'] for d in heatmap), default=1)
    for d in heatmap:
        d['intensity'] = round(d['total'] / max_total * 100) if max_total > 0 else 0

    return heatmap


def get_income_stability(user_id):
    """Measure variance in monthly income over last 6 months."""
    now = datetime.utcnow()
    six_months_ago = now - timedelta(days=180)

    monthly_income = db.session.query(
        extract('year', Expense.date).label('yr'),
        extract('month', Expense.date).label('mo'),
        func.sum(Expense.amount)
    ).filter(
        Expense.user_id == user_id,
        Expense.transaction_type == 'income',
        Expense.date >= six_months_ago
    ).group_by('yr', 'mo').all()

    amounts = [float(amt) for _, _, amt in monthly_income]

    if len(amounts) < 2:
        return {'score': 100, 'label': 'Insufficient Data', 'months': len(amounts),
                'avg_income': round(amounts[0], 2) if amounts else 0,
                'monthly_amounts': amounts}

    avg = statistics.mean(amounts)
    stdev = statistics.stdev(amounts)
    cv = (stdev / avg * 100) if avg > 0 else 0

    # Score: lower CV = higher stability (100 = perfectly stable)
    score = max(0, min(100, round(100 - cv)))

    if score >= 80:
        label = 'Very Stable'
    elif score >= 60:
        label = 'Stable'
    elif score >= 40:
        label = 'Moderate'
    else:
        label = 'Volatile'

    return {
        'score': score, 'label': label, 'months': len(amounts),
        'avg_income': round(avg, 2), 'std_dev': round(stdev, 2),
        'monthly_amounts': [round(a, 2) for a in amounts]
    }


def get_financial_health_score(user_id):
    """Composite metric combining savings rate, debt ratio, budget adherence, and goal progress."""
    now = datetime.utcnow()
    month_ago = now - timedelta(days=30)

    # 1. Savings rate (0-30 points)
    total_income = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == user_id, Expense.transaction_type == 'income',
        Expense.date >= month_ago
    ).scalar() or 0
    total_expenses = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == user_id, Expense.transaction_type == 'expense',
        Expense.date >= month_ago
    ).scalar() or 0
    savings_rate = ((total_income - total_expenses) / total_income * 100) if total_income > 0 else 0
    savings_score = min(30, max(0, round(savings_rate * 1.5)))

    # 2. Debt ratio (0-25 points) — lower debt = higher score
    total_debt = db.session.query(func.sum(Creditor.amount)).filter(
        Creditor.user_id == user_id
    ).scalar() or 0
    total_balance = db.session.query(func.sum(Wallet.balance)).filter(
        Wallet.user_id == user_id
    ).scalar() or 0
    debt_ratio = (total_debt / max(total_balance, 1)) * 100
    debt_score = max(0, round(25 - (debt_ratio * 0.25)))

    # 3. Budget adherence (0-25 points)
    budgets = Budget.query.filter_by(user_id=user_id, is_active=True).all()
    if budgets:
        within_budget = 0
        for b in budgets:
            spent = db.session.query(func.sum(Expense.amount)).filter(
                Expense.user_id == user_id, Expense.category_id == b.category_id,
                Expense.transaction_type == 'expense', Expense.date >= b.start_date
            ).scalar() or 0
            if spent <= b.amount:
                within_budget += 1
        adherence = (within_budget / len(budgets)) * 100
        budget_score = round(adherence * 0.25)
    else:
        budget_score = 12  # Neutral if no budgets set

    # 4. Goal progress (0-20 points)
    goals = Goal.query.filter(Goal.user_id == user_id, Goal.is_completed == False).all()
    completed_goals = Goal.query.filter_by(user_id=user_id, is_completed=True).count()
    if goals or completed_goals:
        goal_progresses = []
        for g in goals:
            progress = (g.current_amount / g.target_amount * 100) if g.target_amount > 0 else 0
            goal_progresses.append(min(100, progress))
        avg_progress = statistics.mean(goal_progresses) if goal_progresses else 0
        completion_bonus = min(10, completed_goals * 2)
        goal_score = min(20, round(avg_progress * 0.1) + completion_bonus)
    else:
        goal_score = 10  # Neutral if no goals

    total_score = savings_score + debt_score + budget_score + goal_score

    if total_score >= 80:
        grade, color = 'Excellent', 'success'
    elif total_score >= 60:
        grade, color = 'Good', 'primary'
    elif total_score >= 40:
        grade, color = 'Fair', 'warning'
    else:
        grade, color = 'Needs Attention', 'danger'

    return {
        'total': total_score,
        'grade': grade,
        'color': color,
        'breakdown': {
            'savings': {'score': savings_score, 'max': 30, 'detail': f'{savings_rate:.1f}% savings rate'},
            'debt': {'score': debt_score, 'max': 25, 'detail': f'{debt_ratio:.0f}% debt-to-asset ratio'},
            'budget': {'score': budget_score, 'max': 25, 'detail': f'{len(budgets)} active budgets'},
            'goals': {'score': goal_score, 'max': 20, 'detail': f'{completed_goals} goals completed'},
        }
    }


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

    forecast = get_spending_forecast(current_user.id)
    recommendations = get_top_recommendations(current_user.id)
    heatmap = get_weekly_heatmap(current_user.id)
    income_stability = get_income_stability(current_user.id)
    health_score = get_financial_health_score(current_user.id)

    return render_template('ai_insights.html', insights=insights,
                           monthly_income=monthly_income, monthly_expenses=monthly_expenses,
                           net_savings=net_savings, savings_rate=savings_rate,
                           forecast=forecast, recommendations=recommendations,
                           heatmap=heatmap, income_stability=income_stability,
                           health_score=health_score)
