from flask import jsonify, request, g
from . import api_bp, require_api_key
from ..models import Goal
from .. import db


def serialize_goal(goal):
    progress = (goal.current_amount / goal.target_amount * 100) if goal.target_amount > 0 else 0
    return {
        'id': goal.id,
        'name': goal.name,
        'target_amount': goal.target_amount,
        'current_amount': goal.current_amount,
        'progress_percent': round(progress, 1),
        'deadline': goal.deadline.isoformat() if goal.deadline else None,
        'goal_type': goal.goal_type,
        'icon': goal.icon,
        'color': goal.color,
        'is_completed': goal.current_amount >= goal.target_amount,
    }


@api_bp.route('/goals', methods=['GET'])
@require_api_key('read')
def list_goals():
    goals = Goal.query.filter_by(user_id=g.api_user_id).all()
    return jsonify({'data': [serialize_goal(g_item) for g_item in goals]})


@api_bp.route('/goals/<int:id>', methods=['GET'])
@require_api_key('read')
def get_goal(id):
    goal = Goal.query.filter_by(id=id, user_id=g.api_user_id).first()
    if not goal:
        return jsonify({'error': 'Goal not found'}), 404
    return jsonify({'data': serialize_goal(goal)})


@api_bp.route('/goals/<int:id>/contribute', methods=['POST'])
@require_api_key('write_goals')
def contribute_to_goal(id):
    goal = Goal.query.filter_by(id=id, user_id=g.api_user_id).first()
    if not goal:
        return jsonify({'error': 'Goal not found'}), 404

    data = request.get_json()
    if not data or 'amount' not in data:
        return jsonify({'error': 'amount is required'}), 400

    goal.current_amount += float(data['amount'])
    db.session.commit()
    return jsonify({'data': serialize_goal(goal)})
