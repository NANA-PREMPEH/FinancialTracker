"""
Pension Schemes API endpoints for the REST API.

Provides CRUD operations for pension schemes.
"""

from flask import jsonify, request, g
from . import api_bp, require_api_key, paginate_query
from ..models import PensionScheme
from .. import db
from datetime import datetime


def serialize_pension(p):
    return {
        'id': p.id,
        'name': p.name,
        'scheme_type': p.scheme_type,
        'contributions': p.contributions,
        'employer_match': p.employer_match,
        'balance': p.balance,
        'notes': p.notes,
        'created_at': p.created_at.isoformat() if p.created_at else None,
    }


@api_bp.route('/pensions', methods=['GET'])
@require_api_key('read')
def list_pension_schemes():
    query = PensionScheme.query.filter_by(user_id=g.api_user_id).order_by(PensionScheme.created_at.desc())
    items, meta = paginate_query(query)
    return jsonify({'data': [serialize_pension(p) for p in items], 'meta': meta})


@api_bp.route('/pensions/<int:id>', methods=['GET'])
@require_api_key('read')
def get_pension_scheme(id):
    p = PensionScheme.query.filter_by(id=id, user_id=g.api_user_id).first()
    if not p:
        return jsonify({'error': 'Pension scheme not found'}), 404
    return jsonify({'data': serialize_pension(p)})


@api_bp.route('/pensions', methods=['POST'])
@require_api_key('write')
def create_pension_scheme():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400
    
    if not data.get('name') or not data.get('scheme_type'):
        return jsonify({'error': 'Name and scheme type are required'}), 400
    
    p = PensionScheme(
        user_id=g.api_user_id,
        name=data['name'],
        scheme_type=data['scheme_type'],
        contributions=float(data.get('contributions', 0)),
        employer_match=float(data.get('employer_match', 0)),
        balance=float(data.get('balance', 0)),
        notes=data.get('notes'),
    )
    db.session.add(p)
    db.session.commit()
    return jsonify({'data': serialize_pension(p)}), 201


@api_bp.route('/pensions/<int:id>', methods=['PUT'])
@require_api_key('write')
def update_pension_scheme(id):
    p = PensionScheme.query.filter_by(id=id, user_id=g.api_user_id).first()
    if not p:
        return jsonify({'error': 'Pension scheme not found'}), 404
    
    data = request.get_json()
    if 'name' in data:
        p.name = data['name']
    if 'scheme_type' in data:
        p.scheme_type = data['scheme_type']
    if 'contributions' in data:
        p.contributions = float(data['contributions'])
    if 'employer_match' in data:
        p.employer_match = float(data['employer_match'])
    if 'balance' in data:
        p.balance = float(data['balance'])
    if 'notes' in data:
        p.notes = data['notes']
    
    db.session.commit()
    return jsonify({'data': serialize_pension(p)})


@api_bp.route('/pensions/<int:id>', methods=['DELETE'])
@require_api_key('write')
def delete_pension_scheme(id):
    p = PensionScheme.query.filter_by(id=id, user_id=g.api_user_id).first()
    if not p:
        return jsonify({'error': 'Pension scheme not found'}), 404
    
    db.session.delete(p)
    db.session.commit()
    return jsonify({'message': 'Pension scheme deleted'}), 200


@api_bp.route('/pensions/summary', methods=['GET'])
@require_api_key('read')
def pensions_summary():
    """Get summary of all pension schemes."""
    schemes = PensionScheme.query.filter_by(user_id=g.api_user_id).all()
    
    total_balance = sum(p.balance for p in schemes)
    total_contributions = sum(p.contributions for p in schemes)
    total_employer_match = sum(p.employer_match for p in schemes)
    
    by_type = {}
    for p in schemes:
        t = p.scheme_type
        if t not in by_type:
            by_type[t] = {'count': 0, 'total_balance': 0}
        by_type[t]['count'] += 1
        by_type[t]['total_balance'] += p.balance
    
    return jsonify({
        'total_balance': total_balance,
        'total_contributions': total_contributions,
        'total_employer_match': total_employer_match,
        'count': len(schemes),
        'by_type': by_type,
    })
