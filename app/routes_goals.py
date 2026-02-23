from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from . import db
from .models import Goal, Wallet
from datetime import datetime

goals_bp = Blueprint('goals', __name__)


@goals_bp.route('/goals')
@login_required
def goals():
    all_goals = Goal.query.filter_by(user_id=current_user.id).order_by(Goal.created_at.desc()).all()
    active_goals = [g for g in all_goals if not g.is_completed]
    completed_goals = [g for g in all_goals if g.is_completed]
    return render_template('goals.html', active_goals=active_goals, completed_goals=completed_goals)


@goals_bp.route('/goals/add', methods=['GET', 'POST'])
@login_required
def add_goal():
    if request.method == 'POST':
        goal = Goal(
            user_id=current_user.id,
            name=request.form.get('name', '').strip(),
            target_amount=float(request.form.get('target_amount', 0)),
            current_amount=float(request.form.get('current_amount', 0)),
            goal_type=request.form.get('goal_type', 'Custom'),
            icon=request.form.get('icon', '🎯'),
            color=request.form.get('color', '#6366f1'),
            notes=request.form.get('notes', '').strip() or None,
        )
        deadline = request.form.get('deadline')
        if deadline:
            goal.deadline = datetime.strptime(deadline, '%Y-%m-%d')
        db.session.add(goal)
        db.session.commit()
        flash('Goal created successfully!', 'success')
        return redirect(url_for('goals.goals'))
    return render_template('add_goal.html')


@goals_bp.route('/goals/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_goal(id):
    goal = Goal.query.get_or_404(id)
    if request.method == 'POST':
        goal.name = request.form.get('name', goal.name).strip()
        goal.target_amount = float(request.form.get('target_amount', goal.target_amount))
        goal.current_amount = float(request.form.get('current_amount', goal.current_amount))
        goal.goal_type = request.form.get('goal_type', goal.goal_type)
        goal.icon = request.form.get('icon', goal.icon)
        goal.color = request.form.get('color', goal.color)
        goal.notes = request.form.get('notes', '').strip() or None
        deadline = request.form.get('deadline')
        goal.deadline = datetime.strptime(deadline, '%Y-%m-%d') if deadline else None
        goal.is_completed = goal.current_amount >= goal.target_amount
        db.session.commit()
        flash('Goal updated successfully!', 'success')
        return redirect(url_for('goals.goals'))
    return render_template('edit_goal.html', goal=goal)


@goals_bp.route('/goals/delete/<int:id>', methods=['POST'])
@login_required
def delete_goal(id):
    goal = Goal.query.get_or_404(id)
    db.session.delete(goal)
    db.session.commit()
    flash('Goal deleted.', 'success')
    return redirect(url_for('goals.goals'))


@goals_bp.route('/goals/contribute/<int:id>', methods=['POST'])
@login_required
def contribute_to_goal(id):
    goal = Goal.query.get_or_404(id)
    amount = float(request.form.get('amount', 0))
    wallet_id = request.form.get('wallet_id')

    if amount <= 0:
        flash('Amount must be positive.', 'error')
        return redirect(url_for('goals.goals'))

    if wallet_id:
        wallet = Wallet.query.get(int(wallet_id))
        if wallet and wallet.balance >= amount:
            wallet.balance -= amount
        else:
            flash('Insufficient wallet balance.', 'error')
            return redirect(url_for('goals.goals'))

    goal.current_amount += amount
    if goal.current_amount >= goal.target_amount:
        goal.is_completed = True
        flash(f'Congratulations! Goal "{goal.name}" achieved!', 'success')
    else:
        flash(f'GHS {amount:.2f} contributed to "{goal.name}".', 'success')

    db.session.commit()
    return redirect(url_for('goals.goals'))
