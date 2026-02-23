from flask import jsonify, request, g
from . import api_bp, require_api_key, paginate_query
from ..models import Wallet
from .. import db


def serialize_wallet(w):
    return {
        'id': w.id,
        'name': w.name,
        'balance': w.balance,
        'currency': w.currency,
        'icon': w.icon,
        'wallet_type': w.wallet_type,
        'account_number': w.account_number,
        'is_shared': w.is_shared,
    }


@api_bp.route('/wallets', methods=['GET'])
@require_api_key('read')
def list_wallets():
    wallets = Wallet.query.filter_by(user_id=g.api_user_id).all()
    return jsonify({'data': [serialize_wallet(w) for w in wallets]})


@api_bp.route('/wallets/<int:id>', methods=['GET'])
@require_api_key('read')
def get_wallet(id):
    w = Wallet.query.filter_by(id=id, user_id=g.api_user_id).first()
    if not w:
        return jsonify({'error': 'Wallet not found'}), 404
    return jsonify({'data': serialize_wallet(w)})
