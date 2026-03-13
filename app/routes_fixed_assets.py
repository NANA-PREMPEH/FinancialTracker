from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from . import db
from .models import FixedAsset
from datetime import datetime

fixed_assets_bp = Blueprint('fixed_assets', __name__)

ASSET_CATEGORIES = ['Land', 'Buildings', 'Vehicles', 'Equipment']
CONDITIONS = ['Excellent', 'Good', 'Fair', 'Poor']


@fixed_assets_bp.route('/fixed-assets')
@login_required
def fixed_assets_list():
    assets = FixedAsset.query.filter_by(user_id=current_user.id).order_by(FixedAsset.created_at.desc()).all()
    total_value = sum(a.current_value for a in assets)
    total_purchase = sum(a.purchase_price for a in assets)
    return render_template('fixed_assets.html', assets=assets, total_value=total_value,
                           total_purchase=total_purchase, categories=ASSET_CATEGORIES, conditions=CONDITIONS)


@fixed_assets_bp.route('/fixed-assets/add', methods=['POST'])
@login_required
def add_asset():
    asset = FixedAsset(
        user_id=current_user.id,
        name=request.form.get('name', '').strip(),
        asset_category=request.form.get('asset_category', 'Equipment'),
        purchase_price=float(request.form.get('purchase_price', 0)),
        current_value=float(request.form.get('current_value', 0)),
        location=request.form.get('location', '').strip() or None,
        condition=request.form.get('condition', 'Good'),
        depreciation_rate=float(request.form.get('depreciation_rate', 0)),
        notes=request.form.get('notes', '').strip() or None,
    )
    pd = request.form.get('purchase_date')
    if pd:
        asset.purchase_date = datetime.strptime(pd, '%Y-%m-%d')
    db.session.add(asset)
    db.session.commit()
    flash('Asset registered.', 'success')
    return redirect(url_for('fixed_assets.fixed_assets_list'))


@fixed_assets_bp.route('/fixed-assets/edit/<int:id>', methods=['POST'])
@login_required
def edit_asset(id):
    asset = FixedAsset.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    asset.name = request.form.get('name', asset.name).strip()
    asset.asset_category = request.form.get('asset_category', asset.asset_category)
    asset.purchase_price = float(request.form.get('purchase_price', asset.purchase_price))
    asset.current_value = float(request.form.get('current_value', asset.current_value))
    asset.location = request.form.get('location', '').strip() or None
    asset.condition = request.form.get('condition', asset.condition)
    asset.depreciation_rate = float(request.form.get('depreciation_rate', asset.depreciation_rate))
    asset.notes = request.form.get('notes', '').strip() or None
    pd = request.form.get('purchase_date')
    asset.purchase_date = datetime.strptime(pd, '%Y-%m-%d') if pd else asset.purchase_date
    db.session.commit()
    flash('Asset updated.', 'success')
    return redirect(url_for('fixed_assets.fixed_assets_list'))


@fixed_assets_bp.route('/fixed-assets/delete/<int:id>', methods=['POST'])
@login_required
def delete_asset(id):
    asset = FixedAsset.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    db.session.delete(asset)
    db.session.commit()
    flash('Asset deleted.', 'success')
    return redirect(url_for('fixed_assets.fixed_assets_list'))
