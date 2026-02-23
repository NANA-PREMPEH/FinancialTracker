from flask import Blueprint, jsonify, request, g
from functools import wraps
from werkzeug.security import check_password_hash
from datetime import datetime

api_bp = Blueprint('api', __name__, url_prefix='/api/v1')


def require_api_key(permission='read'):
    """Decorator to authenticate API requests using the existing ApiKey model."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            from ..models import ApiKey
            from .. import db

            key = request.headers.get('X-API-Key') or request.args.get('api_key')
            if not key:
                return jsonify({'error': 'API key required. Pass via X-API-Key header or api_key query parameter.'}), 401

            api_keys = ApiKey.query.filter_by(is_active=True).all()
            matched = None
            for ak in api_keys:
                if check_password_hash(ak.key_hash, key):
                    matched = ak
                    break

            if not matched:
                return jsonify({'error': 'Invalid API key'}), 401

            if permission not in matched.permissions.split(','):
                return jsonify({'error': f'Missing permission: {permission}'}), 403

            g.api_user_id = matched.user_id
            g.api_key_id = matched.id
            matched.last_used = datetime.utcnow()
            db.session.commit()

            return f(*args, **kwargs)
        return decorated
    return decorator


def paginate_query(query):
    """Apply pagination to a SQLAlchemy query and return (items, meta)."""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    return items, {
        'page': page,
        'per_page': per_page,
        'total': total,
        'pages': (total + per_page - 1) // per_page
    }


# Import and register route modules
from . import transactions
from . import wallets
from . import categories
from . import budgets
from . import goals
from . import summary
