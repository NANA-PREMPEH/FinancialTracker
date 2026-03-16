from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from . import db
from .models import CashFlowProjection, CashFlowAlert, Expense, ProjectItem, ProjectItemPayment, DebtPayment, DebtorPayment, ContractPayment, Category, FinancialSummary
from datetime import datetime, timedelta
from sqlalchemy import func, or_
import calendar as cal_module

cashflow_bp = Blueprint('cashflow', __name__)


@cashflow_bp.route('/cash-flow')
@login_required
def cash_flow():
    now = datetime.utcnow()
    projections = CashFlowProjection.query.filter_by(user_id=current_user.id).order_by(
        CashFlowProjection.year.desc(), CashFlowProjection.month.desc()).all()
    alerts = CashFlowAlert.query.filter_by(user_id=current_user.id).order_by(CashFlowAlert.created_at.desc()).all()

    # Build monthly data for last 6 months
    monthly_data = []
    months_list = []
    curr_y, curr_m = now.year, now.month
    for _ in range(6):
        months_list.append((curr_y, curr_m))
        curr_m -= 1
        if curr_m == 0:
            curr_m = 12
            curr_y -= 1
    months_list.reverse()

    # Exclude Transfer category
    transfer_cat = Category.query.filter_by(name='Transfer', user_id=current_user.id).first()
    transfer_id = transfer_cat.id if transfer_cat else -1
    transfer_types = ('transfer', 'transfer_out', 'transfer_in')
    
    # Robust Transfer Filter (Handles NULLs)
    transfer_filter = or_(
        Expense.transaction_type.in_(transfer_types),
        func.coalesce(Expense.tags, '').ilike('%transfer%'),
        func.coalesce(Expense.description, '').ilike('Transfer %')
    )
    if transfer_id != -1:
        transfer_filter = or_(transfer_filter, Expense.category_id == transfer_id)

    for y, m in months_list:
        month_start = datetime(y, m, 1)
        if m == 12:
            month_end = datetime(y + 1, 1, 1)
        else:
            month_end = datetime(y, m + 1, 1)

        # Check for historical summary
        hist_summary = FinancialSummary.query.filter_by(
            user_id=current_user.id, year=y, month=m).first()

        if hist_summary:
            actual_income = hist_summary.total_income
            actual_expenses = hist_summary.total_expense
        else:
            actual_income = db.session.query(func.sum(Expense.amount)).filter(
                Expense.user_id == current_user.id,
                Expense.transaction_type == 'income',
                Expense.date >= month_start,
                Expense.date < month_end,
                ~transfer_filter
            ).scalar() or 0

            actual_expenses = db.session.query(func.sum(Expense.amount)).filter(
                Expense.user_id == current_user.id,
                Expense.transaction_type == 'expense',
                Expense.date >= month_start,
                Expense.date < month_end,
                ~transfer_filter
            ).scalar() or 0

            # Extra payments for this month (Cash Flow)
            m_extra_debt_exp = db.session.query(func.sum(DebtPayment.amount)).filter(
                DebtPayment.user_id == current_user.id,
                DebtPayment.date >= month_start,
                DebtPayment.date < month_end
            ).scalar() or 0

            m_extra_debtor_inc = db.session.query(func.sum(DebtorPayment.amount)).filter(
                DebtorPayment.user_id == current_user.id,
                DebtorPayment.date >= month_start,
                DebtorPayment.date < month_end
            ).scalar() or 0

            m_extra_contract_inc = db.session.query(func.sum(ContractPayment.amount)).filter(
                ContractPayment.user_id == current_user.id,
                ContractPayment.payment_date >= month_start,
                ContractPayment.payment_date < month_end
            ).scalar() or 0

            actual_expenses += m_extra_debt_exp


        # Find matching projection
        proj = CashFlowProjection.query.filter_by(
            user_id=current_user.id, year=y, month=m).first()

        monthly_data.append({
            'month': m, 'year': y,
            'month_name': cal_module.month_abbr[m],
            'actual_income': actual_income,
            'actual_expenses': actual_expenses,
            'projected_income': proj.projected_income if proj else 0,
            'projected_expenses': proj.projected_expenses if proj else 0,
            'net_flow': actual_income - actual_expenses,
        })

    return render_template('cash_flow.html', monthly_data=monthly_data,
                           projections=projections, alerts=alerts)


@cashflow_bp.route('/cash-flow/projections/add', methods=['POST'])
@login_required
def add_projection():
    month = int(request.form.get('month', datetime.utcnow().month))
    year = int(request.form.get('year', datetime.utcnow().year))

    existing = CashFlowProjection.query.filter_by(
        user_id=current_user.id, month=month, year=year).first()
    if existing:
        existing.projected_income = float(request.form.get('projected_income', 0))
        existing.projected_expenses = float(request.form.get('projected_expenses', 0))
        existing.notes = request.form.get('notes', '').strip() or None
    else:
        proj = CashFlowProjection(
            user_id=current_user.id,
            month=month, year=year,
            projected_income=float(request.form.get('projected_income', 0)),
            projected_expenses=float(request.form.get('projected_expenses', 0)),
            notes=request.form.get('notes', '').strip() or None,
        )
        db.session.add(proj)

    db.session.commit()
    flash('Projection saved.', 'success')
    return redirect(url_for('cashflow.cash_flow'))


@cashflow_bp.route('/cash-flow/projections/delete/<int:id>', methods=['POST'])
@login_required
def delete_projection(id):
    proj = CashFlowProjection.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    db.session.delete(proj)
    db.session.commit()
    flash('Projection deleted.', 'success')
    return redirect(url_for('cashflow.cash_flow'))


@cashflow_bp.route('/cash-flow/alerts/add', methods=['POST'])
@login_required
def add_alert():
    alert = CashFlowAlert(
        user_id=current_user.id,
        alert_type=request.form.get('alert_type', 'negative_cashflow'),
        threshold=float(request.form.get('threshold', 0)) or None,
        message=request.form.get('message', '').strip() or None,
    )
    db.session.add(alert)
    db.session.commit()
    flash('Alert created.', 'success')
    return redirect(url_for('cashflow.cash_flow'))


@cashflow_bp.route('/cash-flow/alerts/delete/<int:id>', methods=['POST'])
@login_required
def delete_alert(id):
    alert = CashFlowAlert.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    db.session.delete(alert)
    db.session.commit()
    flash('Alert deleted.', 'success')
    return redirect(url_for('cashflow.cash_flow'))


@cashflow_bp.route('/cash-flow/alerts/toggle/<int:id>', methods=['POST'])
@login_required
def toggle_alert(id):
    alert = CashFlowAlert.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    alert.is_active = not alert.is_active
    db.session.commit()
    flash(f'Alert {"activated" if alert.is_active else "deactivated"}.', 'success')
    return redirect(url_for('cashflow.cash_flow'))
