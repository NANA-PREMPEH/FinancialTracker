from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from . import db
from .models import Creditor, Wallet, Expense
from datetime import datetime, timedelta
from sqlalchemy import func
import math

calculator_bp = Blueprint("calculator", __name__)


def calc_loan_amortization(principal, annual_rate, years):
    """Compute monthly payment, total interest, and full amortization schedule."""
    if principal <= 0 or years <= 0:
        return None
    n = int(years * 12)
    mr = annual_rate / 100 / 12

    if mr == 0:
        monthly = principal / n
    else:
        monthly = principal * (mr * math.pow(1 + mr, n)) / (math.pow(1 + mr, n) - 1)

    schedule = []
    balance = principal
    total_interest = 0
    for i in range(1, n + 1):
        interest = balance * mr
        princ = monthly - interest
        if princ > balance:
            princ = balance
        balance -= princ
        total_interest += interest
        schedule.append({
            'month': i, 'payment': round(monthly, 2),
            'principal': round(princ, 2), 'interest': round(interest, 2),
            'balance': round(max(balance, 0), 2)
        })

    return {
        'monthly_payment': round(monthly, 2),
        'total_payment': round(monthly * n, 2),
        'total_interest': round(total_interest, 2),
        'schedule': schedule
    }


def calc_compound_interest(principal, monthly_contrib, annual_rate, years):
    """Compute future value with optional monthly contributions and yearly breakdown."""
    n = int(years * 12)
    mr = annual_rate / 100 / 12

    breakdown = []
    balance = principal
    total_contrib = principal
    for year in range(1, int(years) + 1):
        for _ in range(12):
            balance = balance * (1 + mr) + monthly_contrib
            total_contrib += monthly_contrib
        breakdown.append({
            'year': year,
            'balance': round(balance, 2),
            'contributions': round(total_contrib, 2),
            'growth': round(balance - total_contrib, 2)
        })

    # Handle remaining months if years is not whole
    remaining = n - int(years) * 12
    for _ in range(remaining):
        balance = balance * (1 + mr) + monthly_contrib
        total_contrib += monthly_contrib

    return {
        'future_value': round(balance, 2),
        'total_contributions': round(total_contrib, 2),
        'total_growth': round(balance - total_contrib, 2),
        'breakdown': breakdown
    }


def calc_savings_goal(target, current, annual_rate, years):
    """How much to save monthly to reach a target by deadline."""
    if target <= 0 or years <= 0:
        return None
    n = int(years * 12)
    mr = annual_rate / 100 / 12

    future_current = current * math.pow(1 + mr, n) if mr > 0 else current
    gap = target - future_current

    if gap <= 0:
        return {
            'monthly_needed': 0,
            'total_deposits': round(current, 2),
            'interest_earned': round(target - current, 2),
            'message': 'Your current savings will reach the target with interest alone.',
            'breakdown': []
        }

    if mr == 0:
        monthly = gap / n
    else:
        monthly = gap * mr / (math.pow(1 + mr, n) - 1)

    breakdown = []
    balance = current
    for year in range(1, int(years) + 1):
        for _ in range(12):
            balance = balance * (1 + mr) + monthly
        breakdown.append({
            'year': year,
            'balance': round(balance, 2),
            'target_pct': round(balance / target * 100, 1)
        })

    return {
        'monthly_needed': round(monthly, 2),
        'total_deposits': round(current + monthly * n, 2),
        'interest_earned': round(target - (current + monthly * n), 2),
        'message': f'Save GHS {monthly:,.2f}/month for {n} months to reach your goal.',
        'breakdown': breakdown
    }


def calc_debt_payoff_strategies(creditors_data, extra_payment=0):
    """Compare snowball (smallest balance first) vs avalanche (highest rate first)."""
    if not creditors_data:
        return None

    def simulate(debts, order_key):
        debts = [dict(d) for d in debts]
        debts.sort(key=lambda d: d[order_key])
        total_interest = 0
        months = 0
        min_payments = sum(d['min_payment'] for d in debts)
        monthly_budget = min_payments + extra_payment
        timeline = []

        while any(d['balance'] > 0 for d in debts) and months < 1200:
            months += 1
            remaining_budget = monthly_budget

            # Pay minimums first
            for d in debts:
                if d['balance'] <= 0:
                    continue
                interest = d['balance'] * (d['rate'] / 100 / 12)
                total_interest += interest
                d['balance'] += interest
                payment = min(d['min_payment'], d['balance'])
                d['balance'] -= payment
                remaining_budget -= payment

            # Apply extra to priority debt
            for d in debts:
                if d['balance'] <= 0:
                    continue
                extra = min(remaining_budget, d['balance'])
                d['balance'] -= extra
                remaining_budget -= extra
                if remaining_budget <= 0:
                    break

            total_remaining = sum(max(d['balance'], 0) for d in debts)
            if months % 3 == 0 or total_remaining == 0:
                timeline.append({'month': months, 'remaining': round(total_remaining, 2)})

            if total_remaining <= 0.01:
                break

        return {
            'months': months,
            'total_interest': round(total_interest, 2),
            'total_paid': round(sum(d['original'] for d in debts) + total_interest, 2),
            'timeline': timeline
        }

    debts = []
    for c in creditors_data:
        debts.append({
            'name': c['name'],
            'balance': c['balance'],
            'original': c['balance'],
            'rate': c['rate'],
            'min_payment': c['min_payment']
        })

    snowball = simulate(debts, 'balance')
    # Note: avalanche is computed manually below, so skip the broken simulate call

    # Redo avalanche properly with correct sort
    debts_aval = []
    for c in creditors_data:
        debts_aval.append({
            'name': c['name'],
            'balance': c['balance'],
            'original': c['balance'],
            'rate': c['rate'],
            'min_payment': c['min_payment']
        })
    debts_aval.sort(key=lambda d: -d['rate'])

    total_interest_aval = 0
    months_aval = 0
    min_payments = sum(d['min_payment'] for d in debts_aval)
    monthly_budget = min_payments + extra_payment
    timeline_aval = []

    while any(d['balance'] > 0 for d in debts_aval) and months_aval < 1200:
        months_aval += 1
        remaining_budget = monthly_budget
        for d in debts_aval:
            if d['balance'] <= 0:
                continue
            interest = d['balance'] * (d['rate'] / 100 / 12)
            total_interest_aval += interest
            d['balance'] += interest
            payment = min(d['min_payment'], d['balance'])
            d['balance'] -= payment
            remaining_budget -= payment
        for d in debts_aval:
            if d['balance'] <= 0:
                continue
            extra = min(remaining_budget, d['balance'])
            d['balance'] -= extra
            remaining_budget -= extra
            if remaining_budget <= 0:
                break
        total_remaining = sum(max(d['balance'], 0) for d in debts_aval)
        if months_aval % 3 == 0 or total_remaining == 0:
            timeline_aval.append({'month': months_aval, 'remaining': round(total_remaining, 2)})
        if total_remaining <= 0.01:
            break

    avalanche = {
        'months': months_aval,
        'total_interest': round(total_interest_aval, 2),
        'total_paid': round(sum(c['balance'] for c in creditors_data) + total_interest_aval, 2),
        'timeline': timeline_aval
    }

    savings = round(snowball['total_interest'] - avalanche['total_interest'], 2)

    return {
        'snowball': snowball,
        'avalanche': avalanche,
        'interest_savings': savings,
        'recommendation': 'avalanche' if savings > 0 else 'snowball',
        'debts': [{'name': c['name'], 'balance': c['balance'], 'rate': c['rate']} for c in creditors_data]
    }


def calc_net_worth_projection(current_assets, current_debts, monthly_savings, annual_return, years):
    """Project net worth growth based on current savings rate."""
    if years <= 0:
        return None
    mr = annual_return / 100 / 12
    n = int(years * 12)

    net_worth = current_assets - current_debts
    projection = []

    assets = current_assets
    debts = current_debts

    for year in range(1, int(years) + 1):
        for _ in range(12):
            assets = assets * (1 + mr) + monthly_savings
            debts = max(0, debts * 0.98)  # Assume ~2% monthly debt reduction
        projection.append({
            'year': year,
            'assets': round(assets, 2),
            'debts': round(debts, 2),
            'net_worth': round(assets - debts, 2)
        })

    return {
        'current_net_worth': round(current_assets - current_debts, 2),
        'projected_net_worth': round(assets - debts, 2),
        'growth': round((assets - debts) - (current_assets - current_debts), 2),
        'projection': projection
    }


@calculator_bp.route("/calculator")
@login_required
def calculator_view():
    # Pre-load user creditors for debt payoff calculator if logged in
    creditors = []
    total_assets = 0
    total_debts = 0
    monthly_savings = 0

    if hasattr(current_user, 'id') and current_user.is_authenticated:
        creds = Creditor.query.filter(
            Creditor.user_id == current_user.id,
            Creditor.status == 'active',
            Creditor.amount > 0
        ).all()
        creditors = [{
            'name': c.name, 'balance': c.amount,
            'rate': c.interest_rate or 0,
            'min_payment': c.minimum_payment or 0
        } for c in creds]

        total_assets = db.session.query(func.sum(Wallet.balance)).filter(
            Wallet.user_id == current_user.id
        ).scalar() or 0
        total_debts = db.session.query(func.sum(Creditor.amount)).filter(
            Creditor.user_id == current_user.id, Creditor.status == 'active'
        ).scalar() or 0

        now = datetime.utcnow()
        month_ago = now - timedelta(days=30)
        income = db.session.query(func.sum(Expense.amount)).filter(
            Expense.user_id == current_user.id, Expense.transaction_type == 'income',
            Expense.date >= month_ago
        ).scalar() or 0
        expenses = db.session.query(func.sum(Expense.amount)).filter(
            Expense.user_id == current_user.id, Expense.transaction_type == 'expense',
            Expense.date >= month_ago
        ).scalar() or 0
        monthly_savings = max(0, income - expenses)

    return render_template("calculator.html", creditors=creditors,
                           total_assets=total_assets, total_debts=total_debts,
                           monthly_savings=monthly_savings)


@calculator_bp.route("/calculator/compute", methods=['POST'])
@login_required
def calculator_compute():
    """Server-side calculation endpoint returning JSON results with breakdowns."""
    data = request.get_json()
    calc_type = data.get('type')

    if calc_type == 'loan':
        result = calc_loan_amortization(
            float(data.get('principal', 0)),
            float(data.get('rate', 0)),
            float(data.get('years', 0))
        )
    elif calc_type == 'compound':
        result = calc_compound_interest(
            float(data.get('principal', 0)),
            float(data.get('monthly_contrib', 0)),
            float(data.get('rate', 0)),
            float(data.get('years', 0))
        )
    elif calc_type == 'savings':
        result = calc_savings_goal(
            float(data.get('target', 0)),
            float(data.get('current', 0)),
            float(data.get('rate', 0)),
            float(data.get('years', 0))
        )
    elif calc_type == 'debt_payoff':
        creds = Creditor.query.filter(
            Creditor.user_id == current_user.id,
            Creditor.status == 'active',
            Creditor.amount > 0
        ).all()
        creditors_data = [{
            'name': c.name, 'balance': c.amount,
            'rate': c.interest_rate or 0,
            'min_payment': c.minimum_payment or 0
        } for c in creds]
        result = calc_debt_payoff_strategies(
            creditors_data,
            float(data.get('extra_payment', 0))
        )
    elif calc_type == 'net_worth':
        result = calc_net_worth_projection(
            float(data.get('assets', 0)),
            float(data.get('debts', 0)),
            float(data.get('monthly_savings', 0)),
            float(data.get('rate', 0)),
            float(data.get('years', 0))
        )
    else:
        return jsonify({'error': 'Unknown calculator type'}), 400

    if result is None:
        return jsonify({'error': 'Invalid input values'}), 400

    return jsonify(result)
