"""
Commitments API endpoints for the REST API.

Provides CRUD operations for financial commitments (recurring obligations).
"""

from flask import jsonify, request, g
from . import api_bp, require_api_key, paginate_query
from ..models import Commitment
from .. import db
from datetime import datetime


def serialize_commitment(c):
    return {
        'id': c.id,
        'name': c.name,
        'amount': c.amount,
        'frequency': c.frequency,
        'category': c.commitment_category,
        'due_date': c.due_date.isoformat() if c.due_date else None,
        'status': c.status,
        'notes': c.notes,
        'created_at': c.created_at.isoformat() if c.created_at else None,
    }


@api_bp.route('/commitments', methods=['GET'])
@require_api_key('read')
def list_commitments():
    query = Commitment.query.filter_by(user_id=g.api_user_id).order_by(Commitment.created_at.desc())
    items, meta = paginate_query(query)
    return jsonify({'data': [serialize_commitment(c) for c in items], 'meta': meta})


@api_bp.route('/commitments/active', methods=['GET'])
@require_api_key('read')
def list_active_commitments():
    """Get only active commitments (useful for budget calculations)."""
    commitments = Commitment.query.filter_by(user_id=g.api_user_id, status='pending').order_by(Commitment.name).all()
    return jsonify({'data': [serialize_commitment(c) for c in commitments]})


@api_bp.route('/commitments/<int:id>', methods=['GET'])
@require_api_key('read')
def get_commitment(id):
    c = Commitment.query.filter_by(id=id, user_id=g.api_user_id).first()
    if not c:
        return jsonify({'error': 'Commitment not found'}), 404
    return jsonify({'data': serialize_commitment(c)})


@api_bp.route('/commitments', methods=['POST'])
@require_api_key('write')
def create_commitment():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400
    
    if not data.get('name') or not data.get('amount') or not data.get('frequency'):
        return jsonify({'error': 'Name, amount, and frequency are required'}), 400
    
    c = Commitment(
        user_id=g.api_user_id,
        name=data['name'],
        amount=float(data['amount']),
        frequency=data['frequency'],
        commitment_category=data.get('category', 'Custom'),
        due_date=datetime.fromisoformat(data['due_date']) if data.get('due_date') else None,
        status=data.get('status', 'pending'),
        notes=data.get('notes'),
    )
    db.session.add(c)
    db.session.commit()
    return jsonify({'data': serialize_commitment(c)}), 201


@api_bp.route('/commitments/<int:id>', methods=['PUT'])
@require_api_key('write')
def update_commitment(id):
    c = Commitment.query.filter_by(id=id, user_id=g.api_user_id).first()
    if not c:
        return jsonify({'error': 'Commitment not found'}), 404
    
    data = request.get_json()
    if 'name' in data:
        c.name = data['name']
    if 'amount' in data:
        c.amount = float(data['amount'])
    if 'frequency' in data:
        c.frequency = data['frequency']
    if 'category' in data:
        c.commitment_category = data['category']
    if 'due_date' in data:
        c.due_date = datetime.fromisoformat(data['due_date']) if data['due_date'] else None
    if 'status' in data:
        c.status = data['status']
    if 'notes' in data:
        c.notes = data['notes']
    
    db.session.commit()
    return jsonify({'data': serialize_commitment(c)})


@api_bp.route('/commitments/<int:id>', methods=['DELETE'])
@require_api_key('write')
def delete_commitment(id):
    c = Commitment.query.filter_by(id=id, user_id=g.api_user_id).first()
    if not c:
        return jsonify({'error': 'Commitment not found'}), 404
    
    db.session.delete(c)
    db.session.commit()
    return jsonify({'message': 'Commitment deleted'}), 200


@api_bp.route('/commitments/<int:id>/toggle', methods=['POST'])
@require_api_key('write')
def toggle_commitment(id):
    """Toggle commitment active status."""
    c = Commitment.query.filter_by(id=id, user_id=g.api_user_id).first()
    if not c:
        return jsonify({'error': 'Commitment not found'}), 404
    
    c.status = 'paid' if c.status == 'pending' else 'pending'
    db.session.commit()
    return jsonify({'data': serialize_commitment(c)})
