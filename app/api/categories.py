from flask import jsonify, g
from . import api_bp, require_api_key
from ..models import Category


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
