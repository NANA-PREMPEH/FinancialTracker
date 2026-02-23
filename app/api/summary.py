from flask import jsonify, g
from . import api_bp, require_api_key
from ..models import Expense, Wallet, Budget, Goal, Creditor, Category
from .. import db
from datetime import datetime
from sqlalchemy import func


@api_bp.route('/summary', methods=['GET'])
@require_api_key('read')
def dashboard_summary():
    user_id = g.api_user_id
    now = datetime.utcnow()
    month_start = datetime(now.year, now.month, 1)
    year_start = datetime(now.year, 1, 1)

    # Totals
    total_income = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == user_id, Expense.transaction_type == 'income'
    ).scalar() or 0

    total_expense = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == user_id, Expense.transaction_type == 'expense'
    ).scalar() or 0

    monthly_expense = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == user_id, Expense.transaction_type == 'expense',
        Expense.date >= month_start
    ).scalar() or 0

    yearly_expense = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == user_id, Expense.transaction_type == 'expense',
        Expense.date >= year_start
    ).scalar() or 0

    # Wallet balances
    wallets = Wallet.query.filter_by(user_id=user_id).all()
    wallet_balance = sum(w.balance for w in wallets)

    # Debts
    total_debt = db.session.query(func.sum(Creditor.amount)).filter(
        Creditor.user_id == user_id
    ).scalar() or 0

    # Goals progress
    goals = Goal.query.filter_by(user_id=user_id).all()
    goals_count = len(goals)
    goals_completed = sum(1 for g_item in goals if g_item.current_amount >= g_item.target_amount)

    # Category spending this month
    category_spending = db.session.query(
        Category.name, func.sum(Expense.amount)
    ).join(Category).filter(
        Expense.user_id == user_id,
        Expense.transaction_type == 'expense',
        Expense.date >= month_start
    ).group_by(Category.name).order_by(func.sum(Expense.amount).desc()).limit(10).all()

    return jsonify({
        'data': {
            'total_income': float(total_income),
            'total_expense': float(total_expense),
            'monthly_expense': float(monthly_expense),
            'yearly_expense': float(yearly_expense),
            'wallet_balance': float(wallet_balance),
            'total_debt': float(total_debt),
            'net_worth': float(wallet_balance - total_debt),
            'goals_total': goals_count,
            'goals_completed': goals_completed,
            'category_spending': [
                {'category': name, 'amount': float(amount)}
                for name, amount in category_spending
            ],
            'transaction_count': Expense.query.filter_by(user_id=user_id).count(),
        }
    })
