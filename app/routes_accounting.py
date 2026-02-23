from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from . import db
from .models import ChartOfAccount, JournalEntry
from datetime import datetime

accounting_bp = Blueprint('accounting', __name__)

ACCOUNT_TYPES = ['Asset', 'Liability', 'Equity', 'Revenue', 'Expense']


@accounting_bp.route('/accounting')
@login_required
def accounting_overview():
    accounts = ChartOfAccount.query.filter_by(user_id=current_user.id).order_by(ChartOfAccount.code).all()
    entries = JournalEntry.query.filter_by(user_id=current_user.id).order_by(JournalEntry.date.desc()).limit(50).all()
    return render_template('accounting.html', accounts=accounts, entries=entries, account_types=ACCOUNT_TYPES)


@accounting_bp.route('/accounting/chart/add', methods=['POST'])
@login_required
def add_account():
    account = ChartOfAccount(
        user_id=current_user.id,
        code=request.form.get('code', '').strip(),
        name=request.form.get('name', '').strip(),
        account_type=request.form.get('account_type', 'Asset'),
        parent_id=int(request.form.get('parent_id')) if request.form.get('parent_id') else None,
    )
    db.session.add(account)
    db.session.commit()
    flash('Account added to chart.', 'success')
    return redirect(url_for('accounting.accounting_overview'))


@accounting_bp.route('/accounting/chart/delete/<int:id>', methods=['POST'])
@login_required
def delete_account(id):
    account = ChartOfAccount.query.get_or_404(id)
    db.session.delete(account)
    db.session.commit()
    flash('Account deleted.', 'success')
    return redirect(url_for('accounting.accounting_overview'))


@accounting_bp.route('/accounting/journal/add', methods=['POST'])
@login_required
def add_journal_entry():
    entry = JournalEntry(
        user_id=current_user.id,
        date=datetime.strptime(request.form['date'], '%Y-%m-%d'),
        description=request.form.get('description', '').strip(),
        debit_account_id=int(request.form['debit_account_id']),
        credit_account_id=int(request.form['credit_account_id']),
        amount=float(request.form.get('amount', 0)),
        reference=request.form.get('reference', '').strip() or None,
    )
    # Update account balances
    debit_acc = ChartOfAccount.query.get(entry.debit_account_id)
    credit_acc = ChartOfAccount.query.get(entry.credit_account_id)
    if debit_acc:
        debit_acc.balance += entry.amount
    if credit_acc:
        credit_acc.balance -= entry.amount

    db.session.add(entry)
    db.session.commit()
    flash('Journal entry recorded.', 'success')
    return redirect(url_for('accounting.accounting_overview'))


@accounting_bp.route('/accounting/journal/delete/<int:id>', methods=['POST'])
@login_required
def delete_journal_entry(id):
    entry = JournalEntry.query.get_or_404(id)
    # Reverse account balances
    debit_acc = ChartOfAccount.query.get(entry.debit_account_id)
    credit_acc = ChartOfAccount.query.get(entry.credit_account_id)
    if debit_acc:
        debit_acc.balance -= entry.amount
    if credit_acc:
        credit_acc.balance += entry.amount
    db.session.delete(entry)
    db.session.commit()
    flash('Journal entry deleted.', 'success')
    return redirect(url_for('accounting.accounting_overview'))
