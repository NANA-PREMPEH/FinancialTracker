"""
Insurance Policies API endpoints for the REST API.

Provides CRUD operations for insurance policies.
"""

from flask import jsonify, request, g
from . import api_bp, require_api_key, paginate_query
from ..models import InsurancePolicy
from .. import db
from datetime import datetime


def serialize_policy(p):
    return {
        'id': p.id,
        'provider': p.provider,
        'policy_number': p.policy_number,
        'policy_type': p.policy_type,
        'premium': p.premium,
        'coverage': p.coverage,
        'start_date': p.start_date.isoformat() if p.start_date else None,
        'end_date': p.end_date.isoformat() if p.end_date else None,
        'notes': p.notes,
        'created_at': p.created_at.isoformat() if p.created_at else None,
    }


@api_bp.route('/insurance', methods=['GET'])
@require_api_key('read')
def list_insurance_policies():
    query = InsurancePolicy.query.filter_by(user_id=g.api_user_id).order_by(InsurancePolicy.created_at.desc())
    items, meta = paginate_query(query)
    return jsonify({'data': [serialize_policy(p) for p in items], 'meta': meta})


@api_bp.route('/insurance/<int:id>', methods=['GET'])
@require_api_key('read')
def get_insurance_policy(id):
    p = InsurancePolicy.query.filter_by(id=id, user_id=g.api_user_id).first()
    if not p:
        return jsonify({'error': 'Insurance policy not found'}), 404
    return jsonify({'data': serialize_policy(p)})


@api_bp.route('/insurance', methods=['POST'])
@require_api_key('write')
def create_insurance_policy():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400
    
    if not data.get('provider') or not data.get('policy_type'):
        return jsonify({'error': 'Provider and policy type are required'}), 400
    
    p = InsurancePolicy(
        user_id=g.api_user_id,
        provider=data['provider'],
        policy_number=data.get('policy_number'),
        policy_type=data['policy_type'],
        premium=float(data.get('premium', 0)),
        coverage=float(data.get('coverage', 0)) if data.get('coverage') else None,
        start_date=datetime.fromisoformat(data['start_date']) if data.get('start_date') else None,
        end_date=datetime.fromisoformat(data['end_date']) if data.get('end_date') else None,
        notes=data.get('notes'),
    )
    db.session.add(p)
    db.session.commit()
    return jsonify({'data': serialize_policy(p)}), 201


@api_bp.route('/insurance/<int:id>', methods=['PUT'])
@require_api_key('write')
def update_insurance_policy(id):
    p = InsurancePolicy.query.filter_by(id=id, user_id=g.api_user_id).first()
    if not p:
        return jsonify({'error': 'Insurance policy not found'}), 404
    
    data = request.get_json()
    if 'provider' in data:
        p.provider = data['provider']
    if 'policy_number' in data:
        p.policy_number = data['policy_number']
    if 'policy_type' in data:
        p.policy_type = data['policy_type']
    if 'premium' in data:
        p.premium = float(data['premium'])
    if 'coverage' in data:
        p.coverage = float(data['coverage']) if data['coverage'] else None
    if 'start_date' in data:
        p.start_date = datetime.fromisoformat(data['start_date']) if data['start_date'] else None
    if 'end_date' in data:
        p.end_date = datetime.fromisoformat(data['end_date']) if data['end_date'] else None
    if 'notes' in data:
        p.notes = data['notes']
    
    db.session.commit()
    return jsonify({'data': serialize_policy(p)})


@api_bp.route('/insurance/<int:id>', methods=['DELETE'])
@require_api_key('write')
def delete_insurance_policy(id):
    p = InsurancePolicy.query.filter_by(id=id, user_id=g.api_user_id).first()
    if not p:
        return jsonify({'error': 'Insurance policy not found'}), 404
    
    db.session.delete(p)
    db.session.commit()
    return jsonify({'message': 'Insurance policy deleted'}), 200


@api_bp.route('/insurance/summary', methods=['GET'])
@require_api_key('read')
def insurance_summary():
    """Get summary of all insurance policies."""
    policies = InsurancePolicy.query.filter_by(user_id=g.api_user_id).all()
    
    total_coverage = sum(p.coverage or 0 for p in policies)
    total_premium = sum(p.premium for p in policies)
    
    by_type = {}
    for p in policies:
        t = p.policy_type
        if t not in by_type:
            by_type[t] = {'count': 0, 'total_premium': 0, 'total_coverage': 0}
        by_type[t]['count'] += 1
        by_type[t]['total_premium'] += p.premium
        by_type[t]['total_coverage'] += p.coverage or 0
    
    return jsonify({
        'total_coverage': total_coverage,
        'total_premium': total_premium,
        'count': len(policies),
        'by_type': by_type,
    })
