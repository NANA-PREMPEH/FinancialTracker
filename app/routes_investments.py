from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from . import db
from .models import Investment, Dividend, InsurancePolicy, PensionScheme, SSNITContribution, GlobalEntity
from datetime import datetime, timedelta
import json
from collections import defaultdict

investments_bp = Blueprint('investments', __name__, url_prefix='/investments')


@investments_bp.route('/', methods=['GET'])
@login_required
def investments_list():
    """List all investments, businesses, partnerships, shareholding, and jobs"""
    investments = Investment.query.filter_by(user_id=current_user.id).all()
    global_entities = GlobalEntity.query.filter_by(user_id=current_user.id).all()
    
    businesses = [e for e in global_entities if e.entity_type == 'Business']
    partnerships = [e for e in global_entities if e.entity_type == 'Partnership']
    shareholding = [e for e in global_entities if e.entity_type == 'Shareholding']
    jobs = [e for e in global_entities if e.entity_type == 'Job']
    
    total_invested = sum(inv.amount_invested for inv in investments)
    total_investment_value = sum(inv.current_value for inv in investments)
    total_entity_value = sum(e.value for e in global_entities)
    
    total_portfolio_value = total_investment_value + total_entity_value
    
    investment_gain = total_investment_value - total_invested
    total_gain_loss = investment_gain 
    
    total_roi = (investment_gain / total_invested * 100) if total_invested > 0 else 0
    total_investments_count = len(investments) + len(global_entities)
    
    asset_types = set([inv.investment_type for inv in investments] + [e.entity_type for e in global_entities])
    asset_classes_count = len(asset_types)
    
    best_performer_name = "N/A"
    best_performer_roi = 0
    if investments:
        best_inv = max(investments, key=lambda i: i.roi if hasattr(i, 'roi') else ((i.current_value - i.amount_invested) / i.amount_invested) if i.amount_invested > 0 else 0)
        best_performer_name = best_inv.name
        best_performer_roi = best_inv.roi if hasattr(best_inv, 'roi') else ((best_inv.current_value - best_inv.amount_invested) / best_inv.amount_invested * 100) if best_inv.amount_invested > 0 else 0
        
    allocation_data = defaultdict(float)
    for inv in investments:
        allocation_data[inv.investment_type] += inv.current_value
    for e in global_entities:
        allocation_data[e.entity_type] += e.value
        
    allocation_labels = list(allocation_data.keys())
    allocation_series = list(allocation_data.values())
    
    # Portfolio Performance Chart Data (Mock data for 6 months representation)
    performance_labels = []
    performance_series = []
    today = datetime.today()
    for i in range(5, -1, -1):
        month_date = today.replace(day=1) - timedelta(days=30 * i)
        performance_labels.append(month_date.strftime('%b'))
        # Using mock historical variation based on today's value for demonstration
        performance_series.append(total_portfolio_value * (1 - (0.015 * i)))

    return render_template(
        'investments.html',
        investments=investments,
        businesses=businesses,
        partnerships=partnerships,
        shareholding=shareholding,
        jobs=jobs,
        total_portfolio_value=total_portfolio_value,
        total_gain_loss=total_gain_loss,
        total_roi=total_roi,
        total_investments_count=total_investments_count,
        asset_classes_count=asset_classes_count,
        best_performer_name=best_performer_name,
        best_performer_roi=best_performer_roi,
        allocation_labels=json.dumps(allocation_labels),
        allocation_series=json.dumps(allocation_series),
        performance_labels=json.dumps(performance_labels),
        performance_series=json.dumps(performance_series)
    )


@investments_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_investment():
    """Add new investment"""
    if request.method == 'POST':
        try:
            investment_type = request.form.get('investment_type')
            name = request.form.get('name')
            amount_invested = float(request.form.get('amount_invested', 0))
            current_value = float(request.form.get('current_value', 0))
            purchase_date_str = request.form.get('purchase_date')
            purchase_date = datetime.strptime(purchase_date_str, '%Y-%m-%d').date() if purchase_date_str else None
            platform = request.form.get('platform', '')
            notes = request.form.get('notes', '')

            investment = Investment(
                user_id=current_user.id,
                investment_type=investment_type,
                name=name,
                amount_invested=amount_invested,
                current_value=current_value,
                purchase_date=purchase_date,
                platform=platform,
                notes=notes
            )

            db.session.add(investment)
            db.session.commit()

            flash('Investment added successfully!', 'success')
            return redirect(url_for('investments.investments_list'))
        except Exception as e:
            flash(f'Error adding investment: {str(e)}', 'danger')
            return redirect(url_for('investments.add_investment'))

    return render_template('add_investment.html')


@investments_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_investment(id):
    """Edit investment"""
    investment = Investment.query.get_or_404(id)

    if investment.user_id != current_user.id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('investments.investments_list'))

    if request.method == 'POST':
        try:
            investment.investment_type = request.form.get('investment_type')
            investment.name = request.form.get('name')
            investment.amount_invested = float(request.form.get('amount_invested', 0))
            investment.current_value = float(request.form.get('current_value', 0))
            purchase_date_str = request.form.get('purchase_date')
            investment.purchase_date = datetime.strptime(purchase_date_str, '%Y-%m-%d').date() if purchase_date_str else None
            investment.platform = request.form.get('platform', '')
            investment.notes = request.form.get('notes', '')

            db.session.commit()

            flash('Investment updated successfully!', 'success')
            return redirect(url_for('investments.investments_list'))
        except Exception as e:
            flash(f'Error updating investment: {str(e)}', 'danger')
            return redirect(url_for('investments.edit_investment', id=id))

    return render_template('edit_investment.html', investment=investment)


@investments_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete_investment(id):
    """Delete investment"""
    investment = Investment.query.get_or_404(id)

    if investment.user_id != current_user.id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('investments.investments_list'))

    try:
        db.session.delete(investment)
        db.session.commit()
        flash('Investment deleted successfully!', 'success')
    except Exception as e:
        flash(f'Error deleting investment: {str(e)}', 'danger')

    return redirect(url_for('investments.investments_list'))


@investments_bp.route('/dividends/add/<int:id>', methods=['POST'])
@login_required
def add_dividend(id):
    """Add dividend to investment"""
    investment = Investment.query.get_or_404(id)

    if investment.user_id != current_user.id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('investments.investments_list'))

    try:
        amount = float(request.form.get('amount'))
        date_str = request.form.get('date')
        dividend_date = datetime.strptime(date_str, '%Y-%m-%d') if date_str else datetime.utcnow()
        notes = request.form.get('notes', '')

        dividend = Dividend(
            investment_id=id,
            amount=amount,
            date=dividend_date,
            notes=notes
        )

        db.session.add(dividend)
        db.session.commit()

        flash('Dividend added successfully!', 'success')
    except Exception as e:
        flash(f'Error adding dividend: {str(e)}', 'danger')

    return redirect(url_for('investments.investments_list'))


@investments_bp.route('/insurance', methods=['GET'])
@login_required
def insurance_policies():
    """List insurance policies"""
    policies = InsurancePolicy.query.filter_by(user_id=current_user.id).all()
    return render_template('insurance_policies.html', policies=policies)


@investments_bp.route('/insurance/add', methods=['POST'])
@login_required
def add_insurance_policy():
    """Add insurance policy"""
    try:
        policy_type = request.form.get('policy_type')
        provider = request.form.get('provider')
        policy_number = request.form.get('policy_number', '')
        premium = float(request.form.get('premium'))
        start_date_str = request.form.get('start_date')
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d') if start_date_str else None
        coverage = float(request.form.get('coverage', 0))
        end_date_str = request.form.get('end_date', None)
        end_date = None
        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        notes = request.form.get('notes', '')

        policy = InsurancePolicy(
            user_id=current_user.id,
            policy_type=policy_type,
            provider=provider,
            policy_number=policy_number,
            premium=premium,
            start_date=start_date,
            coverage=coverage,
            end_date=end_date,
            notes=notes
        )

        db.session.add(policy)
        db.session.commit()

        flash('Insurance policy added successfully!', 'success')
    except Exception as e:
        flash(f'Error adding insurance policy: {str(e)}', 'danger')

    return redirect(url_for('investments.insurance_policies'))


@investments_bp.route('/insurance/delete/<int:id>', methods=['POST'])
@login_required
def delete_insurance_policy(id):
    """Delete insurance policy"""
    policy = InsurancePolicy.query.get_or_404(id)

    if policy.user_id != current_user.id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('investments.insurance_policies'))

    try:
        db.session.delete(policy)
        db.session.commit()
        flash('Insurance policy deleted successfully!', 'success')
    except Exception as e:
        flash(f'Error deleting insurance policy: {str(e)}', 'danger')

    return redirect(url_for('investments.insurance_policies'))


@investments_bp.route('/pensions', methods=['GET'])
@login_required
def pensions_list():
    """List pensions"""
    pensions = PensionScheme.query.filter_by(user_id=current_user.id).all()
    return render_template('pensions.html', pensions=pensions)


@investments_bp.route('/pensions/add', methods=['POST'])
@login_required
def add_pension():
    """Add pension scheme"""
    try:
        name = request.form.get('name')
        scheme_type = request.form.get('scheme_type')
        contributions = float(request.form.get('contributions', 0))
        employer_match = float(request.form.get('employer_match', 0))
        balance = float(request.form.get('balance', 0))
        notes = request.form.get('notes', '')

        pension = PensionScheme(
            user_id=current_user.id,
            name=name,
            scheme_type=scheme_type,
            contributions=contributions,
            employer_match=employer_match,
            balance=balance,
            notes=notes
        )

        db.session.add(pension)
        db.session.commit()

        flash('Pension scheme added successfully!', 'success')
    except Exception as e:
        flash(f'Error adding pension scheme: {str(e)}', 'danger')

    return redirect(url_for('investments.pensions_list'))


@investments_bp.route('/pensions/delete/<int:id>', methods=['POST'])
@login_required
def delete_pension(id):
    """Delete pension"""
    pension = PensionScheme.query.get_or_404(id)

    if pension.user_id != current_user.id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('investments.pensions_list'))

    try:
        db.session.delete(pension)
        db.session.commit()
        flash('Pension scheme deleted successfully!', 'success')
    except Exception as e:
        flash(f'Error deleting pension scheme: {str(e)}', 'danger')

    return redirect(url_for('investments.pensions_list'))


@investments_bp.route('/ssnit', methods=['GET'])
@login_required
def ssnit_contributions():
    """List SSNIT contributions"""
    contributions = SSNITContribution.query.filter_by(user_id=current_user.id).all()
    return render_template('ssnit_contributions.html', contributions=contributions)


@investments_bp.route('/ssnit/add', methods=['POST'])
@login_required
def add_ssnit_contribution():
    """Add SSNIT contribution"""
    try:
        month = int(request.form.get('month'))
        year = int(request.form.get('year'))
        amount = float(request.form.get('amount'))
        employer = request.form.get('employer', '')
        employee_number = request.form.get('employee_number', '')

        contribution = SSNITContribution(
            user_id=current_user.id,
            month=month,
            year=year,
            amount=amount,
            employer=employer,
            employee_number=employee_number
        )

        db.session.add(contribution)
        db.session.commit()

        flash('SSNIT contribution added successfully!', 'success')
    except Exception as e:
        flash(f'Error adding SSNIT contribution: {str(e)}', 'danger')

    return redirect(url_for('investments.ssnit_contributions'))
