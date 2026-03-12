from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_

from . import db
from .models import Expense, User, Wallet, WalletShare

shared_wallets_bp = Blueprint('shared_wallets', __name__)


@shared_wallets_bp.route('/wallets/shared')
@login_required
def shared_wallets():
    """List all wallets shared with the current user and wallets they've shared."""
    # Wallets shared with me (accepted)
    received = WalletShare.query.filter_by(
        shared_with_id=current_user.id, accepted=True
    ).all()

    # Wallets I've shared with others
    sent = WalletShare.query.filter_by(owner_id=current_user.id).all()

    # Pending invites for me
    pending = WalletShare.query.filter_by(
        shared_with_id=current_user.id, accepted=False
    ).all()

    # Activity feed — recent transactions on wallets shared with me
    shared_wallet_ids = [s.wallet_id for s in received]
    activity = []
    if shared_wallet_ids:
        activity = Expense.query.filter(
            Expense.wallet_id.in_(shared_wallet_ids)
        ).order_by(Expense.date.desc()).limit(30).all()

    return render_template('shared_wallets.html',
        received=received, sent=sent, pending=pending, activity=activity)


@shared_wallets_bp.route('/wallets/<int:id>/share', methods=['POST'])
@login_required
def share_wallet(id):
    """Invite a user to share a wallet by email."""
    wallet = Wallet.query.get_or_404(id)
    if wallet.user_id != current_user.id:
        flash('You can only share wallets you own.', 'error')
        return redirect(url_for('main.wallets'))

    email = request.form.get('email', '').strip().lower()
    permission = request.form.get('permission', 'view')
    if permission not in ('view', 'contribute', 'manage'):
        permission = 'view'

    if not email:
        flash('Please enter an email address.', 'error')
        return redirect(url_for('main.wallets'))

    if email == current_user.email:
        flash('You cannot share a wallet with yourself.', 'error')
        return redirect(url_for('main.wallets'))

    # Find the target user
    target_user = User.query.filter_by(email=email).first()
    if not target_user:
        flash(f'No user found with email "{email}". They must have an account first.', 'error')
        return redirect(url_for('main.wallets'))

    # Check for existing share
    existing = WalletShare.query.filter_by(
        wallet_id=wallet.id, shared_with_id=target_user.id
    ).first()
    if existing:
        flash(f'This wallet is already shared with {target_user.name}.', 'error')
        return redirect(url_for('main.wallets'))

    share = WalletShare(
        wallet_id=wallet.id,
        owner_id=current_user.id,
        shared_with_id=target_user.id,
        permission=permission,
        accepted=False,
    )
    db.session.add(share)

    # Mark the wallet as shared
    wallet.is_shared = True
    db.session.commit()

    flash(f'Invite sent to {target_user.name} ({email}) with {permission} access.', 'success')
    return redirect(url_for('shared_wallets.shared_wallets'))


@shared_wallets_bp.route('/wallets/invites/<int:id>/accept', methods=['POST'])
@login_required
def accept_invite(id):
    """Accept a wallet share invite."""
    share = WalletShare.query.get_or_404(id)
    if share.shared_with_id != current_user.id:
        flash('Unauthorized.', 'error')
        return redirect(url_for('shared_wallets.shared_wallets'))

    share.accepted = True
    db.session.commit()
    flash(f'You now have {share.permission} access to "{share.wallet.name}".', 'success')
    return redirect(url_for('shared_wallets.shared_wallets'))


@shared_wallets_bp.route('/wallets/invites/<int:id>/decline', methods=['POST'])
@login_required
def decline_invite(id):
    """Decline a wallet share invite."""
    share = WalletShare.query.get_or_404(id)
    if share.shared_with_id != current_user.id:
        flash('Unauthorized.', 'error')
        return redirect(url_for('shared_wallets.shared_wallets'))

    db.session.delete(share)
    db.session.commit()
    flash('Invite declined.', 'success')
    return redirect(url_for('shared_wallets.shared_wallets'))


@shared_wallets_bp.route('/wallets/shares/<int:id>/revoke', methods=['POST'])
@login_required
def revoke_share(id):
    """Owner revokes a share or shared user leaves."""
    share = WalletShare.query.get_or_404(id)
    if share.owner_id != current_user.id and share.shared_with_id != current_user.id:
        flash('Unauthorized.', 'error')
        return redirect(url_for('shared_wallets.shared_wallets'))

    wallet = share.wallet
    db.session.delete(share)
    db.session.commit()

    # If no more shares, unmark wallet
    remaining = WalletShare.query.filter_by(wallet_id=wallet.id).count()
    if remaining == 0:
        wallet.is_shared = False
        db.session.commit()

    flash('Wallet share revoked.', 'success')
    return redirect(url_for('shared_wallets.shared_wallets'))


@shared_wallets_bp.route('/wallets/shares/<int:id>/update', methods=['POST'])
@login_required
def update_permission(id):
    """Owner updates a share's permission level."""
    share = WalletShare.query.get_or_404(id)
    if share.owner_id != current_user.id:
        flash('Only the wallet owner can change permissions.', 'error')
        return redirect(url_for('shared_wallets.shared_wallets'))

    permission = request.form.get('permission', 'view')
    if permission not in ('view', 'contribute', 'manage'):
        permission = 'view'

    share.permission = permission
    db.session.commit()
    flash(f'Permission updated to {permission}.', 'success')
    return redirect(url_for('shared_wallets.shared_wallets'))
