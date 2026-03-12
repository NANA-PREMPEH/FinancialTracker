"""
Creditors API endpoints for the REST API.

Provides CRUD operations for creditors and payments.
"""

from flask import jsonify, request, g
from . import api_bp, require_api_key, paginate_query
from ..models import Creditor, DebtPayment
from .. import db
from datetime import datetime


def serialize_creditor(c):
    return {
        'id': c.id,
        'name': c.name,
        'amount': c.amount,
        'interest_rate': c.interest_rate,
        'debt_type': c.debt_type,
        'due_date': c.due_date.isoformat() if c.due_date else None,
        'status': c.status,
        'created_at': c.created_at.isoformat() if c.created_at else None,
    }


@api_bp.route('/creditors', methods=['GET'])
@require_api_key('read')
def list_creditors():
    query = Creditor.query.filter_by(user_id=g.api_user_id).order_by(Creditor.created_at.desc())
    items, meta = paginate_query(query)
    return jsonify({'data': [serialize_creditor(c) for c in items], 'meta': meta})


@api_bp.route('/creditors/<int:id>', methods=['GET'])
@require_api_key('read')
def get_creditor(id):
    c = Creditor.query.filter_by(id=id, user_id=g.api_user_id).first()
    if not c:
        return jsonify({'error': 'Creditor not found'}), 404
    return jsonify({'data': serialize_creditor(c)})


@api_bp.route('/creditors', methods=['POST'])
@require_api_key('write')
def create_creditor():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400
    
    if not data.get('name') or not data.get('amount'):
        return jsonify({'error': 'Name and amount are required'}), 400
    
    c = Creditor(
        user_id=g.api_user_id,
        name=data['name'],
        amount=float(data['amount']),
        interest_rate=data.get('interest_rate', 0),
        debt_type=data.get('debt_type', 'personal'),
        due_date=datetime.fromisoformat(data['due_date']) if data.get('due_date') else None,
        status=data.get('status', 'active'),
    )
    db.session.add(c)
    db.session.commit()
    return jsonify({'data': serialize_creditor(c)}), 201


@api_bp.route('/creditors/<int:id>', methods=['PUT'])
@require_api_key('write')
def update_creditor(id):
    c = Creditor.query.filter_by(id=id, user_id=g.api_user_id).first()
    if not c:
        return jsonify({'error': 'Creditor not found'}), 404
    
    data = request.get_json()
    if 'name' in data:
        c.name = data['name']
    if 'amount' in data:
        c.amount = float(data['amount'])
    if 'interest_rate' in data:
        c.interest_rate = data['interest_rate']
    if 'debt_type' in data:
        c.debt_type = data['debt_type']
    if 'due_date' in data:
        c.due_date = datetime.fromisoformat(data['due_date']) if data['due_date'] else None
    if 'status' in data:
        c.status = data['status']
    
    db.session.commit()
    return jsonify({'data': serialize_creditor(c)})


@api_bp.route('/creditors/<int:id>', methods=['DELETE'])
@require_api_key('write')
def delete_creditor(id):
    c = Creditor.query.filter_by(id=id, user_id=g.api_user_id).first()
    if not c:
        return jsonify({'error': 'Creditor not found'}), 404
    
    db.session.delete(c)
    db.session.commit()
    return jsonify({'message': 'Creditor deleted'}), 200


@api_bp.route('/creditors/<int:id>/payments', methods=['GET'])
@require_api_key('read')
def list_creditor_payments(id):
    c = Creditor.query.filter_by(id=id, user_id=g.api_user_id).first()
    if not c:
        return jsonify({'error': 'Creditor not found'}), 404
    
    payments = DebtPayment.query.filter_by(creditor_id=id).order_by(DebtPayment.payment_date.desc()).all()
    return jsonify({
        'data': [{
            'id': p.id,
            'amount': p.amount,
            'payment_date': p.payment_date.isoformat() if p.payment_date else None,
            'notes': p.notes,
        } for p in payments]
    })


@api_bp.route('/creditors/<int:id>/payments', methods=['POST'])
@require_api_key('write')
def create_creditor_payment(id):
    c = Creditor.query.filter_by(id=id, user_id=g.api_user_id).first()
    if not c:
        return jsonify({'error': 'Creditor not found'}), 404
    
    data = request.get_json()
    if not data or not data.get('amount'):
        return jsonify({'error': 'Amount is required'}), 400
    
    payment = DebtPayment(
        creditor_id=id,
        amount=float(data['amount']),
        payment_date=datetime.fromisoformat(data['payment_date']) if data.get('payment_date') else datetime.utcnow(),
        notes=data.get('notes'),
    )
    db.session.add(payment)
    
    # Reduce creditor amount
    c.amount = max(0, c.amount - float(data['amount']))
    if c.amount == 0:
        c.status = 'paid'
    
    db.session.commit()
    return jsonify({'message': 'Payment recorded'}), 201
