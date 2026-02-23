from flask import jsonify, request, g
from . import api_bp, require_api_key, paginate_query
from ..models import Expense, Category, Wallet
from .. import db
from datetime import datetime


def serialize_transaction(t):
    return {
        'id': t.id,
        'date': t.date.isoformat() if t.date else None,
        'description': t.description,
        'amount': t.amount,
        'transaction_type': t.transaction_type,
        'category': t.category.name if t.category else None,
        'category_id': t.category_id,
        'wallet': t.wallet.name if t.wallet else None,
        'wallet_id': t.wallet_id,
        'tags': t.tags,
        'notes': t.notes,
        'created_at': t.created_at.isoformat() if t.created_at else None,
    }


@api_bp.route('/transactions', methods=['GET'])
@require_api_key('read')
def list_transactions():
    query = Expense.query.filter_by(user_id=g.api_user_id).order_by(Expense.date.desc())

    # Filters
    tx_type = request.args.get('type')
    if tx_type in ('income', 'expense'):
        query = query.filter_by(transaction_type=tx_type)

    category_id = request.args.get('category_id', type=int)
    if category_id:
        query = query.filter_by(category_id=category_id)

    wallet_id = request.args.get('wallet_id', type=int)
    if wallet_id:
        query = query.filter_by(wallet_id=wallet_id)

    items, meta = paginate_query(query)
    return jsonify({'data': [serialize_transaction(t) for t in items], 'meta': meta})


@api_bp.route('/transactions/<int:id>', methods=['GET'])
@require_api_key('read')
def get_transaction(id):
    t = Expense.query.filter_by(id=id, user_id=g.api_user_id).first()
    if not t:
        return jsonify({'error': 'Transaction not found'}), 404
    return jsonify({'data': serialize_transaction(t)})


@api_bp.route('/transactions', methods=['POST'])
@require_api_key('write_transactions')
def create_transaction():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    required = ['amount', 'category_id', 'wallet_id']
    for field in required:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400

    t = Expense(
        user_id=g.api_user_id,
        description=data.get('description', ''),
        amount=float(data['amount']),
        transaction_type=data.get('transaction_type', 'expense'),
        category_id=int(data['category_id']),
        wallet_id=int(data['wallet_id']),
        date=datetime.fromisoformat(data['date']) if data.get('date') else datetime.utcnow(),
        tags=data.get('tags'),
        notes=data.get('notes'),
    )
    db.session.add(t)

    # Update wallet balance
    wallet = Wallet.query.get(t.wallet_id)
    if wallet:
        if t.transaction_type == 'income':
            wallet.balance += t.amount
        else:
            wallet.balance -= t.amount

    db.session.commit()
    return jsonify({'data': serialize_transaction(t)}), 201


@api_bp.route('/transactions/<int:id>', methods=['PUT'])
@require_api_key('write_transactions')
def update_transaction(id):
    t = Expense.query.filter_by(id=id, user_id=g.api_user_id).first()
    if not t:
        return jsonify({'error': 'Transaction not found'}), 404

    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    if 'description' in data:
        t.description = data['description']
    if 'amount' in data:
        t.amount = float(data['amount'])
    if 'transaction_type' in data:
        t.transaction_type = data['transaction_type']
    if 'category_id' in data:
        t.category_id = int(data['category_id'])
    if 'date' in data:
        t.date = datetime.fromisoformat(data['date'])
    if 'tags' in data:
        t.tags = data['tags']
    if 'notes' in data:
        t.notes = data['notes']

    db.session.commit()
    return jsonify({'data': serialize_transaction(t)})


@api_bp.route('/transactions/<int:id>', methods=['DELETE'])
@require_api_key('write_transactions')
def delete_transaction(id):
    t = Expense.query.filter_by(id=id, user_id=g.api_user_id).first()
    if not t:
        return jsonify({'error': 'Transaction not found'}), 404

    # Reverse wallet balance
    wallet = Wallet.query.get(t.wallet_id)
    if wallet:
        if t.transaction_type == 'income':
            wallet.balance -= t.amount
        else:
            wallet.balance += t.amount

    db.session.delete(t)
    db.session.commit()
    return jsonify({'message': 'Transaction deleted'}), 200
