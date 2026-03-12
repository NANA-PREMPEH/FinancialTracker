"""
Fixed Assets API endpoints for the REST API.

Provides CRUD operations for fixed assets.
"""

from flask import jsonify, request, g
from . import api_bp, require_api_key, paginate_query
from ..models import FixedAsset
from .. import db
from datetime import datetime


def serialize_asset(a):
    return {
        'id': a.id,
        'name': a.name,
        'asset_category': a.asset_category,
        'purchase_date': a.purchase_date.isoformat() if a.purchase_date else None,
        'purchase_price': a.purchase_price,
        'current_value': a.current_value,
        'location': a.location,
        'condition': a.condition,
        'depreciation_rate': a.depreciation_rate,
        'notes': a.notes,
        'created_at': a.created_at.isoformat() if a.created_at else None,
    }


@api_bp.route('/fixed-assets', methods=['GET'])
@require_api_key('read')
def list_fixed_assets():
    query = FixedAsset.query.filter_by(user_id=g.api_user_id).order_by(FixedAsset.created_at.desc())
    items, meta = paginate_query(query)
    return jsonify({'data': [serialize_asset(a) for a in items], 'meta': meta})


@api_bp.route('/fixed-assets/<int:id>', methods=['GET'])
@require_api_key('read')
def get_fixed_asset(id):
    a = FixedAsset.query.filter_by(id=id, user_id=g.api_user_id).first()
    if not a:
        return jsonify({'error': 'Fixed asset not found'}), 404
    return jsonify({'data': serialize_asset(a)})


@api_bp.route('/fixed-assets', methods=['POST'])
@require_api_key('write')
def create_fixed_asset():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400
    
    if not data.get('name') or not data.get('asset_category'):
        return jsonify({'error': 'Name and asset category are required'}), 400
    
    a = FixedAsset(
        user_id=g.api_user_id,
        name=data['name'],
        asset_category=data['asset_category'],
        purchase_date=datetime.fromisoformat(data['purchase_date']) if data.get('purchase_date') else None,
        purchase_price=float(data.get('purchase_price', 0)),
        current_value=float(data.get('current_value', data.get('purchase_price', 0))),
        location=data.get('location'),
        condition=data.get('condition', 'Good'),
        depreciation_rate=float(data.get('depreciation_rate', 0)),
        notes=data.get('notes'),
    )
    db.session.add(a)
    db.session.commit()
    return jsonify({'data': serialize_asset(a)}), 201


@api_bp.route('/fixed-assets/<int:id>', methods=['PUT'])
@require_api_key('write')
def update_fixed_asset(id):
    a = FixedAsset.query.filter_by(id=id, user_id=g.api_user_id).first()
    if not a:
        return jsonify({'error': 'Fixed asset not found'}), 404
    
    data = request.get_json()
    if 'name' in data:
        a.name = data['name']
    if 'asset_category' in data:
        a.asset_category = data['asset_category']
    if 'purchase_date' in data:
        a.purchase_date = datetime.fromisoformat(data['purchase_date']) if data['purchase_date'] else None
    if 'purchase_price' in data:
        a.purchase_price = float(data['purchase_price'])
    if 'current_value' in data:
        a.current_value = float(data['current_value'])
    if 'location' in data:
        a.location = data['location']
    if 'condition' in data:
        a.condition = data['condition']
    if 'depreciation_rate' in data:
        a.depreciation_rate = float(data['depreciation_rate'])
    if 'notes' in data:
        a.notes = data['notes']
    
    db.session.commit()
    return jsonify({'data': serialize_asset(a)})


@api_bp.route('/fixed-assets/<int:id>', methods=['DELETE'])
@require_api_key('write')
def delete_fixed_asset(id):
    a = FixedAsset.query.filter_by(id=id, user_id=g.api_user_id).first()
    if not a:
        return jsonify({'error': 'Fixed asset not found'}), 404
    
    db.session.delete(a)
    db.session.commit()
    return jsonify({'message': 'Fixed asset deleted'}), 200


@api_bp.route('/fixed-assets/summary', methods=['GET'])
@require_api_key('read')
def fixed_assets_summary():
    """Get summary of all fixed assets."""
    assets = FixedAsset.query.filter_by(user_id=g.api_user_id).all()
    
    total_purchase = sum(a.purchase_price for a in assets)
    total_current = sum(a.current_value for a in assets)
    
    by_category = {}
    for a in assets:
        c = a.asset_category
        if c not in by_category:
            by_category[c] = {'count': 0, 'total_value': 0}
        by_category[c]['count'] += 1
        by_category[c]['total_value'] += a.current_value
    
    return jsonify({
        'total_purchase_value': total_purchase,
        'total_current_value': total_current,
        'count': len(assets),
        'by_category': by_category,
    })
