from flask import jsonify, request, g
from . import api_bp, require_api_key
from ..models import Budget, Category, Expense
from .. import db
from datetime import datetime, timedelta
from sqlalchemy import func


def serialize_budget(b):
    # Calculate spent amount
    now = datetime.utcnow()
    if b.period == 'weekly':
        start = now - timedelta(days=now.weekday())
    elif b.period == 'yearly':
        start = datetime(now.year, 1, 1)
    else:
        start = datetime(now.year, now.month, 1)

    spent = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == b.user_id,
        Expense.category_id == b.category_id,
        Expense.transaction_type == 'expense',
        Expense.date >= start
    ).scalar() or 0

    return {
        'id': b.id,
        'category': b.category.name if b.category else None,
        'category_id': b.category_id,
        'amount': b.amount,
        'period': b.period,
        'spent': float(spent),
        'remaining': b.amount - float(spent),
        'percent_used': round((float(spent) / b.amount * 100), 1) if b.amount > 0 else 0,
    }


@api_bp.route('/budgets', methods=['GET'])
@require_api_key('read')
def list_budgets():
    budgets = Budget.query.filter_by(user_id=g.api_user_id).all()
    return jsonify({'data': [serialize_budget(b) for b in budgets]})


@api_bp.route('/budgets', methods=['POST'])
@require_api_key('write_budgets')
def create_budget():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    if not data.get('category_id') or not data.get('amount'):
        return jsonify({'error': 'category_id and amount are required'}), 400

    period = data.get('period', 'monthly')
    start_date = datetime.fromisoformat(data['start_date']) if data.get('start_date') else datetime.utcnow()

    if period == 'weekly':
        end_date = start_date + timedelta(days=7)
    elif period == 'yearly':
        end_date = start_date + timedelta(days=365)
    else:
        end_date = start_date + timedelta(days=30)

    b = Budget(
        user_id=g.api_user_id,
        category_id=int(data['category_id']),
        amount=float(data['amount']),
        period=period,
        start_date=start_date,
        end_date=end_date,
    )
    db.session.add(b)
    db.session.commit()
    return jsonify({'data': serialize_budget(b)}), 201
