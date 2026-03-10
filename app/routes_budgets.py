from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from . import db
from .models import Expense, Category, Budget
from datetime import datetime, timedelta
from sqlalchemy import func


def register_routes(main):

    @main.route('/budgets')
    @main.route('/budget')
    @login_required
    def budgets():
        all_budgets = Budget.query.filter_by(is_active=True).all()
        budget_data = []

        for budget in all_budgets:
            # Calculate effective start date based on period
            now = datetime.utcnow()
            if budget.period == 'weekly':
                effective_start = now - timedelta(days=now.weekday())
            elif budget.period == 'monthly':
                effective_start = datetime(now.year, now.month, 1)
            elif budget.period == 'yearly':
                effective_start = datetime(now.year, 1, 1)
            else:
                effective_start = budget.start_date

            spent = db.session.query(func.sum(Expense.amount)).filter(
                Expense.category_id == budget.category_id,
                Expense.transaction_type == 'expense',
                Expense.date >= effective_start
            ).scalar() or 0

            percentage = (spent / budget.amount * 100) if budget.amount > 0 else 0
            budget_data.append({
                'budget': budget,
                'spent': spent,
                'remaining': budget.amount - spent,
                'percentage': percentage,
                'width_percentage': min(percentage, 100)
            })

        return render_template('budgets.html', budgets=budget_data)

    @main.route('/budgets/add', methods=['GET', 'POST'])
    @login_required
    def add_budget():
        categories = Category.query.all()

        if request.method == 'POST':
            category_id = int(request.form.get('category'))
            amount = float(request.form.get('amount'))
            period = request.form.get('period', 'monthly')

            # Calculate start and end dates based on period
            start_date = datetime.utcnow()
            if period == 'weekly':
                end_date = start_date + timedelta(days=7)
            elif period == 'monthly':
                end_date = start_date + timedelta(days=30)
            elif period == 'yearly':
                end_date = start_date + timedelta(days=365)

            budget = Budget(
                category_id=category_id,
                amount=amount,
                period=period,
                start_date=start_date,
                end_date=end_date
            )
            db.session.add(budget)
            db.session.commit()
            flash('Budget created successfully!', 'success')
            return redirect(url_for('main.budgets'))

        return render_template('add_budget.html', categories=categories)

    @main.route('/budgets/delete/<int:id>', methods=['POST'])
    @login_required
    def delete_budget(id):
        budget = Budget.query.get_or_404(id)
        db.session.delete(budget)
        db.session.commit()
        flash('Budget deleted successfully!', 'success')
        return redirect(url_for('main.budgets'))
