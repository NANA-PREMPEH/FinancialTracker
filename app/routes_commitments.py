from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from . import db
from .models import Commitment, Wallet, Expense, Category
from datetime import datetime

commitments_bp = Blueprint('commitments', __name__)

COMMITMENT_CATEGORIES = ['Church Levy', 'Church Group', 'Ceremony', 'Donation', 'Dues', 'Family Support', 'Harvest', 'Custom']


@commitments_bp.route('/commitments')
@login_required
def commitments_list():
    all_commitments = Commitment.query.filter_by(user_id=current_user.id).order_by(Commitment.due_date.asc()).all()
    # Update overdue status
    for c in all_commitments:
        if c.status == 'pending' and c.due_date and c.due_date < datetime.utcnow():
            c.status = 'overdue'
    db.session.commit()
    pending = [c for c in all_commitments if c.status in ('pending', 'overdue')]
    paid = [c for c in all_commitments if c.status == 'paid']
    total_pending = sum(c.amount for c in pending)
    return render_template('commitments.html', pending=pending, paid=paid,
                           total_pending=total_pending, categories=COMMITMENT_CATEGORIES)


@commitments_bp.route('/commitments/add', methods=['POST'])
@login_required
def add_commitment():
    commitment = Commitment(
        user_id=current_user.id,
        name=request.form.get('name', '').strip(),
        commitment_category=request.form.get('commitment_category', 'Custom'),
        amount=float(request.form.get('amount', 0)),
        frequency=request.form.get('frequency', 'one_time'),
        notes=request.form.get('notes', '').strip() or None,
    )
    due = request.form.get('due_date')
    if due:
        commitment.due_date = datetime.strptime(due, '%Y-%m-%d')
    db.session.add(commitment)
    db.session.commit()
    flash('Commitment added.', 'success')
    return redirect(url_for('commitments.commitments_list'))


@commitments_bp.route('/commitments/edit/<int:id>', methods=['POST'])
@login_required
def edit_commitment(id):
    c = Commitment.query.get_or_404(id)
    c.name = request.form.get('name', c.name).strip()
    c.commitment_category = request.form.get('commitment_category', c.commitment_category)
    c.amount = float(request.form.get('amount', c.amount))
    c.frequency = request.form.get('frequency', c.frequency)
    c.notes = request.form.get('notes', '').strip() or None
    due = request.form.get('due_date')
    c.due_date = datetime.strptime(due, '%Y-%m-%d') if due else None
    db.session.commit()
    flash('Commitment updated.', 'success')
    return redirect(url_for('commitments.commitments_list'))


@commitments_bp.route('/commitments/delete/<int:id>', methods=['POST'])
@login_required
def delete_commitment(id):
    c = Commitment.query.get_or_404(id)
    db.session.delete(c)
    db.session.commit()
    flash('Commitment deleted.', 'success')
    return redirect(url_for('commitments.commitments_list'))


@commitments_bp.route('/commitments/pay/<int:id>', methods=['POST'])
@login_required
def pay_commitment(id):
    c = Commitment.query.get_or_404(id)
    wallet_id = request.form.get('wallet_id')
    if wallet_id:
        wallet = Wallet.query.get(int(wallet_id))
        if wallet and wallet.balance >= c.amount:
            wallet.balance -= c.amount
            # Create expense record
            cat = Category.query.filter_by(name='Donation').first()
            if not cat:
                cat = Category.query.first()
            expense = Expense(
                user_id=current_user.id, amount=c.amount,
                description=f'Commitment: {c.name}', date=datetime.utcnow(),
                category_id=cat.id, wallet_id=wallet.id,
                transaction_type='expense', tags='commitment'
            )
            db.session.add(expense)
        else:
            flash('Insufficient wallet balance.', 'error')
            return redirect(url_for('commitments.commitments_list'))
    c.status = 'paid'
    db.session.commit()
    flash(f'Commitment "{c.name}" marked as paid.', 'success')
    return redirect(url_for('commitments.commitments_list'))
