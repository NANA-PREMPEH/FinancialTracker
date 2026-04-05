from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from . import db
from .models import Expense, Category, Wallet
from .utils import get_exchange_rate
from datetime import datetime, timedelta
from sqlalchemy import func, or_


def register_routes(main):

    @main.route('/add', methods=['GET', 'POST'])
    @login_required
    def add_expense():
        categories = Category.query.filter_by(user_id=current_user.id).all()
        wallets = Wallet.query.filter_by(user_id=current_user.id).all()
        from .currencies import CURRENCIES

        if request.method == 'POST':
            description = request.form.get('description')
            category_id_str = request.form.get('category')
            category_id = int(category_id_str) if category_id_str else Category.query.filter_by(user_id=current_user.id).first().id
            wallet_id_str = request.form.get('wallet')
            if not wallet_id_str:
                flash('Please select a wallet!', 'error')
                return redirect(url_for('main.add_expense'))
            wallet_id = int(wallet_id_str)
            date_str = request.form.get('date')
            notes = request.form.get('notes', '')
            tags = request.form.get('tags', '')
            transaction_type = request.form.get('transaction_type', 'expense')
            currency = request.form.get('currency', 'GHS')

            if not description or not description.strip():
                flash('Description is required!', 'error')
                return redirect(url_for('main.add_expense'))

            try:
                input_amount = float(request.form.get('amount'))
                if input_amount <= 0:
                     flash('Amount must be greater than 0!', 'error')
                     return redirect(url_for('main.add_expense'))
            except (ValueError, TypeError):
                flash('Invalid amount provided!', 'error')
                return redirect(url_for('main.add_expense'))

            if date_str:
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            else:
                date_obj = datetime.utcnow()

            # Handle file upload
            receipt_path = None
            if 'receipt' in request.files:
                file = request.files['receipt']
                if file and file.filename:
                    import os
                    from werkzeug.utils import secure_filename
                    filename = secure_filename(file.filename)
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename = f"{timestamp}_{filename}"
                    filepath = os.path.join('app', 'static', 'receipts', filename)
                    file.save(filepath)
                    receipt_path = f"receipts/{filename}"

            # Currency Conversion Logic
            wallet = Wallet.query.filter_by(id=wallet_id, user_id=current_user.id).first_or_404()
            converted_amount = input_amount

            if currency != wallet.currency:
                rate = get_exchange_rate(currency, wallet.currency)
                converted_amount = input_amount * rate
                print(f"Converting {input_amount} {currency} to {converted_amount} {wallet.currency} (Rate: {rate})")

            if transaction_type == 'transfer':
                to_wallet_id_str = request.form.get('to_wallet')
                if not to_wallet_id_str:
                    flash('Please select a destination wallet for the transfer.', 'error')
                    return redirect(url_for('main.add_expense'))

                to_wallet_id = int(to_wallet_id_str)
                if wallet_id == to_wallet_id:
                    flash('Cannot transfer to the same wallet!', 'error')
                    return redirect(url_for('main.add_expense'))

                to_wallet = Wallet.query.filter_by(id=to_wallet_id, user_id=current_user.id).first_or_404()
                if not to_wallet:
                    flash('Destination wallet not found!', 'error')
                    return redirect(url_for('main.add_expense'))

                # Ensure "Transfer" category exists for this user
                transfer_cat = Category.query.filter_by(name='Transfer', user_id=current_user.id).first()
                if not transfer_cat:
                    transfer_cat = Category(name='Transfer', icon='??', user_id=current_user.id)
                    db.session.add(transfer_cat)
                    db.session.flush() # flush to get ID
                category_id = transfer_cat.id

                # Create the withdrawal record (source wallet)
                expense_out = Expense(
                    user_id=current_user.id,
                    amount=converted_amount,
                    description=f"Transfer to {to_wallet.name}: {description}",
                    category_id=category_id,
                    wallet_id=wallet_id,
                    date=date_obj,
                    notes=notes,
                    tags=tags,
                    receipt_path=receipt_path,
                    transaction_type='transfer_out',
                    original_amount=input_amount,
                    original_currency=currency
                )
                db.session.add(expense_out)
                wallet.balance = float(wallet.balance) - converted_amount

                # Create the deposit record (destination wallet)
                to_converted_amount = input_amount
                if currency != to_wallet.currency:
                    rate = get_exchange_rate(currency, to_wallet.currency)
                    to_converted_amount = input_amount * rate

                expense_in = Expense(
                    user_id=current_user.id,
                    amount=to_converted_amount,
                    description=f"Transfer from {wallet.name}: {description}",
                    category_id=category_id,
                    wallet_id=to_wallet_id,
                    date=date_obj,
                    notes=notes,
                    tags=tags,
                    receipt_path=receipt_path,
                    transaction_type='transfer_in',
                    original_amount=input_amount,
                    original_currency=currency
                )
                db.session.add(expense_in)
                to_wallet.balance = float(to_wallet.balance) + to_converted_amount

                db.session.commit()
                flash(f'Transfer successful! ({input_amount} {currency})', 'success')

            else:
                expense = Expense(
                    user_id=current_user.id,
                    amount=converted_amount,
                    description=description,
                    category_id=category_id,
                    wallet_id=wallet_id,
                    date=date_obj,
                    notes=notes,
                    tags=tags,
                    receipt_path=receipt_path,
                    transaction_type=transaction_type,
                    original_amount=input_amount,
                    original_currency=currency
                )
                db.session.add(expense)

                # Update wallet balance (using converted amount)
                if transaction_type == 'expense':
                    wallet.balance = float(wallet.balance) - converted_amount
                elif transaction_type in ('income', 'liability', 'debt_recovery'):
                    wallet.balance = float(wallet.balance) + converted_amount

                db.session.commit()
                flash(f'Transaction added successfully! ({input_amount} {currency})', 'success')

            action = request.form.get('action')
            if action == 'save_and_continue':
                return redirect(url_for('main.add_expense'))
            else:
                return redirect(url_for('main.all_expenses'))

        return render_template('add_expense.html', categories=categories, wallets=wallets, currencies=CURRENCIES)

    @main.route('/edit/<int:id>', methods=['GET', 'POST'])
    @login_required
    def edit_expense(id):
        expense = Expense.query.filter_by(id=id, user_id=current_user.id).first_or_404()
        categories = Category.query.filter_by(user_id=current_user.id).all()
        wallets = Wallet.query.filter_by(user_id=current_user.id).all()

        if request.method == 'POST':
            old_amount = expense.amount
            old_type = expense.transaction_type
            old_wallet_id = expense.wallet_id

            expense.amount = float(request.form.get('amount'))
            expense.description = request.form.get('description')
            expense.category_id = int(request.form.get('category'))
            expense.wallet_id = int(request.form.get('wallet'))
            expense.notes = request.form.get('notes', '')
            expense.tags = request.form.get('tags', '')
            expense.transaction_type = request.form.get('transaction_type', 'expense')
            date_str = request.form.get('date')

            if date_str:
                expense.date = datetime.strptime(date_str, '%Y-%m-%d')

            # Handle file upload
            if 'receipt' in request.files:
                file = request.files['receipt']
                if file and file.filename:
                    import os
                    from werkzeug.utils import secure_filename
                    filename = secure_filename(file.filename)
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename = f"{timestamp}_{filename}"
                    filepath = os.path.join('app', 'static', 'receipts', filename)
                    file.save(filepath)
                    expense.receipt_path = f"receipts/{filename}"

            # Update wallet balances
            old_wallet = Wallet.query.filter_by(id=old_wallet_id, user_id=current_user.id).first_or_404()
            new_wallet = Wallet.query.filter_by(id=expense.wallet_id, user_id=current_user.id).first_or_404()

            # Reverse old transaction
            if old_type == 'expense':
                old_wallet.balance = float(old_wallet.balance) + old_amount
            elif old_type in ('income', 'liability', 'debt_recovery'):
                old_wallet.balance = float(old_wallet.balance) - old_amount

            # Apply new transaction
            if expense.transaction_type == 'expense':
                new_wallet.balance = float(new_wallet.balance) - expense.amount
            elif expense.transaction_type in ('income', 'liability', 'debt_recovery'):
                new_wallet.balance = float(new_wallet.balance) + expense.amount

            db.session.commit()
            flash('Transaction updated successfully!', 'success')
            return redirect(url_for('main.all_expenses') + f'#expense-{id}')

        return render_template('edit_expense.html', expense=expense, categories=categories, wallets=wallets)

    @main.route('/delete/<int:id>', methods=['POST'])
    @login_required
    def delete_expense(id):
        expense = Expense.query.filter_by(id=id, user_id=current_user.id).first_or_404()

        # Update wallet balance
        wallet = Wallet.query.filter_by(id=expense.wallet_id, user_id=current_user.id).first_or_404()
        if expense.transaction_type == 'expense':
            wallet.balance = float(wallet.balance) + expense.amount
        elif expense.transaction_type in ('income', 'liability', 'debt_recovery'):
            wallet.balance = float(wallet.balance) - expense.amount

        db.session.delete(expense)
        db.session.commit()
        flash('Transaction deleted successfully!', 'success')
        return redirect(url_for('main.all_expenses'))

    @main.route('/expenses')
    @main.route('/transactions')
    @login_required
    def all_expenses():
        # Search and filter
        search_query = request.args.get('search', '')
        category_filter = request.args.get('category', '')
        wallet_filter = request.args.get('wallet', '')
        type_filter = request.args.get('type', '')
        date_from = request.args.get('from', '')
        date_to = request.args.get('to', '')

        query = Expense.query.filter_by(user_id=current_user.id)

        if search_query:
            query = query.filter(or_(
                Expense.description.contains(search_query),
                Expense.notes.contains(search_query),
                Expense.tags.contains(search_query)
            ))

        if category_filter:
            query = query.filter_by(category_id=int(category_filter))
        else:
            # Exclude Transfer category by default unless specifically filtered for it
            if type_filter != 'transfer':
                transfer_cat = Category.query.filter_by(name='Transfer', user_id=current_user.id).first()
                if transfer_cat:
                    query = query.filter(Expense.category_id != transfer_cat.id)

        if wallet_filter:
            query = query.filter_by(wallet_id=int(wallet_filter))

        if type_filter:
            if type_filter == 'transfer':
                query = query.filter(Expense.transaction_type.in_(['transfer', 'transfer_out', 'transfer_in', 'expense', 'income']))
            else:
                query = query.filter_by(transaction_type=type_filter)

        if date_from:
            query = query.filter(Expense.date >= datetime.strptime(date_from, '%Y-%m-%d'))

        if date_to:
            query = query.filter(Expense.date < datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1))

        # Sorting
        sort_by = request.args.get('sort', 'date')
        sort_order = request.args.get('order', 'desc')

        if sort_by == 'date':
            if sort_order == 'asc':
                query = query.order_by(Expense.date.asc())
            else:
                query = query.order_by(Expense.date.desc())
        elif sort_by == 'description':
            if sort_order == 'asc':
                query = query.order_by(Expense.description.asc())
            else:
                query = query.order_by(Expense.description.desc())
        elif sort_by == 'category':
            query = query.join(Category)
            if sort_order == 'asc':
                query = query.order_by(Category.name.asc())
            else:
                query = query.order_by(Category.name.desc())
        elif sort_by == 'amount':
            if sort_order == 'asc':
                query = query.order_by(Expense.amount.asc())
            else:
                query = query.order_by(Expense.amount.desc())
        else:
            # Default fallback
            query = query.order_by(Expense.date.desc())

        expenses = query.all()
        categories = Category.query.filter_by(user_id=current_user.id).all()
        wallets = Wallet.query.filter_by(user_id=current_user.id).all()

        # AJAX live search: return JSON with rendered partial
        if request.args.get('ajax') == '1':
            html = render_template('_partials/expense_rows.html', expenses=expenses)
            return jsonify({'html': html, 'count': len(expenses)})

        return render_template('all_expenses.html',
                             expenses=expenses,
                             categories=categories,
                             wallets=wallets,
                             filters={
                                 'search': search_query,
                                 'category': category_filter,
                                 'wallet': wallet_filter,
                                 'type': type_filter,
                                 'from': date_from,
                                 'to': date_to,
                                 'sort': sort_by,
                                 'order': sort_order
                             })
