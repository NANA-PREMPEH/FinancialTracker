from flask import jsonify, g, request
from . import api_bp, require_api_key
from ..models import Category
from .. import db


def serialize_category(c):
    return {
        'id': c.id,
        'name': c.name,
        'icon': c.icon,
        'is_custom': c.is_custom,
    }


@api_bp.route('/categories', methods=['GET'])
@require_api_key('read')
def list_categories():
    categories = Category.query.filter(
        (Category.user_id == g.api_user_id) | (Category.user_id == None)
    ).all()
    return jsonify({'data': [serialize_category(c) for c in categories]})


@api_bp.route('/categories/bulk', methods=['POST'])
@require_api_key('write')
def bulk_create_categories():
    """Create up to 100 categories in one call."""
    data = request.get_json()
    if not data or not isinstance(data, list):
        return jsonify({'error': 'JSON array of categories required'}), 400
    
    if len(data) > 100:
        return jsonify({'error': 'Maximum 100 categories per bulk request'}), 400
    
    if len(data) == 0:
        return jsonify({'error': 'At least one category required'}), 400
    
    created = []
    errors = []
    
    for i, item in enumerate(data):
        try:
            if not item.get('name'):
                errors.append({'index': i, 'error': 'Name is required'})
                continue
            
            # Check if category already exists for this user
            existing = Category.query.filter_by(
                user_id=g.api_user_id, 
                name=item['name']
            ).first()
            
            if existing:
                errors.append({'index': i, 'error': f'Category "{item["name"]}" already exists'})
                continue
            
            c = Category(
                user_id=g.api_user_id,
                name=item['name'],
                icon=item.get('icon', '📁'),
                is_custom=True,
            )
            db.session.add(c)
            created.append(c)
        except Exception as e:
            errors.append({'index': i, 'error': str(e)})
    
    db.session.commit()
    
    return jsonify({
        'message': f'{len(created)} categories created',
        'created': [serialize_category(c) for c in created],
        'errors': errors if errors else None
    }), 201 if created else 400
