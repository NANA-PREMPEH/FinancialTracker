import sys

file_path = "app/routes.py"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Make sure models are imported at the top-ish or when needed
if "from .models import " in content and "Debtor," not in content:
    # We will just ensure Debtor is imported within the routes as needed. Creditors is already imported at the top globally usually, let's check.
    pass

debtors_routes = """
# ===== DEBTORS =====
def _safe_return_url_debtors(default_endpoint='main.debtors'):
    return request.referrer or url_for(default_endpoint)

def _debtor_for_current_user_or_404(debtor_id):
    from .models import Debtor
    debtor = Debtor.query.filter_by(id=debtor_id, user_id=current_user.id).first()
    if not debtor:
        from werkzeug.exceptions import abort
        abort(404)
    return debtor

@main.route('/debtors')
@login_required
def debtors():
    from .models import Debtor, Wallet, Expense
    all_debtors = Debtor.query.filter_by(user_id=current_user.id).order_by(Debtor.amount.desc()).all()
    wallets = Wallet.query.filter_by(user_id=current_user.id).order_by(Wallet.balance.desc()).all()

    # KPI calculations
    now = datetime.utcnow()
    month_start = datetime(now.year, now.month, 1)

    active_debts = [d for d in all_debtors if d.computed_status == 'active']
    overdue_debts = [d for d in all_debtors if d.computed_status == 'overdue']
    paid_off_debts = [d for d in all_debtors if d.computed_status == 'paid_off']
    total_expected = sum(d.amount for d in all_debtors if d.computed_status != 'paid_off')
    monthly_expected = sum(d.minimum_payment or 0 for d in active_debts + overdue_debts)

    from .models import DebtorPayment
    collected_this_month = db.session.query(func.sum(DebtorPayment.amount)).join(Debtor).filter(
        Debtor.user_id == current_user.id,
        DebtorPayment.date >= month_start
    ).scalar() or 0

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
        sort_by=sort_by
    )

@main.route('/debtors/add', methods=['GET', 'POST'])
@login_required
def add_debtor():
    from .models import Debtor
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
            payment_frequency=payment_frequency,
            minimum_payment=minimum_payment,
            contact_info=contact_info,
            priority=priority,
            notes=notes
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
    from .models import Wallet, Category, Expense, DebtorPayment
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
        coll_cat = Category(name='Debt Collection', icon='💵', is_custom=True, user_id=current_user.id)
        db.session.add(coll_cat)
        db.session.flush()

    # Log as income instead of expense
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

"""

if "# ===== DEBTORS =====" not in content:
    # insert before EXPORT
    export_index = content.find("# ===== EXPORT =====")
    if export_index != -1:
        new_content = content[:export_index] + debtors_routes + "\n" + content[export_index:]
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print("Success")
    else:
        print("Could not find insertion point")
else:
    print("Already inserted")
