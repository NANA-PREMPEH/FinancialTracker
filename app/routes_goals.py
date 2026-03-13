from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from . import db
from .models import Goal, Wallet, GoalTask, GoalMilestone
from .push_events import check_goal_milestone
from datetime import datetime, timedelta

goals_bp = Blueprint('goals', __name__)


@goals_bp.route('/goals')
@login_required
def goals():
    all_goals = Goal.query.filter_by(user_id=current_user.id).order_by(Goal.priority.desc(), Goal.created_at.desc()).all()
    active_goals = [g for g in all_goals if not g.is_completed]
    completed_goals = [g for g in all_goals if g.is_completed]
    wallets = Wallet.query.filter_by(user_id=current_user.id).order_by(Wallet.name.asc()).all()

    now = datetime.utcnow()
    goal_insights = {
        'on_track': 0,
        'at_risk': 0,
        'overdue': 0,
        'avg_progress': 0.0,
        'avg_monthly_required': 0.0
    }
    goal_forecasts = {}
    total_progress = 0.0
    total_monthly_required = 0.0

    for goal in active_goals:
        remaining = max(goal.target_amount - goal.current_amount, 0.0)
        progress = goal.progress if hasattr(goal, 'progress') else 0.0
        total_progress += progress

        created_at = goal.created_at or now
        elapsed_days = max((now - created_at).days, 1)
        elapsed_months = max(elapsed_days / 30.0, 0.1)
        historical_monthly = goal.current_amount / elapsed_months if goal.current_amount > 0 else 0.0

        forecast = {
            'status': 'At Risk',
            'required_monthly': 0.0,
            'historical_monthly': historical_monthly,
            'projected_days': None,
            'projected_date': None
        }

        if goal.deadline:
            days_left = (goal.deadline - now).days
            months_left = max(days_left / 30.0, 0.1)
            required_monthly = remaining / months_left if remaining > 0 else 0.0
            total_monthly_required += required_monthly
            forecast['required_monthly'] = required_monthly

            if remaining <= 0:
                forecast['status'] = 'On Track'
                goal_insights['on_track'] += 1
            elif days_left < 0:
                forecast['status'] = 'Overdue'
                goal_insights['overdue'] += 1
            elif historical_monthly >= required_monthly * 0.9:
                forecast['status'] = 'On Track'
                goal_insights['on_track'] += 1
            else:
                forecast['status'] = 'At Risk'
                goal_insights['at_risk'] += 1
        else:
            if progress >= 40:
                forecast['status'] = 'On Track'
                goal_insights['on_track'] += 1
            else:
                forecast['status'] = 'At Risk'
                goal_insights['at_risk'] += 1

        if remaining > 0 and historical_monthly > 0:
            projected_months = remaining / historical_monthly
            projected_days = int(projected_months * 30)
            forecast['projected_days'] = projected_days
            forecast['projected_date'] = now + timedelta(days=projected_days)

        goal_forecasts[goal.id] = forecast

    if active_goals:
        goal_insights['avg_progress'] = round(total_progress / len(active_goals), 1)
        goal_insights['avg_monthly_required'] = round(total_monthly_required / len(active_goals), 2)
    
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
    return render_template(
        'goals.html',
        active_goals=active_goals,
        completed_goals=completed_goals,
        recommendations=recommendations,
        goal_insights=goal_insights,
        goal_forecasts=goal_forecasts,
        wallets=wallets,
        datetime=datetime
    )


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
    goal = Goal.query.filter_by(id=id, user_id=current_user.id).first_or_404()
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
    goal = Goal.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    db.session.delete(goal)
    db.session.commit()
    flash('Goal deleted.', 'success')
    return redirect(url_for('goals.goals'))


@goals_bp.route('/goals/contribute/<int:id>', methods=['POST'])
@login_required
def contribute_to_goal(id):
    goal = Goal.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    amount = float(request.form.get('amount', 0))
    wallet_id = request.form.get('wallet_id')

    if amount <= 0:
        flash('Amount must be positive.', 'error')
        return redirect(url_for('goals.goals'))

    if wallet_id:
        wallet = Wallet.query.filter_by(id=int(wallet_id), user_id=current_user.id).first()
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

    # Push notification for goal milestones
    try:
        check_goal_milestone(current_user.id, goal)
    except Exception:
        pass

    return redirect(url_for('goals.goals'))

@goals_bp.route('/goals/<int:id>/tasks', methods=['POST'])
@login_required
def add_task(id):
    goal = Goal.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    
    title = request.form.get('title', '').strip()
    if title:
        task = GoalTask(
            user_id=current_user.id,
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
    task = GoalTask.query.join(Goal).filter(Goal.user_id == current_user.id, GoalTask.id == task_id).first_or_404()
    
    task.is_completed = not task.is_completed
    db.session.commit()
    # If it's an API request return JSON, else redirect
    if request.headers.get('Accept') == 'application/json':
        return {'status': 'success', 'is_completed': task.is_completed}
    return redirect(url_for('goals.goals'))
    
@goals_bp.route('/goals/tasks/<int:task_id>/delete', methods=['POST'])
@login_required
def delete_task(task_id):
    task = GoalTask.query.join(Goal).filter(Goal.user_id == current_user.id, GoalTask.id == task_id).first_or_404()
    
    db.session.delete(task)
    db.session.commit()
    flash('Task deleted.', 'success')
    return redirect(url_for('goals.goals'))

@goals_bp.route('/goals/<int:id>/milestones', methods=['POST'])
@login_required
def add_milestone(id):
    goal = Goal.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    
    title = request.form.get('title', '').strip()
    target_amount = float(request.form.get('target_amount', 0))
    if title and target_amount > 0:
        milestone = GoalMilestone(
            user_id=current_user.id,
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
    milestone = GoalMilestone.query.join(Goal).filter(Goal.user_id == current_user.id, GoalMilestone.id == milestone_id).first_or_404()
    
    db.session.delete(milestone)
    db.session.commit()
    flash('Milestone deleted.', 'success')
    return redirect(url_for('goals.goals'))
