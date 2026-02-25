from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from . import db
from .models import Goal, Wallet, GoalTask, GoalMilestone
from datetime import datetime

goals_bp = Blueprint('goals', __name__)


@goals_bp.route('/goals')
@login_required
def goals():
    all_goals = Goal.query.filter_by(user_id=current_user.id).order_by(Goal.created_at.desc()).all()
    active_goals = [g for g in all_goals if not g.is_completed]
    completed_goals = [g for g in all_goals if g.is_completed]
    
    # Smart Recommendations Logic
    recommendations = [
        {
            'name': 'Emergency Fund',
            'desc': 'Build a safety net for unexpected expenses',
            'target_amount': 18000.00,
            'timeframe': '24 months',
            'monthly_target': 750.00,
            'category': 'Emergency Fund',
            'priority': 5,
            'why': 'Financial experts recommend 6 months of expenses for security',
            'icon': '🛡️',
            'color': '#ef4444' # red
        },
        {
            'name': 'Retirement Savings',
            'desc': 'Secure your future with consistent retirement contributions',
            'target_amount': 50000.00,
            'timeframe': '60 months',
            'monthly_target': 833.33,
            'category': 'Retirement',
            'priority': 5,
            'why': 'Starting strong compounding early yields better results',
            'icon': '📈',
            'color': '#10b981' # green
        }
    ]
    return render_template('goals.html', active_goals=active_goals, completed_goals=completed_goals, recommendations=recommendations, datetime=datetime)


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
            priority=int(request.form.get('priority', 3)),
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
        goal.priority = int(request.form.get('priority', goal.priority))
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

@goals_bp.route('/goals/<int:id>/tasks', methods=['POST'])
@login_required
def add_task(id):
    goal = Goal.query.get_or_404(id)
    if goal.user_id != current_user.id:
        flash('Unauthorized', 'danger')
        return redirect(url_for('goals.goals'))
    
    title = request.form.get('title', '').strip()
    if title:
        task = GoalTask(
            goal_id=goal.id,
            title=title,
            priority=int(request.form.get('priority', 3)),
            due_date=datetime.strptime(request.form.get('due_date'), '%Y-%m-%d') if request.form.get('due_date') else None
        )
        db.session.add(task)
        db.session.commit()
        flash('Task added successfully.', 'success')
    return redirect(url_for('goals.goals'))

@goals_bp.route('/goals/tasks/<int:task_id>/toggle', methods=['POST'])
@login_required
def toggle_task(task_id):
    task = GoalTask.query.get_or_404(task_id)
    if task.goal.user_id != current_user.id:
        return {'status': 'error', 'message': 'Unauthorized'}, 403
    
    task.is_completed = not task.is_completed
    db.session.commit()
    # If it's an API request return JSON, else redirect
    if request.headers.get('Accept') == 'application/json':
        return {'status': 'success', 'is_completed': task.is_completed}
    return redirect(url_for('goals.goals'))
    
@goals_bp.route('/goals/tasks/<int:task_id>/delete', methods=['POST'])
@login_required
def delete_task(task_id):
    task = GoalTask.query.get_or_404(task_id)
    if task.goal.user_id != current_user.id:
        flash('Unauthorized', 'danger')
        return redirect(url_for('goals.goals'))
    
    db.session.delete(task)
    db.session.commit()
    flash('Task deleted.', 'success')
    return redirect(url_for('goals.goals'))

@goals_bp.route('/goals/<int:id>/milestones', methods=['POST'])
@login_required
def add_milestone(id):
    goal = Goal.query.get_or_404(id)
    if goal.user_id != current_user.id:
        flash('Unauthorized', 'danger')
        return redirect(url_for('goals.goals'))
    
    title = request.form.get('title', '').strip()
    target_amount = float(request.form.get('target_amount', 0))
    if title and target_amount > 0:
        milestone = GoalMilestone(
            goal_id=goal.id,
            title=title,
            target_amount=target_amount
        )
        db.session.add(milestone)
        db.session.commit()
        flash('Milestone added successfully.', 'success')
    return redirect(url_for('goals.goals'))

@goals_bp.route('/goals/milestones/<int:milestone_id>/delete', methods=['POST'])
@login_required
def delete_milestone(milestone_id):
    milestone = GoalMilestone.query.get_or_404(milestone_id)
    if milestone.goal.user_id != current_user.id:
        flash('Unauthorized', 'danger')
        return redirect(url_for('goals.goals'))
    
    db.session.delete(milestone)
    db.session.commit()
    flash('Milestone deleted.', 'success')
    return redirect(url_for('goals.goals'))
