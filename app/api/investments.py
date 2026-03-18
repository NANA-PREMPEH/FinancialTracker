"""
Investments API endpoints for the REST API.

Provides CRUD operations for investments and dividends.
"""

from flask import jsonify, request, g
from . import api_bp, require_api_key, paginate_query
from ..models import Investment, Dividend
from .. import db
from datetime import datetime


def serialize_investment(i):
    return {
        'id': i.id,
        'name': i.name,
        'investment_type': i.investment_type,
        'amount_invested': i.amount_invested,
        'current_value': i.current_value,
        'purchase_date': i.purchase_date.isoformat() if i.purchase_date else None,
        'platform': i.platform,
        'notes': i.notes,
        'roi': i.roi,
        'created_at': i.created_at.isoformat() if i.created_at else None,
    }


def serialize_dividend(d):
    return {
        'id': d.id,
        'investment_id': d.investment_id,
        'amount': d.amount,
        'date': d.date.isoformat() if d.date else None,
        'notes': d.notes,
    }


@api_bp.route('/investments', methods=['GET'])
@require_api_key('read')
def list_investments():
    query = Investment.query.filter_by(user_id=g.api_user_id).order_by(Investment.created_at.desc())
    items, meta = paginate_query(query)
    return jsonify({'data': [serialize_investment(i) for i in items], 'meta': meta})


@api_bp.route('/investments/<int:id>', methods=['GET'])
@require_api_key('read')
def get_investment(id):
    i = Investment.query.filter_by(id=id, user_id=g.api_user_id).first()
    if not i:
        return jsonify({'error': 'Investment not found'}), 404
    return jsonify({'data': serialize_investment(i)})


@api_bp.route('/investments', methods=['POST'])
@require_api_key('write')
def create_investment():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400
    
    if not data.get('name') or not data.get('investment_type'):
        return jsonify({'error': 'Name and investment type are required'}), 400
    
    i = Investment(
        user_id=g.api_user_id,
        name=data['name'],
        investment_type=data['investment_type'],
        amount_invested=float(data.get('amount_invested', 0)),
        current_value=float(data.get('current_value', data.get('amount_invested', 0))),
        purchase_date=datetime.fromisoformat(data['purchase_date']) if data.get('purchase_date') else None,
        platform=data.get('platform'),
        notes=data.get('notes'),
    )
    db.session.add(i)
    db.session.commit()
    return jsonify({'data': serialize_investment(i)}), 201


@api_bp.route('/investments/<int:id>', methods=['PUT'])
@require_api_key('write')
def update_investment(id):
    i = Investment.query.filter_by(id=id, user_id=g.api_user_id).first()
    if not i:
        return jsonify({'error': 'Investment not found'}), 404
    
    data = request.get_json()
    if 'name' in data:
        i.name = data['name']
    if 'investment_type' in data:
        i.investment_type = data['investment_type']
    if 'amount_invested' in data:
        i.amount_invested = float(data['amount_invested'])
    if 'current_value' in data:
        i.current_value = float(data['current_value'])
    if 'purchase_date' in data:
        i.purchase_date = datetime.fromisoformat(data['purchase_date']) if data['purchase_date'] else None
    if 'platform' in data:
        i.platform = data['platform']
    if 'notes' in data:
        i.notes = data['notes']
    
    db.session.commit()
    return jsonify({'data': serialize_investment(i)})


@api_bp.route('/investments/<int:id>', methods=['DELETE'])
@require_api_key('write')
def delete_investment(id):
    i = Investment.query.filter_by(id=id, user_id=g.api_user_id).first()
    if not i:
        return jsonify({'error': 'Investment not found'}), 404
    
    db.session.delete(i)
    db.session.commit()
    return jsonify({'message': 'Investment deleted'}), 200


@api_bp.route('/investments/<int:id>/dividends', methods=['GET'])
@require_api_key('read')
def list_dividends(id):
    i = Investment.query.filter_by(id=id, user_id=g.api_user_id).first()
    if not i:
        return jsonify({'error': 'Investment not found'}), 404
    
    dividends = Dividend.query.filter_by(investment_id=id).order_by(Dividend.date.desc()).all()
    return jsonify({'data': [serialize_dividend(d) for d in dividends]})


@api_bp.route('/investments/<int:id>/dividends', methods=['POST'])
@require_api_key('write')
def create_dividend(id):
    i = Investment.query.filter_by(id=id, user_id=g.api_user_id).first()
    if not i:
        return jsonify({'error': 'Investment not found'}), 404
    
    data = request.get_json()
    if not data or not data.get('amount') or not data.get('date'):
        return jsonify({'error': 'Amount and date are required'}), 400
    
    dividend = Dividend(
        investment_id=id,
        user_id=g.api_user_id,
        amount=float(data['amount']),
        date=datetime.fromisoformat(data['date']),
        notes=data.get('notes'),
    )
    db.session.add(dividend)
    db.session.commit()
    return jsonify({'data': serialize_dividend(dividend)}), 201


@api_bp.route('/investments/summary', methods=['GET'])
@require_api_key('read')
def investments_summary():
    """Get summary statistics for all investments."""
    investments = Investment.query.filter_by(user_id=g.api_user_id).all()
    
    total_invested = sum(i.amount_invested for i in investments)
    total_value = sum(i.current_value for i in investments)
    total_roi = ((total_value - total_invested) / total_invested * 100) if total_invested > 0 else 0
    
    by_type = {}
    for i in investments:
        t = i.investment_type
        if t not in by_type:
            by_type[t] = {'count': 0, 'total_value': 0}
        by_type[t]['count'] += 1
        by_type[t]['total_value'] += i.current_value
    
    return jsonify({
        'total_invested': total_invested,
        'total_value': total_value,
        'total_roi': round(total_roi, 2),
        'count': len(investments),
        'by_type': by_type,
    })
