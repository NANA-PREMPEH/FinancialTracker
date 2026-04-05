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
    wallet = Wallet.query.filter_by(id=t.wallet_id, user_id=g.api_user_id).first()
    if wallet:
        if t.transaction_type == 'income':
            wallet.balance = float(wallet.balance) + t.amount
        else:
            wallet.balance = float(wallet.balance) - t.amount

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
    wallet = Wallet.query.filter_by(id=t.wallet_id, user_id=g.api_user_id).first()
    if wallet:
        if t.transaction_type == 'income':
            wallet.balance = float(wallet.balance) - t.amount
        else:
            wallet.balance = float(wallet.balance) + t.amount

    db.session.delete(t)
    db.session.commit()
    return jsonify({'message': 'Transaction deleted'}), 200


@api_bp.route('/transactions/bulk', methods=['POST'])
@require_api_key('write_transactions')
def bulk_create_transactions():
    """Create up to 100 transactions in one call."""
    data = request.get_json()
    if not data or not isinstance(data, list):
        return jsonify({'error': 'JSON array of transactions required'}), 400
    
    if len(data) > 100:
        return jsonify({'error': 'Maximum 100 transactions per bulk request'}), 400
    
    if len(data) == 0:
        return jsonify({'error': 'At least one transaction required'}), 400
    
    created = []
    errors = []
    
    for i, item in enumerate(data):
        try:
            if not item.get('amount') or not item.get('category_id') or not item.get('wallet_id'):
                errors.append({'index': i, 'error': 'Missing required fields (amount, category_id, wallet_id)'})
                continue
            
            t = Expense(
                user_id=g.api_user_id,
                description=item.get('description', ''),
                amount=float(item['amount']),
                transaction_type=item.get('transaction_type', 'expense'),
                category_id=int(item['category_id']),
                wallet_id=int(item['wallet_id']),
                date=datetime.fromisoformat(item['date']) if item.get('date') else datetime.utcnow(),
                tags=item.get('tags'),
                notes=item.get('notes'),
            )
            
            # Update wallet balance
            wallet = Wallet.query.filter_by(id=t.wallet_id, user_id=g.api_user_id).first()
            if wallet:
                if t.transaction_type == 'income':
                    wallet.balance = float(wallet.balance) + t.amount
                else:
                    wallet.balance = float(wallet.balance) - t.amount
            
            db.session.add(t)
            created.append(t)
        except Exception as e:
            errors.append({'index': i, 'error': str(e)})
    
    db.session.commit()
    
    return jsonify({
        'message': f'{len(created)} transactions created',
        'created': [serialize_transaction(t) for t in created],
        'errors': errors if errors else None
    }), 201 if created else 400


@api_bp.route('/transactions/bulk', methods=['DELETE'])
@require_api_key('write_transactions')
def bulk_delete_transactions():
    """Delete multiple transactions by IDs."""
    data = request.get_json()
    if not data or not isinstance(data, dict):
        return jsonify({'error': 'JSON object with ids array required'}), 400
    
    ids = data.get('ids', [])
    if not ids:
        return jsonify({'error': 'ids array is required'}), 400
    
    if len(ids) > 100:
        return jsonify({'error': 'Maximum 100 IDs per bulk request'}), 400
    
    # Get all transactions that belong to user
    transactions = Expense.query.filter(
        Expense.id.in_(ids),
        Expense.user_id == g.api_user_id
    ).all()
    
    deleted_ids = []
    for t in transactions:
        # Reverse wallet balance
        wallet = Wallet.query.filter_by(id=t.wallet_id, user_id=g.api_user_id).first()
        if wallet:
            if t.transaction_type == 'income':
                wallet.balance = float(wallet.balance) - t.amount
            else:
                wallet.balance = float(wallet.balance) + t.amount
        
        db.session.delete(t)
        deleted_ids.append(t.id)
    
    not_found = set(ids) - set(deleted_ids)
    
    db.session.commit()
    
    return jsonify({
        'message': f'{len(deleted_ids)} transactions deleted',
        'deleted': deleted_ids,
        'not_found': list(not_found) if not_found else None
    })
