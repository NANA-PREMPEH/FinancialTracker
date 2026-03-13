from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from . import db
from .models import SMCContract, ContractPayment, ConstructionWork, GlobalEntity
from datetime import datetime

domain_bp = Blueprint('domain', __name__)

# ===== SMC Contracts =====
@domain_bp.route('/smc')
@login_required
def smc_list():
    contracts = SMCContract.query.filter_by(user_id=current_user.id).order_by(SMCContract.created_at.desc()).all()
    total_value = sum(c.contract_value for c in contracts)
    return render_template('smc.html', contracts=contracts, total_value=total_value)


@domain_bp.route('/smc/add', methods=['POST'])
@login_required
def add_contract():
    contract = SMCContract(
        user_id=current_user.id,
        contract_number=request.form.get('contract_number', '').strip(),
        title=request.form.get('title', '').strip(),
        description=request.form.get('description', '').strip() or None,
        contract_value=float(request.form.get('contract_value', 0)),
        status=request.form.get('status', 'active'),
        location=request.form.get('location', '').strip() or None,
        notes=request.form.get('notes', '').strip() or None,
    )
    sd = request.form.get('start_date')
    ed = request.form.get('end_date')
    if sd:
        contract.start_date = datetime.strptime(sd, '%Y-%m-%d')
    if ed:
        contract.end_date = datetime.strptime(ed, '%Y-%m-%d')
    db.session.add(contract)
    db.session.commit()
    flash('Contract added.', 'success')
    return redirect(url_for('domain.smc_list'))


@domain_bp.route('/smc/delete/<int:id>', methods=['POST'])
@login_required
def delete_contract(id):
    c = SMCContract.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    ContractPayment.query.filter_by(contract_id=c.id).delete()
    db.session.delete(c)
    db.session.commit()
    flash('Contract deleted.', 'success')
    return redirect(url_for('domain.smc_list'))


@domain_bp.route('/smc/<int:id>/payments/add', methods=['POST'])
@login_required
def add_contract_payment(id):
    contract = SMCContract.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    payment = ContractPayment(
        user_id=current_user.id,
        contract_id=id,
        amount=float(request.form.get('amount', 0)),
        description=request.form.get('description', '').strip() or None,
        payment_date=datetime.strptime(request.form['payment_date'], '%Y-%m-%d'),
        status=request.form.get('status', 'pending'),
    )
    db.session.add(payment)
    db.session.commit()
    flash('Payment recorded.', 'success')
    return redirect(url_for('domain.smc_list'))


# ===== Construction Works =====
@domain_bp.route('/construction-works')
@login_required
def construction_list():
    works = ConstructionWork.query.filter_by(user_id=current_user.id).order_by(ConstructionWork.created_at.desc()).all()
    total_budget = sum(w.budget for w in works)
    total_spent = sum(w.spent for w in works)
    return render_template('construction.html', works=works, total_budget=total_budget, total_spent=total_spent)


@domain_bp.route('/construction-works/add', methods=['POST'])
@login_required
def add_construction():
    work = ConstructionWork(
        user_id=current_user.id,
        project_name=request.form.get('project_name', '').strip(),
        description=request.form.get('description', '').strip() or None,
        location=request.form.get('location', '').strip() or None,
        budget=float(request.form.get('budget', 0)),
        spent=float(request.form.get('spent', 0)),
        status=request.form.get('status', 'planning'),
        contractor=request.form.get('contractor', '').strip() or None,
        notes=request.form.get('notes', '').strip() or None,
    )
    sd = request.form.get('start_date')
    ed = request.form.get('end_date')
    if sd:
        work.start_date = datetime.strptime(sd, '%Y-%m-%d')
    if ed:
        work.end_date = datetime.strptime(ed, '%Y-%m-%d')
    db.session.add(work)
    db.session.commit()
    flash('Construction work added.', 'success')
    return redirect(url_for('domain.construction_list'))


@domain_bp.route('/construction-works/edit/<int:id>', methods=['POST'])
@login_required
def edit_construction(id):
    work = ConstructionWork.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    work.project_name = request.form.get('project_name', work.project_name).strip()
    work.description = request.form.get('description', '').strip() or None
    work.location = request.form.get('location', '').strip() or None
    work.budget = float(request.form.get('budget', work.budget))
    work.spent = float(request.form.get('spent', work.spent))
    work.status = request.form.get('status', work.status)
    work.contractor = request.form.get('contractor', '').strip() or None
    work.notes = request.form.get('notes', '').strip() or None
    db.session.commit()
    flash('Construction work updated.', 'success')
    return redirect(url_for('domain.construction_list'))


@domain_bp.route('/construction-works/delete/<int:id>', methods=['POST'])
@login_required
def delete_construction(id):
    work = ConstructionWork.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    db.session.delete(work)
    db.session.commit()
    flash('Construction work deleted.', 'success')
    return redirect(url_for('domain.construction_list'))


# ===== Global Finance =====
@domain_bp.route('/global-finance')
@login_required
def global_finance():
    entities = GlobalEntity.query.filter_by(user_id=current_user.id).order_by(GlobalEntity.created_at.desc()).all()
    total_value = sum(e.value for e in entities)
    return render_template('global_finance.html', entities=entities, total_value=total_value)


@domain_bp.route('/global-finance/add', methods=['POST'])
@login_required
def add_entity():
    entity = GlobalEntity(
        user_id=current_user.id,
        name=request.form.get('name', '').strip(),
        entity_type=request.form.get('entity_type', 'Business'),
        ownership_percent=float(request.form.get('ownership_percent', 100)),
        value=float(request.form.get('value', 0)),
        description=request.form.get('description', '').strip() or None,
        notes=request.form.get('notes', '').strip() or None,
    )
    db.session.add(entity)
    db.session.commit()
    flash('Entity added.', 'success')
    return redirect(url_for('domain.global_finance'))


@domain_bp.route('/global-finance/edit/<int:id>', methods=['POST'])
@login_required
def edit_entity(id):
    entity = GlobalEntity.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    entity.name = request.form.get('name', entity.name).strip()
    entity.entity_type = request.form.get('entity_type', entity.entity_type)
    entity.ownership_percent = float(request.form.get('ownership_percent', entity.ownership_percent))
    entity.value = float(request.form.get('value', entity.value))
    entity.description = request.form.get('description', '').strip() or None
    entity.notes = request.form.get('notes', '').strip() or None
    db.session.commit()
    flash('Entity updated.', 'success')
    return redirect(url_for('domain.global_finance'))


@domain_bp.route('/global-finance/delete/<int:id>', methods=['POST'])
@login_required
def delete_entity(id):
    entity = GlobalEntity.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    db.session.delete(entity)
    db.session.commit()
    flash('Entity deleted.', 'success')
    return redirect(url_for('domain.global_finance'))
