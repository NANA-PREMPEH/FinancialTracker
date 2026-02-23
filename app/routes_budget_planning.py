from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from . import db
from .models import BudgetPeriod, Budget, Expense, Category
from datetime import datetime
from sqlalchemy import func

budget_planning_bp = Blueprint('budget_planning', __name__)


@budget_planning_bp.route('/budget-planning')
@login_required
def budget_planning():
    periods = BudgetPeriod.query.filter_by(user_id=current_user.id).order_by(BudgetPeriod.start_date.desc()).all()
    budgets = Budget.query.filter_by(user_id=current_user.id, is_active=True).all()

    # Calculate Arkad 10% rule
    month_start = datetime(datetime.utcnow().year, datetime.utcnow().month, 1)
    monthly_income = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == current_user.id, Expense.transaction_type == 'income',
        Expense.date >= month_start
    ).scalar() or 0
    monthly_expenses = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == current_user.id, Expense.transaction_type == 'expense',
        Expense.date >= month_start
    ).scalar() or 0

    arkad_target = monthly_income * 0.10
    savings = monthly_income - monthly_expenses
    savings_rate = (savings / monthly_income * 100) if monthly_income > 0 else 0
    arkad_met = savings >= arkad_target

    for b in budgets:
        b.spent = db.session.query(func.sum(Expense.amount)).filter(
            Expense.user_id == current_user.id,
            Expense.category_id == b.category_id,
            Expense.transaction_type == 'expense',
            Expense.date >= month_start
        ).scalar() or 0
        # alias amount to limit for template
        b.limit = b.amount

    return render_template('budget_planning.html', periods=periods, budgets=budgets,
                           monthly_income=monthly_income, monthly_expenses=monthly_expenses,
                           arkad_target=arkad_target, savings=savings,
                           savings_rate=savings_rate, arkad_met=arkad_met)


@budget_planning_bp.route('/budget-planning/periods/add', methods=['POST'])
@login_required
def add_period():
    period = BudgetPeriod(
        user_id=current_user.id,
        name=request.form.get('name', '').strip(),
        start_date=datetime.strptime(request.form['start_date'], '%Y-%m-%d'),
        end_date=datetime.strptime(request.form['end_date'], '%Y-%m-%d'),
        total_budget=float(request.form.get('total_budget', 0)),
        notes=request.form.get('notes', '').strip() or None,
    )
    db.session.add(period)
    db.session.commit()
    flash('Budget period created.', 'success')
    return redirect(url_for('budget_planning.budget_planning'))


@budget_planning_bp.route('/budget-planning/periods/delete/<int:id>', methods=['POST'])
@login_required
def delete_period(id):
    period = BudgetPeriod.query.get_or_404(id)
    db.session.delete(period)
    db.session.commit()
    flash('Budget period deleted.', 'success')
    return redirect(url_for('budget_planning.budget_planning'))
