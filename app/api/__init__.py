from flask import Blueprint, jsonify, request, g, current_app
from functools import wraps
from werkzeug.security import check_password_hash
from datetime import datetime
import time
import threading

api_bp = Blueprint('api', __name__, url_prefix='/api/v1')

# Rate limiting configuration
RATE_LIMIT = 100  # requests per window
RATE_WINDOW = 60  # seconds (1 minute)
rate_limit_store = {}  # {api_key_id: {'tokens': int, 'last_update': float}}
rate_lock = threading.Lock()


class TokenBucket:
    """Token bucket rate limiter for each API key."""
    
    def __init__(self, capacity, refill_rate):
        self.capacity = capacity
        self.refill_rate = refill_rate  # tokens per second
        self.tokens = capacity
        self.last_update = time.time()
    
    def consume(self, tokens=1):
        """Try to consume tokens. Returns True if successful, False if rate limited."""
        now = time.time()
        elapsed = now - self.last_update
        
        # Refill tokens based on elapsed time
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_update = now
        
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False
    
    def get_remaining(self):
        """Get remaining tokens."""
        now = time.time()
        elapsed = now - self.last_update
        tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        return int(tokens)
    
    def get_reset_time(self):
        """Get seconds until bucket is fully refilled."""
        tokens_needed = self.capacity - self.tokens
        return int(tokens_needed / self.refill_rate) if self.refill_rate > 0 else 0


def get_rate_limiter(api_key_id):
    """Get or create rate limiter for an API key."""
    with rate_lock:
        if api_key_id not in rate_limit_store:
            # refill_rate = capacity / window (tokens per second)
            refill_rate = RATE_LIMIT / RATE_WINDOW
            rate_limit_store[api_key_id] = TokenBucket(RATE_LIMIT, refill_rate)
        return rate_limit_store[api_key_id]


def check_rate_limit(api_key_id):
    """Check if request is within rate limit. Returns (allowed, remaining, reset_time)."""
    limiter = get_rate_limiter(api_key_id)
    allowed = limiter.consume()
    remaining = limiter.get_remaining()
    reset_time = limiter.get_reset_time()
    return allowed, remaining, reset_time


@api_bp.before_request
def check_api_rate_limit():
    """Check rate limit before processing API request."""
    # Skip rate limiting for non-API routes
    if not request.path.startswith('/api/v1/'):
        return None
    
    # Skip for OPTIONS (CORS preflight)
    if request.method == 'OPTIONS':
        return None
    
    # Get API key from request
    key = request.headers.get('X-API-Key') or request.args.get('api_key')
    if not key:
        # Let require_api_key handle missing key
        return None
    
    # Validate key and get api_key_id
    from ..models import ApiKey
    api_keys = ApiKey.query.filter_by(is_active=True).all()
    matched = None
    for ak in api_keys:
        if check_password_hash(ak.key_hash, key):
            matched = ak
            break
    
    if not matched:
        return None
    
    # Check rate limit
    allowed, remaining, reset_time = check_rate_limit(matched.id)
    
    # Store for after_request
    g.rate_limit_allowed = allowed
    g.rate_limit_remaining = remaining
    g.rate_limit_reset = reset_time
    
    if not allowed:
        response = jsonify({
            'error': 'Rate limit exceeded',
            'message': f'Maximum {RATE_LIMIT} requests per minute allowed',
            'retry_after': reset_time
        })
        response.status_code = 429
        response.headers['Retry-After'] = str(reset_time)
        response.headers['X-RateLimit-Limit'] = str(RATE_LIMIT)
        response.headers['X-RateLimit-Remaining'] = '0'
        response.headers['X-RateLimit-Reset'] = str(reset_time)
        return response
    
    return None


@api_bp.after_request
def add_rate_limit_headers(response):
    """Add rate limit headers to response."""
    if hasattr(g, 'rate_limit_allowed') and hasattr(g, 'rate_limit_remaining'):
        response.headers['X-RateLimit-Limit'] = str(RATE_LIMIT)
        response.headers['X-RateLimit-Remaining'] = str(g.rate_limit_remaining)
        if hasattr(g, 'rate_limit_reset'):
            response.headers['X-RateLimit-Reset'] = str(g.rate_limit_reset)
    return response


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
from . import auth
from . import creditors
from . import debtors
from . import commitments
from . import investments
from . import insurance
from . import pensions
from . import fixed_assets
