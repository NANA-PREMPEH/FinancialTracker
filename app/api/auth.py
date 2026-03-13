"""
Authentication API endpoints for the REST API.

Provides JWT-based authentication alongside the existing API key authentication.
"""

from flask import Blueprint, jsonify, request, g, current_app
from functools import wraps
from datetime import datetime, timedelta
import jwt
import re

auth_bp = Blueprint('api_auth', __name__, url_prefix='/auth')


def generate_jwt_token(user_id, email, expires_in=3600):
    """Generate a JWT token for the user."""
    payload = {
        'user_id': user_id,
        'email': email,
        'exp': datetime.utcnow() + timedelta(seconds=expires_in),
        'iat': datetime.utcnow()
    }
    secret = current_app.config.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    token = jwt.encode(payload, secret, algorithm='HS256')
    return token


def decode_jwt_token(token):
    """Decode and validate a JWT token."""
    secret = current_app.config.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    try:
        payload = jwt.decode(token, secret, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def require_jwt_auth(f):
    """Decorator to require JWT authentication."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Authorization header with Bearer token required'}), 401
        
        token = auth_header[7:]  # Remove 'Bearer ' prefix
        payload = decode_jwt_token(token)
        
        if not payload:
            return jsonify({'error': 'Invalid or expired token'}), 401
        
        g.jwt_user_id = payload.get('user_id')
        g.jwt_email = payload.get('email')
        
        return f(*args, **kwargs)
    return decorated


def require_api_or_jwt_auth(f):
    """Decorator that accepts either API key or JWT authentication."""
    @wraps(f)
    def decorated(*args, **kwargs):
        # Check for JWT first
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]
            payload = decode_jwt_token(token)
            if payload:
                g.api_user_id = payload.get('user_id')
                g.auth_type = 'jwt'
                return f(*args, **kwargs)
        
        # Check for API key
        from ..models import ApiKey
        from .. import db
        from werkzeug.security import check_password_hash
        
        key = request.headers.get('X-API-Key') or request.args.get('api_key')
        if key:
            api_keys = ApiKey.query.filter_by(is_active=True).all()
            matched = None
            for ak in api_keys:
                if check_password_hash(ak.key_hash, key):
                    matched = ak
                    break
            
            if matched:
                g.api_user_id = matched.user_id
                g.auth_type = 'api_key'
                return f(*args, **kwargs)
        
        return jsonify({'error': 'Authentication required. Use Bearer token or X-API-Key header.'}), 401
    
    return decorated


@auth_bp.route('/register', methods=['POST'])
def register():
    """Register a new user via API."""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'JSON body required'}), 400
    
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    name = data.get('name', '').strip()
    
    if not email or not password or not name:
        return jsonify({'error': 'Email, password, and name are required'}), 400
    
    # Validate email format
    if not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
        return jsonify({'error': 'Invalid email format'}), 400
    
    # Check password length
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400
    
    # Check if user exists
    from ..models import User
    from .. import db
    
    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email already registered'}), 409
    
    # Create user
    user = User(
        email=email,
        name=name,
        default_currency=data.get('currency', 'GHS')
    )
    user.set_password(password)
    
    db.session.add(user)
    db.session.commit()
    
    # Generate token
    token = generate_jwt_token(user.id, user.email)
    
    return jsonify({
        'message': 'User registered successfully',
        'user': {
            'id': user.id,
            'email': user.email,
            'name': user.name,
            'default_currency': user.default_currency
        },
        'access_token': token,
        'token_type': 'Bearer',
        'expires_in': 3600
    }), 201


@auth_bp.route('/login', methods=['POST'])
def login():
    """Login via API and get JWT token."""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'JSON body required'}), 400
    
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    
    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400
    
    from ..models import User
    
    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({'error': 'Invalid email or password'}), 401
    
    # Generate token
    token = generate_jwt_token(user.id, user.email)
    
    return jsonify({
        'message': 'Login successful',
        'user': {
            'id': user.id,
            'email': user.email,
            'name': user.name,
            'default_currency': user.default_currency
        },
        'access_token': token,
        'token_type': 'Bearer',
        'expires_in': 3600
    })


@auth_bp.route('/refresh', methods=['POST'])
@require_jwt_auth
def refresh():
    """Refresh an existing JWT token."""
    from ..models import User
    
    user = User.query.get(g.jwt_user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # Generate new token
    token = generate_jwt_token(user.id, user.email)
    
    return jsonify({
        'access_token': token,
        'token_type': 'Bearer',
        'expires_in': 3600
    })


@auth_bp.route('/me', methods=['GET'])
@require_jwt_auth
def get_current_user():
    """Get current authenticated user profile."""
    from ..models import User
    
    user = User.query.get(g.jwt_user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    return jsonify({
        'id': user.id,
        'email': user.email,
        'name': user.name,
        'default_currency': user.default_currency,
        'theme_preference': user.theme_preference,
        'created_at': user.created_at.isoformat() if user.created_at else None,
        'email_verified': user.email_verified,
        'totp_enabled': user.totp_enabled
    })
