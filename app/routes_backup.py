from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, Response
from flask_login import login_required, current_user
from . import db
from .models import (Wallet, Category, Expense, Budget, RecurringTransaction, Project, ProjectItem,
                     ProjectItemPayment, FinancialSummary, WishlistItem, Creditor, Goal, Investment,
                     InsurancePolicy, PensionScheme, Commitment)
from datetime import datetime
import json

backup_bp = Blueprint('backup', __name__)


@backup_bp.route('/backup')
@login_required
def backup_page():
    return render_template('backup.html')


@backup_bp.route('/backup/create', methods=['POST'])
@login_required
def create_backup():
    uid = current_user.id
    data = {
        'backup_date': datetime.utcnow().isoformat(),
        'user': {'name': current_user.name, 'email': current_user.email},
        'wallets': [{'name': w.name, 'balance': w.balance, 'currency': w.currency, 'icon': w.icon,
                      'wallet_type': w.wallet_type, 'account_number': w.account_number}
                     for w in Wallet.query.filter_by(user_id=uid).all()],
        'categories': [{'name': c.name, 'icon': c.icon, 'is_custom': c.is_custom}
                        for c in Category.query.filter_by(user_id=uid).all()],
        'expenses': [{'amount': e.amount, 'description': e.description,
                       'date': e.date.isoformat() if e.date else None,
                       'category': e.category.name if e.category else '', 'wallet': e.wallet.name if e.wallet else '',
                       'notes': e.notes, 'tags': e.tags, 'transaction_type': e.transaction_type}
                      for e in Expense.query.filter_by(user_id=uid).all()],
        'budgets': [{'category': b.category.name if b.category else '', 'amount': b.amount, 'period': b.period}
                     for b in Budget.query.filter_by(user_id=uid).all()],
        'goals': [{'name': g.name, 'target_amount': g.target_amount, 'current_amount': g.current_amount,
                    'goal_type': g.goal_type, 'deadline': g.deadline.isoformat() if g.deadline else None}
                   for g in Goal.query.filter_by(user_id=uid).all()],
        'creditors': [{'name': c.name, 'amount': c.amount, 'currency': c.currency, 'description': c.description}
                       for c in Creditor.query.filter_by(user_id=uid).all()],
        'investments': [{'name': i.name, 'investment_type': i.investment_type, 'amount_invested': i.amount_invested,
                          'current_value': i.current_value, 'platform': i.platform}
                         for i in Investment.query.filter_by(user_id=uid).all()],
    }

    json_str = json.dumps(data, indent=2)
    return Response(
        json_str,
        mimetype='application/json',
        headers={'Content-Disposition': f'attachment;filename=fintracker_backup_{datetime.utcnow().strftime("%Y%m%d")}.json'}
    )


@backup_bp.route('/backup/restore', methods=['POST'])
@login_required
def restore_backup():
    file = request.files.get('file')
    if not file or not file.filename.endswith('.json'):
        flash('Please upload a JSON backup file.', 'error')
        return redirect(url_for('backup.backup_page'))

    try:
        data = json.loads(file.stream.read().decode('utf-8'))
        flash(f'Backup file loaded. Contains {len(data.get("expenses", []))} transactions, '
              f'{len(data.get("wallets", []))} wallets, {len(data.get("goals", []))} goals. '
              f'Manual review recommended before full restore.', 'success')
    except Exception as e:
        flash(f'Failed to read backup: {str(e)}', 'error')

    return redirect(url_for('backup.backup_page'))
