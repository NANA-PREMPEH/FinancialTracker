from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from . import db
from .models import Expense, Category, Wallet, Debtor, DebtorPayment
from datetime import datetime
from sqlalchemy import func, or_


def _safe_return_url_debtors(default_endpoint='main.debtors'):
    return request.referrer or url_for(default_endpoint)


def _debtor_for_current_user_or_404(debtor_id):
    debtor = Debtor.query.filter_by(id=debtor_id, user_id=current_user.id).first()
    if not debtor:
        from werkzeug.exceptions import abort
        abort(404)
    return debtor


def _parse_due_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d')
    except (TypeError, ValueError):
        return None


def register_routes(main):

    @main.route('/debtors')
    @login_required
    def debtors():
        all_debtors = Debtor.query.filter_by(user_id=current_user.id).order_by(Debtor.amount.desc()).all()
        wallets = Wallet.query.filter_by(user_id=current_user.id).order_by(Wallet.balance.desc()).all()

        # KPI calculations
        now = datetime.utcnow()
        month_start = datetime(now.year, now.month, 1)

        active_debts = [d for d in all_debtors if d.computed_status == 'active']
        overdue_debts = [d for d in all_debtors if d.computed_status == 'overdue']
        paid_off_debts = [d for d in all_debtors if d.computed_status == 'paid_off']
        total_expected = sum(d.amount for d in all_debtors if d.computed_status not in ('paid_off', 'bad_debt'))
        monthly_expected = sum(d.minimum_payment or 0 for d in active_debts + overdue_debts)

        collected_this_month = db.session.query(func.sum(DebtorPayment.amount)).join(Debtor).filter(
            Debtor.user_id == current_user.id,
            DebtorPayment.date >= month_start
        ).scalar() or 0

        # Bad debt stats
        bad_debt_debtors = [d for d in all_debtors if d.computed_status == 'bad_debt']
        bad_debt_count = len(bad_debt_debtors)
        total_bad_debt = db.session.query(func.sum(Expense.amount)).filter(
            Expense.user_id == current_user.id,
            Expense.tags.like('%bad_debt%'),
            ~Expense.tags.like('%bad_debt_recovery%')
        ).scalar() or 0
        total_recovered = db.session.query(func.sum(Expense.amount)).filter(
            Expense.user_id == current_user.id,
            Expense.tags.like('%bad_debt_recovery%')
        ).scalar() or 0

        categories = Category.query.filter_by(user_id=current_user.id).order_by(Category.name).all()

        # Filters
        type_filter = request.args.get('type', 'all')
        status_filter = request.args.get('status', 'all')
        sort_by = request.args.get('sort', 'amount_desc')

        filtered = all_debtors
        if type_filter != 'all':
            filtered = [d for d in filtered if d.debt_type == type_filter]
        if status_filter != 'all':
            filtered = [d for d in filtered if d.computed_status == status_filter]

        if sort_by == 'amount_asc':
            filtered.sort(key=lambda d: d.amount)
        elif sort_by == 'amount_desc':
            filtered.sort(key=lambda d: d.amount, reverse=True)
        elif sort_by == 'due_date':
            filtered.sort(key=lambda d: (d.due_date or datetime(9999, 1, 1)))
        elif sort_by == 'priority':
            filtered.sort(key=lambda d: (d.priority or 3))
        elif sort_by == 'recent':
            filtered.sort(key=lambda d: d.created_at, reverse=True)

        # Fetch collection history
        collection_history = Expense.query.filter(
            Expense.user_id == current_user.id,
            Expense.tags.like('%debt_collection%')
        ).order_by(Expense.date.desc()).limit(30).all()

        return render_template(
            'debtors.html',
            debtors=filtered,
            wallets=wallets,
            total_expected=total_expected,
            active_count=len(active_debts),
            overdue_count=len(overdue_debts),
            paid_off_count=len(paid_off_debts),
            monthly_expected=monthly_expected,
            collected_this_month=collected_this_month,
            collection_history=collection_history,
            now_date=datetime.utcnow().strftime('%Y-%m-%d'),
            type_filter=type_filter,
            status_filter=status_filter,
            sort_by=sort_by,
            bad_debt_count=bad_debt_count,
            total_bad_debt=total_bad_debt,
            total_recovered=total_recovered,
            categories=categories
        )

    @main.route('/debtors/add', methods=['GET', 'POST'])
    @login_required
    def add_debtor():
        if request.method == 'POST':
            name = (request.form.get('name') or '').strip()
            if not name:
                flash('Debtor name is required.', 'error')
                return redirect(_safe_return_url_debtors())

            try:
                amount = float(request.form.get('amount', 0))
            except (TypeError, ValueError):
                flash('Please provide a valid amount.', 'error')
                return redirect(_safe_return_url_debtors())

            if amount <= 0:
                flash('Amount owed must be greater than 0.', 'error')
                return redirect(_safe_return_url_debtors())

            try:
                wallet_id = int(request.form.get('wallet_id'))
            except (TypeError, ValueError):
                flash('Please select a source wallet.', 'error')
                return redirect(_safe_return_url_debtors())

            wallet = Wallet.query.filter_by(id=wallet_id, user_id=current_user.id).first()
            if not wallet:
                flash('Selected wallet is not available.', 'error')
                return redirect(_safe_return_url_debtors())

            if amount > wallet.balance:
                flash(f'Insufficient balance in {wallet.name}.', 'error')
                return redirect(_safe_return_url_debtors())

            currency = (request.form.get('currency') or 'GHS').upper().strip()[:10] or 'GHS'
            description = (request.form.get('description') or '').strip() or None
            debt_type = (request.form.get('debt_type') or 'Money Lent').strip() or 'Money Lent'

            try:
                interest_rate = max(float(request.form.get('interest_rate', 0) or 0), 0)
            except (TypeError, ValueError):
                flash('Interest rate must be a number.', 'error')
                return redirect(_safe_return_url_debtors())

            original_amount_raw = request.form.get('original_amount')
            if original_amount_raw:
                try:
                    original_amount = float(original_amount_raw)
                except (TypeError, ValueError):
                    flash('Original amount must be a number.', 'error')
                    return redirect(_safe_return_url_debtors())
                if original_amount <= 0:
                    flash('Original amount must be greater than 0.', 'error')
                    return redirect(_safe_return_url_debtors())
                original_amount = max(original_amount, amount)
            else:
                original_amount = amount

            due_date = _parse_due_date(request.form.get('due_date'))
            if request.form.get('due_date') and not due_date:
                flash('Invalid due date provided.', 'error')
                return redirect(_safe_return_url_debtors())

            lent_date = _parse_due_date(request.form.get('date')) or datetime.utcnow()

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

            wallet.balance -= amount

            debt_lent_cat = Category.query.filter_by(name='Money Lent', user_id=current_user.id).first()
            if not debt_lent_cat:
                debt_lent_cat = Category(name='Money Lent', icon='\U0001f4b8', is_custom=True, user_id=current_user.id)
                db.session.add(debt_lent_cat)
                db.session.flush()

            expense = Expense(
                user_id=current_user.id,
                amount=amount,
                description=f"Lent to {name}",
                category_id=debt_lent_cat.id,
                wallet_id=wallet.id,
                date=lent_date,
                transaction_type='expense',
                tags='debt_lent',
                notes=notes
            )
            db.session.add(expense)

            debtor = Debtor(
                user_id=current_user.id,
                name=name,
                amount=amount,
                currency=currency,
                description=description,
                debt_type=debt_type,
                interest_rate=interest_rate,
                original_amount=original_amount,
                due_date=due_date,
                created_at=lent_date,
                payment_frequency=payment_frequency,
                minimum_payment=minimum_payment,
                contact_info=contact_info,
                priority=priority,
                notes=notes,
                wallet_id=wallet_id
            )
            db.session.add(debtor)
            db.session.commit()
            flash('Debtor added successfully!', 'success')
            return redirect(_safe_return_url_debtors())

        return redirect(url_for('main.debtors'))

    @main.route('/debtors/edit/<int:id>', methods=['POST'])
    @login_required
    def edit_debtor(id):
        debtor = _debtor_for_current_user_or_404(id)

        name = (request.form.get('name') or '').strip()
        if not name:
            flash('Debtor name is required.', 'error')
            return redirect(_safe_return_url_debtors() + f'#debtor-{id}')

        try:
            amount = float(request.form.get('amount', debtor.amount))
        except (TypeError, ValueError):
            flash('Please provide a valid amount.', 'error')
            return redirect(_safe_return_url_debtors() + f'#debtor-{id}')

        if amount < 0:
            flash('Amount owed cannot be negative.', 'error')
            return redirect(_safe_return_url_debtors() + f'#debtor-{id}')

        try:
            interest_rate = max(float(request.form.get('interest_rate', debtor.interest_rate or 0) or 0), 0)
        except (TypeError, ValueError):
            flash('Interest rate must be a number.', 'error')
            return redirect(_safe_return_url_debtors() + f'#debtor-{id}')

        original_amount_raw = request.form.get('original_amount')
        if original_amount_raw:
            try:
                original_amount = float(original_amount_raw)
            except (TypeError, ValueError):
                flash('Original amount must be a number.', 'error')
                return redirect(_safe_return_url_debtors() + f'#debtor-{id}')
            if original_amount <= 0:
                flash('Original amount must be greater than 0.', 'error')
                return redirect(_safe_return_url_debtors() + f'#debtor-{id}')
            original_amount = max(original_amount, amount)
        else:
            existing_original = debtor.original_amount if debtor.original_amount and debtor.original_amount > 0 else amount
            original_amount = max(existing_original, amount)

        due_date = _parse_due_date(request.form.get('due_date'))
        if request.form.get('due_date') and not due_date:
            flash('Invalid due date provided.', 'error')
            return redirect(_safe_return_url_debtors() + f'#debtor-{id}')

        debtor.name = name
        debtor.amount = amount
        debtor.currency = (request.form.get('currency') or debtor.currency or 'GHS').upper().strip()[:10] or 'GHS'
        debtor.description = (request.form.get('description') or '').strip() or None
        debtor.debt_type = (request.form.get('debt_type') or debtor.debt_type or 'Money Lent').strip()
        debtor.interest_rate = interest_rate
        debtor.original_amount = original_amount
        debtor.due_date = due_date if request.form.get('due_date') else None
        
        # Update creation date if provided
        new_created_at = _parse_due_date(request.form.get('date'))
        if new_created_at:
            debtor.created_at = new_created_at
            
        debtor.payment_frequency = (request.form.get('payment_frequency') or '').strip() or None
        try:
            debtor.minimum_payment = max(float(request.form.get('minimum_payment', debtor.minimum_payment or 0) or 0), 0)
        except (TypeError, ValueError):
            pass
        debtor.contact_info = (request.form.get('contact_info') or '').strip() or None
        try:
            p = int(request.form.get('priority', debtor.priority or 3) or 3)
            debtor.priority = max(1, min(4, p))
        except (TypeError, ValueError):
            pass
        debtor.notes = (request.form.get('notes') or '').strip() or None
        
        try:
            new_wallet_id = int(request.form.get('wallet_id'))
            if new_wallet_id != debtor.wallet_id:
                debtor.wallet_id = new_wallet_id
                # Update the associated expense if it exists
                expense = Expense.query.filter_by(user_id=current_user.id, tags='debt_lent').filter(Expense.description.like(f"%{debtor.name}%")).order_by(Expense.date.desc()).first()
                if expense:
                    expense.wallet_id = new_wallet_id
        except (TypeError, ValueError):
            pass

        db.session.commit()
        flash('Debtor updated successfully!', 'success')
        return redirect(_safe_return_url_debtors() + f'#debtor-{id}')

    @main.route('/debtors/delete/<int:id>', methods=['POST'])
    @login_required
    def delete_debtor(id):
        debtor = _debtor_for_current_user_or_404(id)
        db.session.delete(debtor)
        db.session.commit()
        flash('Debtor removed successfully!', 'success')
        return redirect(_safe_return_url_debtors())

    @main.route('/debtors/collect/<int:id>', methods=['POST'])
    @login_required
    def collect_debtor(id):
        debtor = _debtor_for_current_user_or_404(id)

        try:
            wallet_id = int(request.form.get('wallet_id'))
        except (TypeError, ValueError):
            flash('Please select a valid wallet.', 'error')
            return redirect(_safe_return_url_debtors())

        wallet = Wallet.query.filter_by(id=wallet_id, user_id=current_user.id).first()
        if not wallet:
            flash('Selected wallet is not available.', 'error')
            return redirect(_safe_return_url_debtors())

        try:
            amount = float(request.form.get('amount'))
        except (TypeError, ValueError):
            flash('Please provide a valid collection amount.', 'error')
            return redirect(_safe_return_url_debtors())

        payment_date = _parse_due_date(request.form.get('date')) or datetime.utcnow()

        if amount <= 0:
            flash('Collection amount must be positive.', 'error')
            return redirect(_safe_return_url_debtors())

        if amount > debtor.amount:
            flash('Collection amount cannot exceed remaining expected amount.', 'error')
            return redirect(_safe_return_url_debtors())

        wallet.balance += amount
        debtor.amount = max(debtor.amount - amount, 0)
        if debtor.amount <= 0:
            debtor.status = 'paid_off'

        coll_cat = Category.query.filter_by(name='Debt Collection', user_id=current_user.id).first()
        if not coll_cat:
            coll_cat = Category(name='Debt Collection', icon='\U0001f4b5', is_custom=True, user_id=current_user.id)
            db.session.add(coll_cat)
            db.session.flush()

        income_log = Expense(
            user_id=current_user.id,
            amount=amount,
            description=f"Collection from {debtor.name}",
            category_id=coll_cat.id,
            wallet_id=wallet.id,
            date=payment_date,
            transaction_type='income',
            tags='debt_collection'
        )

        debtor_payment = DebtorPayment(
            user_id=current_user.id,
            debtor_id=debtor.id,
            amount=amount,
            date=payment_date,
            notes=(request.form.get('notes') or '').strip() or None
        )

        db.session.add(income_log)
        db.session.add(debtor_payment)
        db.session.commit()

        flash(f'Collected {wallet.currency} {amount:.2f} from {debtor.name}!', 'success')
        return redirect(_safe_return_url_debtors())

    @main.route('/debtors/bad_debt/<int:id>', methods=['POST'])
    @login_required
    def bad_debt_debtor(id):
        debtor = _debtor_for_current_user_or_404(id)

        if debtor.amount <= 0:
            flash('Debtor has no remaining balance to mark as bad debt.', 'error')
            return redirect(_safe_return_url_debtors())

        try:
            amount = float(request.form.get('amount', debtor.amount))
        except (ValueError, TypeError):
            amount = debtor.amount
        amount = min(amount, debtor.amount)
        if amount <= 0:
            flash('Write-off amount must be positive.', 'error')
            return redirect(_safe_return_url_debtors())

        wallet_id = request.form.get('wallet_id')
        if wallet_id:
            wallet = Wallet.query.filter_by(id=wallet_id, user_id=current_user.id).first()
        else:
            wallet = Wallet.query.filter_by(user_id=current_user.id).first()
        if not wallet:
            flash('You need at least one wallet to record bad debt expenses.', 'error')
            return redirect(_safe_return_url_debtors())

        category_id = request.form.get('category_id')
        if category_id:
            bd_cat = Category.query.filter_by(id=category_id, user_id=current_user.id).first()
        else:
            bd_cat = None
        if not bd_cat:
            bd_cat = Category.query.filter_by(name='Bad Debt', user_id=current_user.id).first()
            if not bd_cat:
                bd_cat = Category(name='Bad Debt', icon='\u26a0\ufe0f', is_custom=True, user_id=current_user.id)
                db.session.add(bd_cat)
                db.session.flush()

        write_off_date = _parse_due_date(request.form.get('date')) or datetime.utcnow()

        expense = Expense(
            user_id=current_user.id,
            amount=amount,
            description=f"Bad Debt Write-off: {debtor.name}",
            category_id=bd_cat.id,
            wallet_id=wallet.id,
            date=write_off_date,
            transaction_type='expense',
            tags='bad_debt'
        )

        debtor.amount = max(debtor.amount - amount, 0)
        if debtor.amount <= 0:
            debtor.status = 'bad_debt'

        db.session.add(expense)
        db.session.commit()

        if debtor.status == 'bad_debt':
            flash(f'Wrote off {wallet.currency} {amount:.2f} for {debtor.name}. Fully written off as bad debt.', 'success')
        else:
            flash(f'Wrote off {wallet.currency} {amount:.2f} for {debtor.name}. Remaining: {wallet.currency} {debtor.amount:.2f}', 'success')
        return redirect(_safe_return_url_debtors())

    @main.route('/debtors/recover/<int:id>', methods=['POST'])
    @login_required
    def recover_bad_debt(id):
        debtor = _debtor_for_current_user_or_404(id)

        if debtor.status != 'bad_debt':
            flash('This debtor is not marked as bad debt.', 'error')
            return redirect(_safe_return_url_debtors())

        try:
            amount = float(request.form.get('amount', 0))
        except (ValueError, TypeError):
            amount = 0
        if amount <= 0:
            flash('Recovery amount must be positive.', 'error')
            return redirect(_safe_return_url_debtors())

        total_written_off = db.session.query(func.sum(Expense.amount)).filter(
            Expense.user_id == current_user.id,
            Expense.tags.like('%bad_debt%'),
            ~Expense.tags.like('%bad_debt_recovery%'),
            Expense.description.like(f'%{debtor.name}%')
        ).scalar() or 0
        total_already_recovered = db.session.query(func.sum(Expense.amount)).filter(
            Expense.user_id == current_user.id,
            Expense.tags.like('%bad_debt_recovery%'),
            Expense.description.like(f'%{debtor.name}%')
        ).scalar() or 0
        max_recoverable = total_written_off - total_already_recovered
        if amount > max_recoverable and max_recoverable > 0:
            amount = max_recoverable

        wallet_id = request.form.get('wallet_id')
        wallet = Wallet.query.filter_by(id=wallet_id, user_id=current_user.id).first() if wallet_id else None
        if not wallet:
            wallet = Wallet.query.filter_by(user_id=current_user.id).first()
        if not wallet:
            flash('You need at least one wallet to record recovery.', 'error')
            return redirect(_safe_return_url_debtors())

        recovery_date = _parse_due_date(request.form.get('date')) or datetime.utcnow()

        rec_cat = Category.query.filter_by(name='Bad Debt Recovery', user_id=current_user.id).first()
        if not rec_cat:
            rec_cat = Category(name='Bad Debt Recovery', icon='\U0001f4b0', is_custom=True, user_id=current_user.id)
            db.session.add(rec_cat)
            db.session.flush()

        wallet.balance += amount

        expense = Expense(
            user_id=current_user.id,
            amount=amount,
            description=f"Bad Debt Recovery: {debtor.name}",
            category_id=rec_cat.id,
            wallet_id=wallet.id,
            date=recovery_date,
            transaction_type='income',
            tags='bad_debt_recovery'
        )
        db.session.add(expense)

        new_total_recovered = total_already_recovered + amount
        if new_total_recovered >= total_written_off and total_written_off > 0:
            debtor.status = 'paid_off'

        db.session.commit()

        flash(f'Recovered {wallet.currency} {amount:.2f} from {debtor.name}!', 'success')
        return redirect(_safe_return_url_debtors())
