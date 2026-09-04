from flask import render_template, request, redirect, url_for, flash, jsonify, Response
from flask_login import login_required, current_user
from sqlalchemy import or_
from sqlalchemy.orm import joinedload
from . import db
from .models import Expense, Category, Wallet, WalletShare
from .utils import get_exchange_rate
import csv
import io
from datetime import datetime, timedelta


def register_routes(main):

    @main.route('/wallets')
    @login_required
    def wallets():
        all_wallets = Wallet.query.filter_by(user_id=current_user.id) \
            .order_by(Wallet.balance.desc(), Wallet.name.asc()) \
            .all()
        
        # Wallets shared with me (accepted)
        shared_shares = WalletShare.query.filter_by(
            shared_with_id=current_user.id, accepted=True
        ).order_by(WalletShare.created_at.desc()).all()
        shared_with_me = shared_shares
        
        # Wallets I've shared with others
        shared_wallets = WalletShare.query.filter_by(
            owner_id=current_user.id
        ).order_by(WalletShare.created_at.desc()).all()
        
        # Pending invites for me
        pending_invites = WalletShare.query.filter_by(
            shared_with_id=current_user.id, accepted=False
        ).order_by(WalletShare.created_at.desc()).all()

        # Calculate totals
        totals_by_currency = {}
        grand_total = 0.0
        primary_currency = current_user.default_currency or 'GHS'
        
        # Process owned wallets
        for wallet in all_wallets:
            currency = wallet.currency
            balance = float(wallet.balance)
            if currency not in totals_by_currency:
                totals_by_currency[currency] = 0.0
            totals_by_currency[currency] += balance
            
            # Convert to primary currency for grand total
            if currency == primary_currency:
                grand_total += balance
            else:
                rate = get_exchange_rate(currency, primary_currency)
                grand_total += balance * rate

        # Process shared wallets (that I have access to)
        for share in shared_shares:
            wallet = share.wallet
            currency = wallet.currency
            balance = float(wallet.balance)
            if currency not in totals_by_currency:
                totals_by_currency[currency] = 0.0
            totals_by_currency[currency] += balance
            
            # Convert to primary currency for grand total
            if currency == primary_currency:
                grand_total += balance
            else:
                rate = get_exchange_rate(currency, primary_currency)
                grand_total += balance * rate
        
        # Fetch recent transfers
        transfers = []
        transfer_category = Category.query.filter_by(name='Transfer', user_id=current_user.id).first()
        if transfer_category:
            transfers = Expense.query.filter_by(user_id=current_user.id, category_id=transfer_category.id)\
                .order_by(Expense.date.desc())\
                .limit(8).all()

        return render_template('wallets.html', 
                               wallets=all_wallets, 
                               shared_wallets=shared_wallets,
                               shared_with_me=shared_with_me,
                               pending_invites=pending_invites,
                               transfers=transfers, 
                               totals_by_currency=totals_by_currency, 
                               grand_total=grand_total,
                               primary_currency=primary_currency,
                               can_transfer=len(all_wallets) > 1,
                               now_date=datetime.utcnow().date().isoformat())

    @main.route('/wallets/add', methods=['GET', 'POST'])
    @login_required
    def add_wallet():
        from .currencies import CURRENCIES
        if request.method == 'POST':
            name = request.form.get('name')
            balance = float(request.form.get('balance', 0))
            currency = request.form.get('currency', 'GHS')
            icon = request.form.get('icon', '\U0001f4b0')
            wallet_type = request.form.get('wallet_type', 'cash')
            account_number = request.form.get('account_number')
            is_shared = request.form.get('is_shared') == 'on'

            wallet = Wallet(
                name=name,
                balance=balance,
                currency=currency,
                icon=icon,
                wallet_type=wallet_type,
                account_number=account_number,
                is_shared=is_shared,
                user_id=current_user.id
            )
            db.session.add(wallet)
            db.session.commit()
            flash('Wallet created successfully!', 'success')
            return redirect(url_for('main.wallets'))

        return render_template('add_wallet.html', currencies=CURRENCIES)

    @main.route('/wallets/edit/<int:id>', methods=['GET', 'POST'])
    @login_required
    def edit_wallet(id):
        from .currencies import CURRENCIES
        wallet = Wallet.query.filter_by(id=id, user_id=current_user.id).first_or_404()

        if request.method == 'POST':
            wallet.name = request.form.get('name')
            wallet.balance = float(request.form.get('balance', 0))
            wallet.currency = request.form.get('currency', 'GHS')
            wallet.icon = request.form.get('icon', '\U0001f4b0')
            wallet.wallet_type = request.form.get('wallet_type', 'cash')
            wallet.account_number = request.form.get('account_number')
            wallet.is_shared = request.form.get('is_shared') == 'on'

            db.session.commit()
            flash('Wallet updated successfully!', 'success')
            return redirect(url_for('main.wallets') + f'#wallet-{id}')

        return render_template('edit_wallet.html', wallet=wallet, currencies=CURRENCIES)

    @main.route('/wallets/delete/<int:id>', methods=['POST'])
    @login_required
    def delete_wallet(id):
        wallet = Wallet.query.filter_by(id=id, user_id=current_user.id).first_or_404()

        # Check if wallet has transactions
        expense_count = Expense.query.filter_by(wallet_id=id).count()
        if expense_count > 0:
            flash(f'Cannot delete wallet with {expense_count} transaction(s). Please reassign or delete transactions first.', 'error')
            return redirect(url_for('main.wallets'))

        db.session.delete(wallet)
        db.session.commit()
        flash('Wallet deleted successfully!', 'success')
        return redirect(url_for('main.wallets'))

    @main.route('/wallets/transfer', methods=['POST'])
    @login_required
    def transfer_funds():
        try:
            source_wallet_id = int(request.form.get('source_wallet_id', ''))
            dest_wallet_id = int(request.form.get('dest_wallet_id', ''))
            amount = float(request.form.get('amount', ''))
            exchange_rate = float(request.form.get('exchange_rate', 1.0))
        except (TypeError, ValueError):
            flash('Please complete the transfer form with valid values.', 'error')
            return redirect(url_for('main.wallets'))

        date_str = request.form.get('date')
        reason = request.form.get('reason', '').strip()

        if source_wallet_id == dest_wallet_id:
            flash('Cannot transfer to the same wallet!', 'error')
            return redirect(url_for('main.wallets'))

        if amount <= 0:
            flash('Transfer amount must be greater than 0!', 'error')
            return redirect(url_for('main.wallets'))

        if exchange_rate <= 0:
            flash('Exchange rate must be greater than 0.', 'error')
            return redirect(url_for('main.wallets'))

        source_wallet = Wallet.query.filter_by(id=source_wallet_id, user_id=current_user.id).first_or_404()
        dest_wallet = Wallet.query.filter_by(id=dest_wallet_id, user_id=current_user.id).first_or_404()

        if amount > float(source_wallet.balance):
            flash(f'Insufficient balance in {source_wallet.name}.', 'error')
            return redirect(url_for('main.wallets'))

        # Calculate destination amount based on exchange rate
        dest_amount = amount * exchange_rate

        # Get or create Transfer category for the current user
        transfer_category = Category.query.filter_by(name='Transfer', user_id=current_user.id).first()
        if not transfer_category:
            transfer_category = Category(name='Transfer', icon='\u2194\ufe0f', user_id=current_user.id)
            db.session.add(transfer_category)
            db.session.commit()

        if date_str:
            try:
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            except ValueError:
                flash('Please select a valid transfer date.', 'error')
                return redirect(url_for('main.wallets'))
        else:
            date_obj = datetime.utcnow()

        # Create Expense for Source Wallet
        expense = Expense(
            user_id=current_user.id,
            amount=amount,
            description=f"Transfer to {dest_wallet.name}" + (f": {reason}" if reason else "") + (f" (Rate: {exchange_rate})" if exchange_rate != 1.0 else ""),
            category_id=transfer_category.id,
            wallet_id=source_wallet.id,
            date=date_obj,
            transaction_type='transfer_out',
            tags='transfer,outgoing'
        )

        # Create Income for Destination Wallet
        income = Expense(
            user_id=current_user.id,
            amount=dest_amount,
            description=f"Transfer from {source_wallet.name}" + (f": {reason}" if reason else "") + (f" (Rate: {exchange_rate})" if exchange_rate != 1.0 else ""),
            category_id=transfer_category.id,
            wallet_id=dest_wallet.id,
            date=date_obj,
            transaction_type='transfer_in',
            tags='transfer,incoming'
        )

        db.session.add(expense)
        db.session.add(income)

        # Update balances
        source_wallet.balance = float(source_wallet.balance) - amount
        dest_wallet.balance = float(dest_wallet.balance) + dest_amount

        db.session.commit()

        flash('Funds transferred successfully!', 'success')
        return redirect(url_for('main.wallets'))

    @main.route('/wallets/<int:id>/activity')
    @login_required
    def wallet_activity(id):
        wallet = Wallet.query.get_or_404(id)

        # Access control: user is owner or has accepted share
        is_owner = (wallet.user_id == current_user.id)
        share = WalletShare.query.filter_by(wallet_id=id, shared_with_id=current_user.id, accepted=True).first()

        if not is_owner and not share:
            flash("You do not have permission to view this wallet's activity.", "error")
            return redirect(url_for('main.wallets'))

        search_query = request.args.get('search', '').strip()
        category_filter = request.args.get('category', '').strip()
        type_filter = request.args.get('type', '').strip()
        date_from = request.args.get('from', '').strip()
        date_to = request.args.get('to', '').strip()
        sort_by = request.args.get('sort', 'date')
        sort_order = request.args.get('order', 'desc')

        query = Expense.query.filter_by(wallet_id=wallet.id)

        if search_query:
            query = query.filter(or_(
                Expense.description.contains(search_query),
                Expense.income_source.contains(search_query),
                Expense.project_type.contains(search_query),
                Expense.notes.contains(search_query),
                Expense.tags.contains(search_query)
            ))

        if category_filter:
            try:
                cat_id = int(category_filter)
                query = query.filter_by(category_id=cat_id)
            except ValueError:
                pass

        if type_filter:
            if type_filter == 'transfer':
                query = query.filter(Expense.transaction_type.in_(['transfer', 'transfer_out', 'transfer_in']))
            elif type_filter == 'inflow':
                query = query.filter(Expense.transaction_type.in_(['income', 'transfer_in', 'liability']))
            elif type_filter == 'outflow':
                query = query.filter(Expense.transaction_type.in_(['expense', 'transfer_out']))
            else:
                query = query.filter_by(transaction_type=type_filter)

        if date_from:
            try:
                query = query.filter(Expense.date >= datetime.strptime(date_from, '%Y-%m-%d'))
            except ValueError:
                pass

        if date_to:
            try:
                query = query.filter(Expense.date < datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1))
            except ValueError:
                pass

        # Sorting
        if sort_by == 'date':
            query = query.order_by(Expense.date.asc() if sort_order == 'asc' else Expense.date.desc())
        elif sort_by == 'description':
            query = query.order_by(Expense.description.asc() if sort_order == 'asc' else Expense.description.desc())
        elif sort_by == 'category':
            query = query.join(Category).order_by(Category.name.asc() if sort_order == 'asc' else Category.name.desc())
        elif sort_by == 'amount':
            query = query.order_by(Expense.amount.asc() if sort_order == 'asc' else Expense.amount.desc())
        else:
            query = query.order_by(Expense.date.desc())

        query = query.options(
            joinedload(Expense.category),
            joinedload(Expense.wallet)
        )
        expenses = query.all()

        # Handle CSV export for this specific wallet
        if request.args.get('export') == 'csv':
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['Date', 'Description', 'Category', 'Amount', 'Currency', 'Type', 'Tags', 'Notes', 'Income Source'])
            for exp in expenses:
                writer.writerow([
                    exp.date.strftime('%Y-%m-%d') if exp.date else '',
                    exp.description,
                    exp.category.name if exp.category else '',
                    exp.amount,
                    wallet.currency,
                    exp.transaction_type,
                    exp.tags or '',
                    exp.notes or '',
                    exp.income_source or ''
                ])
            output.seek(0)
            safe_name = wallet.name.replace(" ", "_").lower()
            return Response(
                output.getvalue(),
                mimetype='text/csv',
                headers={'Content-Disposition': f'attachment; filename=wallet_{safe_name}_activity.csv'}
            )

        # Lifetime wallet stats
        all_wallet_expenses = Expense.query.filter_by(wallet_id=wallet.id).all()
        total_inflow = sum(e.amount for e in all_wallet_expenses if e.transaction_type in ['income', 'transfer_in', 'liability'])
        total_outflow = sum(e.amount for e in all_wallet_expenses if e.transaction_type in ['expense', 'transfer_out'])
        net_flow = total_inflow - total_outflow
        total_tx_count = len(all_wallet_expenses)

        # Filtered stats
        filtered_inflow = sum(e.amount for e in expenses if e.transaction_type in ['income', 'transfer_in', 'liability'])
        filtered_outflow = sum(e.amount for e in expenses if e.transaction_type in ['expense', 'transfer_out'])
        filtered_net = filtered_inflow - filtered_outflow

        # Categories for filter dropdown (user's categories + wallet owner's categories if shared)
        categories = Category.query.filter_by(user_id=wallet.user_id).order_by(Category.name.asc()).all()

        # AJAX live search response
        if request.args.get('ajax') == '1':
            html = render_template('_partials/expense_rows.html', expenses=expenses)
            return jsonify({
                'html': html,
                'count': len(expenses),
                'filtered_inflow': f"{wallet.currency} {filtered_inflow:,.2f}",
                'filtered_outflow': f"{wallet.currency} {filtered_outflow:,.2f}",
                'filtered_net': f"{wallet.currency} {filtered_net:,.2f}"
            })

        return render_template(
            'wallet_activity.html',
            wallet=wallet,
            expenses=expenses,
            categories=categories,
            is_owner=is_owner,
            share=share,
            stats={
                'total_inflow': total_inflow,
                'total_outflow': total_outflow,
                'net_flow': net_flow,
                'total_tx_count': total_tx_count,
                'filtered_inflow': filtered_inflow,
                'filtered_outflow': filtered_outflow,
                'filtered_net': filtered_net,
                'filtered_count': len(expenses)
            },
            filters={
                'search': search_query,
                'category': category_filter,
                'type': type_filter,
                'from': date_from,
                'to': date_to,
                'sort': sort_by,
                'order': sort_order
            }
        )

