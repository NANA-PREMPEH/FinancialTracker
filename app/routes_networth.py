from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from . import db
from .models import NetWorthSnapshot, Wallet, Investment, FixedAsset, Creditor
from datetime import datetime
import json

networth_bp = Blueprint('networth', __name__, url_prefix='/net-worth')


@networth_bp.route('', methods=['GET'])
@login_required
def net_worth_dashboard():
    """
    Dashboard showing current net worth calculated from:
    - total_assets = sum of wallet balances + sum of investment current_values + sum of fixed asset current_values
    - total_liabilities = sum of creditor amounts
    - net_worth = total_assets - total_liabilities
    Also lists all NetWorthSnapshot records ordered by date desc.
    Compute assets_breakdown as a dict of categories and values.
    """
    # Calculate wallet assets
    wallets = Wallet.query.filter_by(user_id=current_user.id).all()
    wallet_total = sum(wallet.balance for wallet in wallets)

    # Calculate investment assets
    investments = Investment.query.filter_by(user_id=current_user.id).all()
    investment_total = sum(inv.current_value for inv in investments)

    # Calculate fixed asset assets
    fixed_assets = FixedAsset.query.filter_by(user_id=current_user.id).all()
    fixed_asset_total = sum(asset.current_value for asset in fixed_assets)

    # Calculate total assets
    total_assets = wallet_total + investment_total + fixed_asset_total

    # Calculate total liabilities (creditors)
    creditors = Creditor.query.filter_by(user_id=current_user.id).all()
    total_liabilities = sum(creditor.amount for creditor in creditors)

    # Calculate net worth
    net_worth = total_assets - total_liabilities

    # Build assets breakdown
    assets_breakdown = [
        {'category': 'Wallets', 'amount': wallet_total},
        {'category': 'Investments', 'amount': investment_total},
        {'category': 'Fixed Assets', 'amount': fixed_asset_total}
    ]

    # Get all snapshots for this user ordered by date descending
    snapshots = NetWorthSnapshot.query.filter_by(user_id=current_user.id).order_by(
        NetWorthSnapshot.date.desc()
    ).all()

    return render_template(
        'net_worth.html',
        total_assets=total_assets,
        total_liabilities=total_liabilities,
        net_worth=net_worth,
        assets_breakdown=assets_breakdown,
        snapshots=snapshots,
        wallet_total=wallet_total,
        investment_total=investment_total,
        fixed_asset_total=fixed_asset_total,
        num_creditors=len(creditors)
    )


@networth_bp.route('/snapshot', methods=['POST'])
@login_required
def create_snapshot():
    """
    Create a snapshot (POST) that auto-calculates and saves current totals
    """
    # Calculate wallet assets
    wallets = Wallet.query.filter_by(user_id=current_user.id).all()
    wallet_total = sum(wallet.balance for wallet in wallets)

    # Calculate investment assets
    investments = Investment.query.filter_by(user_id=current_user.id).all()
    investment_total = sum(inv.current_value for inv in investments)

    # Calculate fixed asset assets
    fixed_assets = FixedAsset.query.filter_by(user_id=current_user.id).all()
    fixed_asset_total = sum(asset.current_value for asset in fixed_assets)

    # Calculate total assets
    total_assets = wallet_total + investment_total + fixed_asset_total

    # Calculate total liabilities (creditors)
    creditors = Creditor.query.filter_by(user_id=current_user.id).all()
    total_liabilities = sum(creditor.amount for creditor in creditors)

    # Calculate net worth
    net_worth = total_assets - total_liabilities

    # Build detailed breakdown
    breakdown = {
        'wallets': wallet_total,
        'investments': investment_total,
        'fixed_assets': fixed_asset_total,
        'creditors': total_liabilities,
        'snapshot_date': datetime.utcnow().isoformat()
    }

    # Create and save snapshot
    snapshot = NetWorthSnapshot(
        user_id=current_user.id,
        date=datetime.utcnow(),
        total_assets=total_assets,
        total_liabilities=total_liabilities,
        net_worth=net_worth,
        breakdown_json=json.dumps(breakdown)
    )

    db.session.add(snapshot)
    db.session.commit()

    flash('Net worth snapshot created successfully!', 'success')
    return redirect(url_for('networth.net_worth_dashboard'))


@networth_bp.route('/snapshot/delete/<int:id>', methods=['POST'])
@login_required
def delete_snapshot(id):
    """
    Delete snapshot (POST)
    """
    snapshot = NetWorthSnapshot.query.filter_by(id=id, user_id=current_user.id).first_or_404()

    db.session.delete(snapshot)
    db.session.commit()

    flash('Net worth snapshot deleted successfully!', 'success')
    return redirect(url_for('networth.net_worth_dashboard'))
