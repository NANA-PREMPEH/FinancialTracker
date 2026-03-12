"""
Debtors API endpoints for the REST API.

Provides CRUD operations for debtors and payments.
"""

from flask import jsonify, request, g
from . import api_bp, require_api_key, paginate_query
from ..models import Debtor, DebtorPayment
from .. import db
from datetime import datetime


def serialize_debtor(d):
    return {
        'id': d.id,
        'name': d.name,
        'amount': d.amount,
        'due_date': d.due_date.isoformat() if d.due_date else None,
        'status': d.status,
        'notes': d.notes,
        'created_at': d.created_at.isoformat() if d.created_at else None,
    }


@api_bp.route('/debtors', methods=['GET'])
@require_api_key('read')
def list_debtors():
    query = Debtor.query.filter_by(user_id=g.api_user_id).order_by(Debtor.created_at.desc())
    items, meta = paginate_query(query)
    return jsonify({'data': [serialize_debtor(d) for d in items], 'meta': meta})


@api_bp.route('/debtors/<int:id>', methods=['GET'])
@require_api_key('read')
def get_debtor(id):
    d = Debtor.query.filter_by(id=id, user_id=g.api_user_id).first()
    if not d:
        return jsonify({'error': 'Debtor not found'}), 404
    return jsonify({'data': serialize_debtor(d)})


@api_bp.route('/debtors', methods=['POST'])
@require_api_key('write')
def create_debtor():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400
    
    if not data.get('name') or not data.get('amount'):
        return jsonify({'error': 'Name and amount are required'}), 400
    
    d = Debtor(
        user_id=g.api_user_id,
        name=data['name'],
        amount=float(data['amount']),
        due_date=datetime.fromisoformat(data['due_date']) if data.get('due_date') else None,
        status=data.get('status', 'active'),
        notes=data.get('notes'),
    )
    db.session.add(d)
    db.session.commit()
    return jsonify({'data': serialize_debtor(d)}), 201


@api_bp.route('/debtors/<int:id>', methods=['PUT'])
@require_api_key('write')
def update_debtor(id):
    d = Debtor.query.filter_by(id=id, user_id=g.api_user_id).first()
    if not d:
        return jsonify({'error': 'Debtor not found'}), 404
    
    data = request.get_json()
    if 'name' in data:
        d.name = data['name']
    if 'amount' in data:
        d.amount = float(data['amount'])
    if 'due_date' in data:
        d.due_date = datetime.fromisoformat(data['due_date']) if data['due_date'] else None
    if 'status' in data:
        d.status = data['status']
    if 'notes' in data:
        d.notes = data['notes']
    
    db.session.commit()
    return jsonify({'data': serialize_debtor(d)})


@api_bp.route('/debtors/<int:id>', methods=['DELETE'])
@require_api_key('write')
def delete_debtor(id):
    d = Debtor.query.filter_by(id=id, user_id=g.api_user_id).first()
    if not d:
        return jsonify({'error': 'Debtor not found'}), 404
    
    db.session.delete(d)
    db.session.commit()
    return jsonify({'message': 'Debtor deleted'}), 200


@api_bp.route('/debtors/<int:id>/payments', methods=['GET'])
@require_api_key('read')
def list_debtor_payments(id):
    d = Debtor.query.filter_by(id=id, user_id=g.api_user_id).first()
    if not d:
        return jsonify({'error': 'Debtor not found'}), 404
    
    payments = DebtorPayment.query.filter_by(debtor_id=id).order_by(DebtorPayment.payment_date.desc()).all()
    return jsonify({
        'data': [{
            'id': p.id,
            'amount': p.amount,
            'payment_date': p.payment_date.isoformat() if p.payment_date else None,
            'notes': p.notes,
        } for p in payments]
    })


@api_bp.route('/debtors/<int:id>/payments', methods=['POST'])
@require_api_key('write')
def create_debtor_payment(id):
    d = Debtor.query.filter_by(id=id, user_id=g.api_user_id).first()
    if not d:
        return jsonify({'error': 'Debtor not found'}), 404
    
    data = request.get_json()
    if not data or not data.get('amount'):
        return jsonify({'error': 'Amount is required'}), 400
    
    payment = DebtorPayment(
        debtor_id=id,
        amount=float(data['amount']),
        payment_date=datetime.fromisoformat(data['payment_date']) if data.get('payment_date') else datetime.utcnow(),
        notes=data.get('notes'),
    )
    db.session.add(payment)
    
    # Reduce debtor amount
    d.amount = max(0, d.amount - float(data['amount']))
    if d.amount == 0:
        d.status = 'paid'
    
    db.session.commit()
    return jsonify({'message': 'Payment recorded'}), 201
