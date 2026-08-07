from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from . import db
from .models import Expense, Category, Wallet, Creditor, DebtPayment
from datetime import datetime
from sqlalchemy import func, or_
from .utils import apply_transaction_to_wallet


def _safe_return_url(default_endpoint='main.creditors'):
    next_url = request.form.get('next') or request.args.get('next')
    if next_url and next_url.startswith('/'):
        return next_url
    return url_for(default_endpoint)


def _creditor_for_current_user_or_404(creditor_id):
    return Creditor.query.filter_by(id=creditor_id, user_id=current_user.id).first_or_404()


def _creditor_transactions(creditor):
    """Return only transactions that are explicitly tied to this creditor."""
    return Expense.query.filter(
        Expense.user_id == creditor.user_id,
        or_(
            Expense.creditor_id == creditor.id,
            Expense.notes == f'Creditor ID: {creditor.id}',
        )
    ).all()


def _parse_due_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d')
    except (TypeError, ValueError):
        return None


def _build_creditor_totals(creditors):
    grouped = {}

    for creditor in creditors:
        name = (creditor.name or 'Unnamed Creditor').strip() or 'Unnamed Creditor'
        currency = creditor.currency or 'GHS'
        key = (name.casefold(), currency)
        original_amount = creditor.original_amount if creditor.original_amount and creditor.original_amount > 0 else creditor.amount

        if key not in grouped:
            grouped[key] = {
                'name': name,
                'currency': currency,
                'account_count': 0,
                'outstanding_total': 0.0,
                'original_total': 0.0,
                'minimum_payment_total': 0.0,
                'overdue_count': 0,
                'paid_off_count': 0,
            }

        summary = grouped[key]
        summary['account_count'] += 1
        summary['outstanding_total'] += creditor.amount or 0
        summary['original_total'] += original_amount or 0
        summary['minimum_payment_total'] += creditor.minimum_payment or 0
        if creditor.computed_status == 'overdue':
            summary['overdue_count'] += 1
        elif creditor.computed_status == 'paid_off':
            summary['paid_off_count'] += 1

    summaries = []
    for summary in grouped.values():
        summary['paid_total'] = max(summary['original_total'] - summary['outstanding_total'], 0)
        if summary['original_total'] > 0:
            summary['progress_percent'] = min(round((summary['paid_total'] / summary['original_total']) * 100, 1), 100)
        else:
            summary['progress_percent'] = 0
        summaries.append(summary)

    return sorted(summaries, key=lambda item: item['outstanding_total'], reverse=True)


def register_routes(main):

    @main.route('/creditors')
    @login_required
    def creditors():
        all_creditors = Creditor.query.filter_by(user_id=current_user.id).order_by(Creditor.amount.desc()).all()
        wallets = Wallet.query.filter_by(user_id=current_user.id).order_by(Wallet.balance.desc()).all()

        # KPI calculations
        now = datetime.utcnow()
        month_start = datetime(now.year, now.month, 1)

        active_debts = [c for c in all_creditors if c.computed_status == 'active']
        overdue_debts = [c for c in all_creditors if c.computed_status == 'overdue']
        paid_off_debts = [c for c in all_creditors if c.computed_status == 'paid_off']
        total_debt = sum(c.amount for c in all_creditors if c.computed_status != 'paid_off')
        monthly_due = sum(c.minimum_payment or 0 for c in active_debts + overdue_debts)
        est_monthly_interest = sum((c.amount * (c.interest_rate or 0) / 100 / 12) for c in active_debts + overdue_debts)

        paid_this_month = db.session.query(func.sum(DebtPayment.amount)).join(Creditor).filter(
            Creditor.user_id == current_user.id,
            DebtPayment.date >= month_start
        ).scalar() or 0

        # Filters
        type_filter = request.args.get('type', 'all')
        status_filter = request.args.get('status', 'all')
        sort_by = request.args.get('sort', 'amount_desc')

        filtered = all_creditors
        if type_filter != 'all':
            filtered = [c for c in filtered if c.debt_type == type_filter]
        if status_filter != 'all':
            filtered = [c for c in filtered if c.computed_status == status_filter]

        if sort_by == 'amount_asc':
            filtered.sort(key=lambda c: c.amount)
        elif sort_by == 'amount_desc':
            filtered.sort(key=lambda c: c.amount, reverse=True)
        elif sort_by == 'due_date':
            filtered.sort(key=lambda c: (c.due_date or datetime(9999, 1, 1)))
        elif sort_by == 'priority':
            filtered.sort(key=lambda c: (c.priority or 3))
        elif sort_by == 'recent':
            filtered.sort(key=lambda c: c.created_at, reverse=True)

        creditor_totals = _build_creditor_totals(filtered)

        # Fetch payment history
        payment_history = Expense.query.filter(
            Expense.user_id == current_user.id,
            Expense.tags.like('%debt_payment%')
        ).order_by(Expense.date.desc()).limit(30).all()

        return render_template(
            'creditors.html',
            creditors=filtered,
            creditor_totals=creditor_totals,
            wallets=wallets,
            total_debt=total_debt,
            active_count=len(active_debts),
            overdue_count=len(overdue_debts),
            paid_off_count=len(paid_off_debts),
            monthly_due=monthly_due,
            paid_this_month=paid_this_month,
            est_monthly_interest=est_monthly_interest,
            payment_history=payment_history,
            now_date=datetime.utcnow().strftime('%Y-%m-%d'),
            type_filter=type_filter,
            status_filter=status_filter,
            sort_by=sort_by
        )

    @main.route('/creditors/add', methods=['GET', 'POST'])
    @login_required
    def add_creditor():
        if request.method == 'POST':
            name = (request.form.get('name') or '').strip()
            if not name:
                flash('Debt name is required.', 'error')
                return redirect(_safe_return_url())

            try:
                amount = float(request.form.get('amount', 0))
            except (TypeError, ValueError):
                flash('Please provide a valid amount.', 'error')
                return redirect(_safe_return_url())

            if amount <= 0:
                flash('Amount owed must be greater than 0.', 'error')
                return redirect(_safe_return_url())

            currency = (request.form.get('currency') or 'GHS').upper().strip()[:10] or 'GHS'
            description = (request.form.get('description') or '').strip() or None
            debt_type = (request.form.get('debt_type') or 'Personal Loan').strip() or 'Personal Loan'

            try:
                interest_rate = max(float(request.form.get('interest_rate', 0) or 0), 0)
            except (TypeError, ValueError):
                flash('Interest rate must be a number.', 'error')
                return redirect(_safe_return_url())

            original_amount_raw = request.form.get('original_amount')
            if original_amount_raw:
                try:
                    original_amount = float(original_amount_raw)
                except (TypeError, ValueError):
                    flash('Original amount must be a number.', 'error')
                    return redirect(_safe_return_url())
                if original_amount <= 0:
                    flash('Original amount must be greater than 0.', 'error')
                    return redirect(_safe_return_url())
                original_amount = max(original_amount, amount)
            else:
                original_amount = amount

            due_date = _parse_due_date(request.form.get('due_date'))
            if request.form.get('due_date') and not due_date:
                flash('Invalid due date provided.', 'error')
                return redirect(_safe_return_url())

            payment_frequency = (request.form.get('payment_frequency') or '').strip() or None
            try:
                minimum_payment = max(float(request.form.get('minimum_payment', 0) or 0), 0)
            except (TypeError, ValueError):
                minimum_payment = 0.0
            contact_info = (request.form.get('contact_info') or '').strip() or None
            try:
                priority = int(request.form.get('priority', 3) or 3)
                priority = max(1, min(4, priority))
            except (TypeError, ValueError):
                priority = 3
            notes = (request.form.get('notes') or '').strip() or None
            created_at = _parse_due_date(request.form.get('date')) or datetime.utcnow()

            creditor = Creditor(
                user_id=current_user.id,
                name=name,
                amount=amount,
                currency=currency,
                description=description,
                debt_type=debt_type,
                interest_rate=interest_rate,
                original_amount=original_amount,
                due_date=due_date,
                created_at=created_at,
                payment_frequency=payment_frequency,
                minimum_payment=minimum_payment,
                contact_info=contact_info,
                priority=priority,
                notes=notes
            )
            db.session.add(creditor)
            # The transaction needs a durable reference to this new creditor.
            db.session.flush()

            # Handle wallet balance update if a wallet was selected
            wallet_id = request.form.get('wallet_id')
            if wallet_id:
                try:
                    wallet_id = int(wallet_id)
                    wallet = Wallet.query.filter_by(id=wallet_id, user_id=current_user.id).first()
                    if wallet:
                        wallet.balance = float(wallet.balance) + amount

                        # Ensure a 'Loan Received' category exists
                        loan_cat = Category.query.filter_by(name='Loan Received', user_id=current_user.id).first()
                        if not loan_cat:
                            loan_cat = Category(name='Loan Received', icon='\U0001f4e5', is_custom=True, user_id=current_user.id)
                            db.session.add(loan_cat)
                            db.session.flush()

                        # Record as liability (NOT income) — this is borrowed money
                        income_expense = Expense(
                            user_id=current_user.id,
                            amount=amount,
                            description=description or f"Loan from {name}",
                            category_id=loan_cat.id,
                            wallet_id=wallet.id,
                            date=created_at,
                            transaction_type='liability',
                            tags='loan_received',
                            notes=f"Creditor ID: {creditor.id}",
                            creditor_id=creditor.id
                        )
                        db.session.add(income_expense)
                        flash(f'Added GHS {amount:.2f} to {wallet.name}.', 'success')
                except (TypeError, ValueError):
                    pass

            db.session.commit()
            flash('Debt added successfully!', 'success')
            return redirect(_safe_return_url())

        return redirect(url_for('main.creditors'))

    @main.route('/creditors/edit/<int:id>', methods=['GET', 'POST'])
    @main.route('/creditor/edit/<int:id>', methods=['GET', 'POST']) # Singular alias
    @login_required
    def edit_creditor(id):
        if request.method == 'GET':
            return redirect(url_for('main.creditors') + f'#creditor-{id}')
        
        creditor = _creditor_for_current_user_or_404(id)

        name = (request.form.get('name') or '').strip()
        if not name:
            flash('Debt name is required.', 'error')
            return redirect(_safe_return_url() + f'#creditor-{id}')

        try:
            amount = float(request.form.get('amount', creditor.amount))
        except (TypeError, ValueError):
            flash('Please provide a valid amount.', 'error')
            return redirect(_safe_return_url() + f'#creditor-{id}')

        if amount < 0:
            flash('Amount owed cannot be negative.', 'error')
            return redirect(_safe_return_url() + f'#creditor-{id}')

        try:
            interest_rate = max(float(request.form.get('interest_rate', creditor.interest_rate or 0) or 0), 0)
        except (TypeError, ValueError):
            flash('Interest rate must be a number.', 'error')
            return redirect(_safe_return_url() + f'#creditor-{id}')

        original_amount_raw = request.form.get('original_amount')
        if original_amount_raw:
            try:
                original_amount = float(original_amount_raw)
            except (TypeError, ValueError):
                flash('Original amount must be a number.', 'error')
                return redirect(_safe_return_url() + f'#creditor-{id}')
            if original_amount <= 0:
                flash('Original amount must be greater than 0.', 'error')
                return redirect(_safe_return_url() + f'#creditor-{id}')
            original_amount = max(original_amount, amount)
        else:
            existing_original = creditor.original_amount if creditor.original_amount and creditor.original_amount > 0 else amount
            original_amount = max(existing_original, amount)

        due_date = _parse_due_date(request.form.get('due_date'))
        if request.form.get('due_date') and not due_date:
            flash('Invalid due date provided.', 'error')
            return redirect(_safe_return_url() + f'#creditor-{id}')

        creditor.name = name
        creditor.amount = amount
        creditor.currency = (request.form.get('currency') or creditor.currency or 'GHS').upper().strip()[:10] or 'GHS'
        creditor.description = (request.form.get('description') or '').strip() or None
        creditor.debt_type = (request.form.get('debt_type') or creditor.debt_type or 'Personal Loan').strip()
        creditor.interest_rate = interest_rate
        creditor.original_amount = original_amount
        creditor.due_date = due_date if request.form.get('due_date') else None
        creditor.payment_frequency = (request.form.get('payment_frequency') or '').strip() or None
        try:
            creditor.minimum_payment = max(float(request.form.get('minimum_payment', creditor.minimum_payment or 0) or 0), 0)
        except (TypeError, ValueError):
            pass
        creditor.contact_info = (request.form.get('contact_info') or '').strip() or None
        try:
            p = int(request.form.get('priority', creditor.priority or 3) or 3)
            creditor.priority = max(1, min(4, p))
        except (TypeError, ValueError):
            pass
        creditor.notes = (request.form.get('notes') or '').strip() or None

        # Update creation date if provided
        new_created_at = _parse_due_date(request.form.get('date'))
        if new_created_at:
            creditor.created_at = new_created_at

        # The optional "Receive in Wallet" action creates a liability transaction.
        # Keep that transaction and its wallet balance in sync with the original
        # borrowed amount rather than leaving a stale row on the transactions page.
        for transaction in _creditor_transactions(creditor):
            if not transaction.tags or 'loan_received' not in transaction.tags.split(','):
                continue
            previous_amount = transaction.amount
            transaction.amount = original_amount
            transaction.description = creditor.description or f"Loan from {creditor.name}"
            transaction.transaction_type = 'liability'
            transaction.notes = f"Creditor ID: {creditor.id}"
            transaction.creditor_id = creditor.id
            transaction.date = creditor.created_at
            wallet = Wallet.query.filter_by(id=transaction.wallet_id, user_id=current_user.id).first()
            if wallet:
                # Loan receipts have always credited the wallet directly, even
                # for legacy rows whose stored type was incorrectly "expense".
                apply_transaction_to_wallet(wallet, 'liability', previous_amount, reverse=True)
                apply_transaction_to_wallet(wallet, 'liability', transaction.amount)

        db.session.commit()
        flash('Debt updated successfully!', 'success')
        return redirect(_safe_return_url() + f'#creditor-{id}')

    @main.route('/creditors/delete/<int:id>', methods=['POST'])
    @login_required
    def delete_creditor(id):
        creditor = _creditor_for_current_user_or_404(id)
        # Remove the linked transaction rows and reverse their wallet effects.
        # Without this, the wallet and main transactions page keep ghost data.
        for transaction in _creditor_transactions(creditor):
            wallet = Wallet.query.filter_by(id=transaction.wallet_id, user_id=current_user.id).first()
            if wallet:
                apply_transaction_to_wallet(wallet, transaction.transaction_type, transaction.amount, reverse=True)
            db.session.delete(transaction)
        db.session.delete(creditor)
        db.session.commit()
        flash('Debt removed successfully!', 'success')
        return redirect(_safe_return_url())

    @main.route('/creditors/pay/<int:id>', methods=['GET', 'POST'])
    @main.route('/creditor/pay/<int:id>', methods=['GET', 'POST']) # Singular alias
    @login_required
    def pay_creditor(id):
        if request.method == 'GET':
            return redirect(url_for('main.creditors') + f'#creditor-{id}')
            
        creditor = _creditor_for_current_user_or_404(id)

        try:
            wallet_id = int(request.form.get('wallet_id'))
        except (TypeError, ValueError):
            flash('Please select a valid wallet.', 'error')
            return redirect(_safe_return_url())

        wallet = Wallet.query.filter_by(id=wallet_id, user_id=current_user.id).first()
        if not wallet:
            flash('Selected wallet is not available.', 'error')
            return redirect(_safe_return_url())

        try:
            amount = float(request.form.get('amount'))
        except (TypeError, ValueError):
            flash('Please provide a valid payment amount.', 'error')
            return redirect(_safe_return_url())

        payment_date = _parse_due_date(request.form.get('date')) or datetime.utcnow()

        if amount <= 0:
            flash('Payment amount must be positive.', 'error')
            return redirect(_safe_return_url())

        if amount > float(wallet.balance):
            flash(f'Insufficient balance in {wallet.name}.', 'error')
            return redirect(_safe_return_url())

        if amount > creditor.amount:
            flash('Payment amount cannot exceed remaining debt.', 'error')
            return redirect(_safe_return_url())

        apply_transaction_to_wallet(wallet, 'expense', amount)
        creditor.amount = max(creditor.amount - amount, 0)
        if creditor.amount <= 0:
            creditor.status = 'paid_off'

        debt_cat = Category.query.filter_by(name='Debt Payment', user_id=current_user.id).first()
        if not debt_cat:
            debt_cat = Category(name='Debt Payment', icon='$', is_custom=True, user_id=current_user.id)
            db.session.add(debt_cat)
            db.session.flush()

        expense = Expense(
            user_id=current_user.id,
            amount=amount,
            description=f"Payment to {creditor.name}",
            category_id=debt_cat.id,
            wallet_id=wallet.id,
            date=payment_date,
            transaction_type='expense',
            tags='debt_payment',
            creditor_id=creditor.id
        )

        debt_payment = DebtPayment(
            user_id=current_user.id,
            creditor_id=creditor.id,
            amount=amount,
            date=payment_date,
            notes=(request.form.get('notes') or '').strip() or None
        )

        db.session.add(expense)
        db.session.flush()
        debt_payment.expense_id = expense.id
        db.session.add(debt_payment)
        db.session.commit()

        flash(f'Paid {wallet.currency} {amount:.2f} to {creditor.name}!', 'success')
        return redirect(_safe_return_url())
