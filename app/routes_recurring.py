from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from . import db
from .models import Category, Wallet, RecurringTransaction
from datetime import datetime, timedelta


def register_routes(main):

    @main.route('/recurring')
    @main.route('/recurring-transactions')
    @login_required
    def recurring_transactions():
        recurring = RecurringTransaction.query.filter_by(is_active=True).all()
        return render_template('recurring.html', recurring=recurring)

    @main.route('/recurring/add', methods=['GET', 'POST'])
    @login_required
    def add_recurring():
        categories = Category.query.all()
        wallets = Wallet.query.all()

        if request.method == 'POST':
            amount = float(request.form.get('amount'))
            description = request.form.get('description')
            category_id = int(request.form.get('category'))
            wallet_id = int(request.form.get('wallet'))
            frequency = request.form.get('frequency')
            transaction_type = request.form.get('transaction_type', 'expense')
            start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d')
            notes = request.form.get('notes', '')

            # Calculate next due date
            if frequency == 'daily':
                next_due = start_date + timedelta(days=1)
            elif frequency == 'weekly':
                next_due = start_date + timedelta(days=7)
            elif frequency == 'monthly':
                next_due = start_date + timedelta(days=30)
            elif frequency == 'yearly':
                next_due = start_date + timedelta(days=365)

            recurring = RecurringTransaction(
                user_id=current_user.id,
                amount=amount,
                description=description,
                category_id=category_id,
                wallet_id=wallet_id,
                transaction_type=transaction_type,
                frequency=frequency,
                start_date=start_date,
                next_due=next_due,
                notes=notes
            )
            db.session.add(recurring)
            db.session.commit()
            flash('Recurring transaction created successfully!', 'success')
            return redirect(url_for('main.recurring_transactions'))

        return render_template('add_recurring.html', categories=categories, wallets=wallets)

    @main.route('/recurring/edit/<int:id>', methods=['GET', 'POST'])
    @login_required
    def edit_recurring(id):
        recurring = RecurringTransaction.query.get_or_404(id)
        categories = Category.query.all()
        wallets = Wallet.query.all()

        if request.method == 'POST':
            recurring.amount = float(request.form.get('amount'))
            recurring.description = request.form.get('description')
            recurring.category_id = int(request.form.get('category'))
            recurring.wallet_id = int(request.form.get('wallet'))
            recurring.transaction_type = request.form.get('transaction_type', 'expense')
            recurring.frequency = request.form.get('frequency')
            recurring.notes = request.form.get('notes', '')
            start_date_str = request.form.get('start_date')

            if start_date_str:
                recurring.start_date = datetime.strptime(start_date_str, '%Y-%m-%d')

            # Recalculate next due date based on frequency
            if recurring.frequency == 'daily':
                recurring.next_due = recurring.start_date + timedelta(days=1)
            elif recurring.frequency == 'weekly':
                recurring.next_due = recurring.start_date + timedelta(days=7)
            elif recurring.frequency == 'monthly':
                recurring.next_due = recurring.start_date + timedelta(days=30)
            elif recurring.frequency == 'yearly':
                recurring.next_due = recurring.start_date + timedelta(days=365)

            db.session.commit()
            flash('Recurring transaction updated successfully!', 'success')
            return redirect(url_for('main.recurring_transactions') + f'#recurring-{id}')

        return render_template('edit_recurring.html', recurring=recurring, categories=categories, wallets=wallets)

    @main.route('/recurring/delete/<int:id>', methods=['POST'])
    @login_required
    def delete_recurring(id):
        recurring = RecurringTransaction.query.get_or_404(id)
        db.session.delete(recurring)
        db.session.commit()
        flash('Recurring transaction deleted successfully!', 'success')
        return redirect(url_for('main.recurring_transactions'))
