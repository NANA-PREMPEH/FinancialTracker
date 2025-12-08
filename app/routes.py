from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file, Response
from . import db
from .models import Expense, Category, Wallet, Budget, RecurringTransaction, ExchangeRate, Project, ProjectItem, ProjectItemPayment, FinancialSummary
from datetime import datetime, timedelta
from sqlalchemy import func, or_
import io
import csv

main = Blueprint('main', __name__)

# ===== DASHBOARD =====
@main.route('/')
def dashboard():
    wallets = Wallet.query.all()
    recent_expenses = Expense.query.order_by(Expense.date.desc()).limit(5).all()
    total_expenses = db.session.query(func.sum(Expense.amount)).filter(Expense.transaction_type == 'expense').scalar() or 0
    total_income = db.session.query(func.sum(Expense.amount)).filter(Expense.transaction_type == 'income').scalar() or 0
    
    # Calculate total wallet balance in GHS
    total_wallet_balance = 0
    for wallet in wallets:
        if wallet.currency == 'GHS':
            total_wallet_balance += wallet.balance
        else:
            # Get exchange rate
            rate = ExchangeRate.query.filter_by(
                from_currency=wallet.currency, 
                to_currency='GHS'
            ).order_by(ExchangeRate.date.desc()).first()
            
            # If rate exists and is recent (e.g., within 24 hours), use it
            # Otherwise fetch new rate
            current_rate = 0
            if rate and (datetime.utcnow() - rate.date).days < 1:
                current_rate = rate.rate
            else:
                try:
                    import requests
                    api_url = f'https://api.exchangerate-api.com/v4/latest/{wallet.currency}'
                    response = requests.get(api_url, timeout=5)
                    if response.status_code == 200:
                        data = response.json()
                        current_rate = data.get('rates', {}).get('GHS', 0)
                        
                        # Save new rate
                        new_rate = ExchangeRate(
                            from_currency=wallet.currency,
                            to_currency='GHS',
                            rate=current_rate
                        )
                        db.session.add(new_rate)
                        db.session.commit()
                except Exception as e:
                    print(f"Error fetching rate for {wallet.currency}: {e}")
                    # Fallback to last known rate if available
                    if rate:
                        current_rate = rate.rate
            
            total_wallet_balance += wallet.balance * current_rate
    
    # Calculate current month's expenses
    now = datetime.utcnow()
    month_start = datetime(now.year, now.month, 1)
    monthly_expenses = db.session.query(func.sum(Expense.amount)).filter(
        Expense.transaction_type == 'expense',
        Expense.date >= month_start
    ).scalar() or 0
    
    # Calculate current year's expenses
    year_start = datetime(now.year, 1, 1)
    yearly_expenses = db.session.query(func.sum(Expense.amount)).filter(
        Expense.transaction_type == 'expense',
        Expense.date >= year_start
    ).scalar() or 0
    
    # Budget alerts
    budgets = Budget.query.filter_by(is_active=True).all()
    budget_alerts = []
    for budget in budgets:
        # Calculate effective start date based on period
        now = datetime.utcnow()
        if budget.period == 'weekly':
            # Start of current week (Monday)
            effective_start = now - timedelta(days=now.weekday())
        elif budget.period == 'monthly':
            # Start of current month
            effective_start = datetime(now.year, now.month, 1)
        elif budget.period == 'yearly':
            # Start of current year
            effective_start = datetime(now.year, 1, 1)
        else:
            effective_start = budget.start_date
        
        spent = db.session.query(func.sum(Expense.amount)).filter(
            Expense.category_id == budget.category_id,
            Expense.transaction_type == 'expense',
            Expense.date >= effective_start
        ).scalar() or 0
        
        percentage = (spent / budget.amount * 100) if budget.amount > 0 else 0
        if percentage >= 100:
            budget_alerts.append({'budget': budget, 'spent': spent, 'percentage': percentage, 'level': 'exceeded'})
        elif percentage >= 90:
            budget_alerts.append({'budget': budget, 'spent': spent, 'percentage': percentage, 'level': '90'})
        elif percentage >= 75:
            budget_alerts.append({'budget': budget, 'spent': spent, 'percentage': percentage, 'level': '75'})
    
    return render_template('dashboard.html', 
                         wallets=wallets,
                         recent_expenses=recent_expenses, 
                         total_expenses=total_expenses,
                         total_income=total_income,
                         monthly_expenses=monthly_expenses,
                         yearly_expenses=yearly_expenses,
                         total_wallet_balance=total_wallet_balance,
                         current_date=now,
                         budget_alerts=budget_alerts)

# ===== TRANSACTIONS =====
@main.route('/add', methods=['GET', 'POST'])
def add_expense():
    categories = Category.query.all()
    wallets = Wallet.query.all()
    
    if request.method == 'POST':
        description = request.form.get('description')
        category_id = int(request.form.get('category'))
        wallet_id = int(request.form.get('wallet', 1))
        date_str = request.form.get('date')
        notes = request.form.get('notes', '')
        tags = request.form.get('tags', '')
        transaction_type = request.form.get('transaction_type', 'expense')
        
        if not description or not description.strip():
            flash('Description is required!', 'error')
            return redirect(url_for('main.add_expense'))
            
        try:
            amount = float(request.form.get('amount'))
            if amount <= 0:
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

        expense = Expense(
            amount=amount, 
            description=description, 
            category_id=category_id,
            wallet_id=wallet_id,
            date=date_obj,
            notes=notes,
            tags=tags,
            receipt_path=receipt_path,
            transaction_type=transaction_type
        )
        db.session.add(expense)
        
        # Update wallet balance
        wallet = Wallet.query.get(wallet_id)
        if transaction_type == 'expense':
            wallet.balance -= amount
        elif transaction_type == 'income':
            wallet.balance += amount
        
        db.session.commit()
        db.session.commit()
        flash('Transaction added successfully!', 'success')
        
        action = request.form.get('action')
        if action == 'save_and_continue':
            return redirect(url_for('main.add_expense'))
        else:
            return redirect(url_for('main.all_expenses'))
    
    return render_template('add_expense.html', categories=categories, wallets=wallets)

@main.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_expense(id):
    expense = Expense.query.get_or_404(id)
    categories = Category.query.all()
    wallets = Wallet.query.all()
    
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
        old_wallet = Wallet.query.get(old_wallet_id)
        new_wallet = Wallet.query.get(expense.wallet_id)
        
        # Reverse old transaction
        if old_type == 'expense':
            old_wallet.balance += old_amount
        elif old_type == 'income':
            old_wallet.balance -= old_amount
            
        # Apply new transaction
        if expense.transaction_type == 'expense':
            new_wallet.balance -= expense.amount
        elif expense.transaction_type == 'income':
            new_wallet.balance += expense.amount
        
        db.session.commit()
        flash('Transaction updated successfully!', 'success')
        return redirect(url_for('main.all_expenses'))
    
    return render_template('edit_expense.html', expense=expense, categories=categories, wallets=wallets)

@main.route('/delete/<int:id>', methods=['POST'])
def delete_expense(id):
    expense = Expense.query.get_or_404(id)
    
    # Update wallet balance
    wallet = Wallet.query.get(expense.wallet_id)
    if expense.transaction_type == 'expense':
        wallet.balance += expense.amount
    elif expense.transaction_type == 'income':
        wallet.balance -= expense.amount
    
    db.session.delete(expense)
    db.session.commit()
    flash('Transaction deleted successfully!', 'success')
    return redirect(url_for('main.all_expenses'))

@main.route('/expenses')
def all_expenses():
    # Search and filter
    search_query = request.args.get('search', '')
    category_filter = request.args.get('category', '')
    wallet_filter = request.args.get('wallet', '')
    type_filter = request.args.get('type', '')
    date_from = request.args.get('from', '')
    date_to = request.args.get('to', '')
    
    query = Expense.query
    
    if search_query:
        query = query.filter(or_(
            Expense.description.contains(search_query),
            Expense.notes.contains(search_query),
            Expense.tags.contains(search_query)
        ))
    
    if category_filter:
        query = query.filter_by(category_id=int(category_filter))
    
    if wallet_filter:
        query = query.filter_by(wallet_id=int(wallet_filter))
    
    if type_filter:
        query = query.filter_by(transaction_type=type_filter)
    
    if date_from:
        query = query.filter(Expense.date >= datetime.strptime(date_from, '%Y-%m-%d'))
    
    if date_to:
        query = query.filter(Expense.date <= datetime.strptime(date_to, '%Y-%m-%d'))
    
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
    categories = Category.query.all()
    wallets = Wallet.query.all()
    
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

# ===== WALLETS =====
@main.route('/wallets')
def wallets():
    all_wallets = Wallet.query.all()
    return render_template('wallets.html', wallets=all_wallets)

@main.route('/wallets/add', methods=['GET', 'POST'])
def add_wallet():
    if request.method == 'POST':
        name = request.form.get('name')
        balance = float(request.form.get('balance', 0))
        currency = request.form.get('currency', 'GHS')
        icon = request.form.get('icon', '💰')
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
            is_shared=is_shared
        )
        db.session.add(wallet)
        db.session.commit()
        flash('Wallet created successfully!', 'success')
        return redirect(url_for('main.wallets'))
    
    return render_template('add_wallet.html')

@main.route('/wallets/edit/<int:id>', methods=['GET', 'POST'])
def edit_wallet(id):
    wallet = Wallet.query.get_or_404(id)
    
    if request.method == 'POST':
        wallet.name = request.form.get('name')
        wallet.balance = float(request.form.get('balance', 0))
        wallet.currency = request.form.get('currency', 'GHS')
        wallet.icon = request.form.get('icon', '💰')
        wallet.wallet_type = request.form.get('wallet_type', 'cash')
        wallet.account_number = request.form.get('account_number')
        wallet.is_shared = request.form.get('is_shared') == 'on'
        
        db.session.commit()
        flash('Wallet updated successfully!', 'success')
        return redirect(url_for('main.wallets'))
    
    return render_template('edit_wallet.html', wallet=wallet)

@main.route('/wallets/delete/<int:id>', methods=['POST'])
def delete_wallet(id):
    wallet = Wallet.query.get_or_404(id)
    
    # Check if wallet has transactions
    expense_count = Expense.query.filter_by(wallet_id=id).count()
    if expense_count > 0:
        flash(f'Cannot delete wallet with {expense_count} transaction(s). Please reassign or delete transactions first.', 'error')
        return redirect(url_for('main.wallets'))
    
    db.session.delete(wallet)
    db.session.commit()
    flash('Wallet deleted successfully!', 'success')
    return redirect(url_for('main.wallets'))

# ===== BUDGETS =====
@main.route('/budgets')
def budgets():
    all_budgets = Budget.query.filter_by(is_active=True).all()
    budget_data = []
    
    for budget in all_budgets:
        # Calculate effective start date based on period
        now = datetime.utcnow()
        if budget.period == 'weekly':
            # Start of current week (Monday)
            effective_start = now - timedelta(days=now.weekday())
        elif budget.period == 'monthly':
            # Start of current month
            effective_start = datetime(now.year, now.month, 1)
        elif budget.period == 'yearly':
            # Start of current year
            effective_start = datetime(now.year, 1, 1)
        else:
            effective_start = budget.start_date
        
        spent = db.session.query(func.sum(Expense.amount)).filter(
            Expense.category_id == budget.category_id,
            Expense.transaction_type == 'expense',
            Expense.date >= effective_start
        ).scalar() or 0
        
        percentage = (spent / budget.amount * 100) if budget.amount > 0 else 0
        budget_data.append({
            'budget': budget,
            'spent': spent,
            'remaining': budget.amount - spent,
            'percentage': percentage,
            'width_percentage': min(percentage, 100)
        })
    
    return render_template('budgets.html', budgets=budget_data)

@main.route('/budgets/add', methods=['GET', 'POST'])
def add_budget():
    categories = Category.query.all()
    
    if request.method == 'POST':
        category_id = int(request.form.get('category'))
        amount = float(request.form.get('amount'))
        period = request.form.get('period', 'monthly')
        
        # Calculate start and end dates based on period
        start_date = datetime.utcnow()
        if period == 'weekly':
            end_date = start_date + timedelta(days=7)
        elif period == 'monthly':
            end_date = start_date + timedelta(days=30)
        elif period == 'yearly':
            end_date = start_date + timedelta(days=365)
        
        budget = Budget(
            category_id=category_id,
            amount=amount,
            period=period,
            start_date=start_date,
            end_date=end_date
        )
        db.session.add(budget)
        db.session.commit()
        flash('Budget created successfully!', 'success')
        return redirect(url_for('main.budgets'))
    
    return render_template('add_budget.html', categories=categories)

@main.route('/budgets/delete/<int:id>', methods=['POST'])
def delete_budget(id):
    budget = Budget.query.get_or_404(id)
    db.session.delete(budget)
    db.session.commit()
    flash('Budget deleted successfully!', 'success')
    return redirect(url_for('main.budgets'))

# ===== RECURRING TRANSACTIONS =====
@main.route('/recurring')
def recurring_transactions():
    recurring = RecurringTransaction.query.filter_by(is_active=True).all()
    return render_template('recurring.html', recurring=recurring)

@main.route('/recurring/add', methods=['GET', 'POST'])
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
        return redirect(url_for('main.recurring_transactions'))
    
    return render_template('edit_recurring.html', recurring=recurring, categories=categories, wallets=wallets)

@main.route('/recurring/delete/<int:id>', methods=['POST'])
def delete_recurring(id):
    recurring = RecurringTransaction.query.get_or_404(id)
    db.session.delete(recurring)
    db.session.commit()
    flash('Recurring transaction deleted successfully!', 'success')
    return redirect(url_for('main.recurring_transactions'))

# ===== ANALYTICS =====
@main.route('/analytics')
def analytics():
    # Category breakdown for pie chart (Expenses only)
    category_data = db.session.query(
        Category.name, Category.icon, func.sum(Expense.amount)
    ).join(Expense).filter(Expense.transaction_type == 'expense').group_by(Category.id).all()
    
    # Monthly trend for line chart (last 6 months)
    monthly_data = []
    today = datetime.utcnow()
    
    for i in range(5, -1, -1):
        # Calculate start of month
        month_date = today - timedelta(days=30 * i) # Approximate
        month_start = datetime(month_date.year, month_date.month, 1)
        
        # Calculate end of month
        if month_start.month == 12:
            month_end = datetime(month_start.year + 1, 1, 1)
        else:
            month_end = datetime(month_start.year, month_start.month + 1, 1)
            
        # Get Expenses (Live)
        expense_total = db.session.query(func.sum(Expense.amount)).filter(
            Expense.transaction_type == 'expense',
            Expense.date >= month_start,
            Expense.date < month_end
        ).scalar() or 0
        
        # Get Income (Live)
        income_total = db.session.query(func.sum(Expense.amount)).filter(
            Expense.transaction_type == 'income',
            Expense.date >= month_start,
            Expense.date < month_end
        ).scalar() or 0
        
        # Add Historical Data
        hist_summary = FinancialSummary.query.filter_by(
            year=month_start.year, 
            month=month_start.month
        ).first()
        
        if hist_summary:
            expense_total += hist_summary.total_expense
            income_total += hist_summary.total_income
        
        monthly_data.append({
            'month': month_start.strftime('%b'),
            'expense': expense_total,
            'income': income_total
        })
    
    # Yearly trend (Last 12 Months)
    yearly_data = []
    
    for i in range(11, -1, -1):
        # Calculate start of month
        month_date = today - timedelta(days=30 * i)
        month_start = datetime(month_date.year, month_date.month, 1)
        
        if month_start.month == 12:
            month_end = datetime(month_start.year + 1, 1, 1)
        else:
            month_end = datetime(month_start.year, month_start.month + 1, 1)
            
        # Live Data
        expense_total = db.session.query(func.sum(Expense.amount)).filter(
            Expense.transaction_type == 'expense',
            Expense.date >= month_start,
            Expense.date < month_end
        ).scalar() or 0
        
        income_total = db.session.query(func.sum(Expense.amount)).filter(
            Expense.transaction_type == 'income',
            Expense.date >= month_start,
            Expense.date < month_end
        ).scalar() or 0
        
        # Historical Data
        hist_summary = FinancialSummary.query.filter_by(
            year=month_start.year, 
            month=month_start.month
        ).first()
        
        if hist_summary:
            expense_total += hist_summary.total_expense
            income_total += hist_summary.total_income
        
        yearly_data.append({
            'month': month_start.strftime('%b %Y'),
            'expense': expense_total,
            'income': income_total
        })
        
    # Annual Overview (All Years)
    # Get all years from Expenses
    expense_years = db.session.query(func.extract('year', Expense.date)).distinct().all()
    expense_years = [int(y[0]) for y in expense_years] if expense_years else []
    
    # Get all years from FinancialSummary
    hist_years = db.session.query(FinancialSummary.year).distinct().all()
    hist_years = [int(y[0]) for y in hist_years] if hist_years else []
    
    all_years = sorted(list(set(expense_years + hist_years)), reverse=True)
    
    annual_data = []
    for year in all_years:
        year_start = datetime(year, 1, 1)
        year_end = datetime(year + 1, 1, 1)
        
        # Live Data
        live_expense = db.session.query(func.sum(Expense.amount)).filter(
            Expense.transaction_type == 'expense',
            Expense.date >= year_start,
            Expense.date < year_end
        ).scalar() or 0
        
        live_income = db.session.query(func.sum(Expense.amount)).filter(
            Expense.transaction_type == 'income',
            Expense.date >= year_start,
            Expense.date < year_end
        ).scalar() or 0
        
        # Historical Data (Sum of all monthly + yearly summaries for this year)
        hist_records = FinancialSummary.query.filter_by(year=year).all()
        hist_expense = sum(h.total_expense for h in hist_records)
        hist_income = sum(h.total_income for h in hist_records)
        
        annual_data.append({
            'year': year,
            'expense': live_expense + hist_expense,
            'income': live_income + hist_income
        })

    return render_template('analytics.html', 
                         category_data=category_data,
                         monthly_data=monthly_data,
                         yearly_data=yearly_data,
                         annual_data=annual_data)

# ===== CATEGORIES =====
@main.route('/categories')
def categories():
    all_categories = Category.query.all()
    return render_template('categories.html', categories=all_categories)

@main.route('/categories/add', methods=['POST'])
def add_category():
    name = request.form.get('name')
    icon = request.form.get('icon', '📝')
    
    category = Category(name=name, icon=icon, is_custom=True)
    db.session.add(category)
    db.session.commit()
    flash('Category created successfully!', 'success')
    return redirect(url_for('main.categories'))

@main.route('/categories/delete/<int:id>', methods=['POST'])
def delete_category(id):
    category = Category.query.get_or_404(id)
    if not category.is_custom:
        flash('Cannot delete default categories!', 'error')
        return redirect(url_for('main.categories'))
    
    db.session.delete(category)
    db.session.commit()
    flash('Category deleted successfully!', 'success')
    return redirect(url_for('main.categories'))

# ===== EXPORT =====
@main.route('/export/csv')
def export_csv():
    expenses = Expense.query.order_by(Expense.date.desc()).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Date', 'Description', 'Category', 'Wallet', 'Amount', 'Type', 'Tags', 'Notes'])
    
    for expense in expenses:
        writer.writerow([
            expense.date.strftime('%Y-%m-%d'),
            expense.description,
            expense.category.name,
            expense.wallet.name,
            expense.amount,
            expense.transaction_type,
            expense.tags or '',
            expense.notes or ''
        ])
    
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=expenses.csv'}
    )

# ===== CURRENCY CONVERSION =====
@main.route('/api/convert-currency', methods=['POST'])
def convert_currency():
    try:
        amount = float(request.json.get('amount', 0))
        
        # Use a free currency API to get exchange rates
        import requests
        
        # Using exchangerate-api.com (free tier)
        api_url = 'https://api.exchangerate-api.com/v4/latest/GHS'
        
        response = requests.get(api_url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            rates = data.get('rates', {})
            
            # Convert to popular currencies
            conversions = {
                'GHS': amount,
                'USD': amount * rates.get('USD', 0),
                'EUR': amount * rates.get('EUR', 0),
                'GBP': amount * rates.get('GBP', 0),
                'JPY': amount * rates.get('JPY', 0),
                'CNY': amount * rates.get('CNY', 0),
            }
            
            return jsonify({
                'success': True,
                'conversions': conversions,
                'rates': rates
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to fetch exchange rates'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ===== REPORTS =====
@main.route('/reports')
def reports():
    now = datetime.utcnow()
    
    # Weekly (last 7 days)
    week_start = now - timedelta(days=7)
    weekly_expenses = db.session.query(
        Category.name, func.sum(Expense.amount)
    ).join(Category).filter(Expense.date >= week_start, Expense.transaction_type == 'expense').group_by(Category.name).all()
    
    # Monthly (this month)
    month_start = datetime(now.year, now.month, 1)
    monthly_expenses = db.session.query(
        Category.name, func.sum(Expense.amount)
    ).join(Category).filter(Expense.date >= month_start, Expense.transaction_type == 'expense').group_by(Category.name).all()
    
    # Quarterly (last 3 months approx)
    quarter_start = now - timedelta(days=90)
    quarterly_expenses = db.session.query(
        Category.name, func.sum(Expense.amount)
    ).join(Category).filter(Expense.date >= quarter_start, Expense.transaction_type == 'expense').group_by(Category.name).all()
    
    # Yearly (this year)
    year_start = datetime(now.year, 1, 1)
    yearly_expenses = db.session.query(
        Category.name, func.sum(Expense.amount)
    ).join(Category).filter(Expense.date >= year_start, Expense.transaction_type == 'expense').group_by(Category.name).all()

    # Calculate totals
    weekly_total = sum(amount for _, amount in weekly_expenses)
    monthly_total = sum(amount for _, amount in monthly_expenses)
    quarterly_total = sum(amount for _, amount in quarterly_expenses)
    yearly_total = sum(amount for _, amount in yearly_expenses)

    return render_template('reports.html', 
                           weekly=weekly_expenses, 
                           monthly=monthly_expenses, 
                           quarterly=quarterly_expenses, 
                           yearly=yearly_expenses,
                           weekly_total=weekly_total,
                           monthly_total=monthly_total,
                           quarterly_total=quarterly_total,
                           yearly_total=yearly_total)

# ===== PROJECTS TO-DO =====
@main.route('/projects')
def projects():
    projects = Project.query.order_by(Project.created_date.desc()).all()
    return render_template('projects.html', projects=projects)

@main.route('/projects/add', methods=['GET', 'POST'])
def add_project():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        funding_source = request.form.get('funding_source')
        custom_funding_source = request.form.get('custom_funding_source')
        wallet_id = request.form.get('wallet_id')
        
        # Determine the actual funding source
        if funding_source == 'wallet' and wallet_id:
            final_funding_source = 'wallet'
            final_wallet_id = int(wallet_id)
            final_custom_source = None
        elif funding_source == 'other' and custom_funding_source:
            final_funding_source = 'other'
            final_wallet_id = None
            final_custom_source = custom_funding_source
        else:
            final_funding_source = funding_source
            final_wallet_id = None
            final_custom_source = None
        
        project = Project(
            name=name,
            description=description,
            funding_source=final_funding_source,
            wallet_id=final_wallet_id,
            custom_funding_source=final_custom_source
        )
        db.session.add(project)
        db.session.commit()
        flash('Project created successfully!', 'success')
        return redirect(url_for('main.project_details', id=project.id))
    
    wallets = Wallet.query.all()
    return render_template('add_project.html', wallets=wallets)

@main.route('/projects/<int:id>')
def project_details(id):
    project = Project.query.get_or_404(id)
    
    # Calculate total cost of completed items (sum of all paid payments)
    completed_cost = sum(item.total_paid for item in project.items)
    
    # Calculate total cost of not completed items
    not_completed_cost = sum((item.cost - item.total_paid) for item in project.items)
    
    return render_template('project_details.html', project=project, completed_cost=completed_cost, not_completed_cost=not_completed_cost)

@main.route('/projects/edit/<int:id>', methods=['GET', 'POST'])
def edit_project(id):
    project = Project.query.get_or_404(id)
    
    if request.method == 'POST':
        project.name = request.form.get('name')
        project.description = request.form.get('description')
        funding_source = request.form.get('funding_source')
        custom_funding_source = request.form.get('custom_funding_source')
        wallet_id = request.form.get('wallet_id')
        
        # Determine the actual funding source
        if funding_source == 'wallet' and wallet_id:
            project.funding_source = 'wallet'
            project.wallet_id = int(wallet_id)
            project.custom_funding_source = None
        elif funding_source == 'other' and custom_funding_source:
            project.funding_source = 'other'
            project.wallet_id = None
            project.custom_funding_source = custom_funding_source
        else:
            project.funding_source = funding_source
            project.wallet_id = None
            project.custom_funding_source = None
        
        db.session.commit()
        flash('Project updated successfully!', 'success')
        return redirect(url_for('main.project_details', id=project.id))
    
    wallets = Wallet.query.all()
    return render_template('edit_project.html', project=project, wallets=wallets)

@main.route('/projects/delete/<int:id>', methods=['POST'])
def delete_project(id):
    project = Project.query.get_or_404(id)
    db.session.delete(project)
    db.session.commit()
    flash('Project deleted successfully!', 'success')
    return redirect(url_for('main.projects'))

@main.route('/projects/<int:project_id>/items/add', methods=['POST'])
def add_project_item(project_id):
    project = Project.query.get_or_404(project_id)
    item_name = request.form.get('item_name')
    cost = float(request.form.get('cost', 0))
    description = request.form.get('description', '')
    
    item = ProjectItem(
        project_id=project_id,
        item_name=item_name,
        cost=cost,
        description=description
    )
    db.session.add(item)
    db.session.commit()
    flash('Item added successfully!', 'success')
    return redirect(url_for('main.project_details', id=project_id))

@main.route('/projects/<int:project_id>/items/<int:item_id>/delete', methods=['POST'])
def delete_project_item(project_id, item_id):
    item = ProjectItem.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    flash('Item deleted successfully!', 'success')
    return redirect(url_for('main.project_details', id=project_id))

@main.route('/projects/<int:project_id>/items/<int:item_id>/edit', methods=['GET', 'POST'])
def edit_project_item(project_id, item_id):
    item = ProjectItem.query.get_or_404(item_id)
    project = Project.query.get_or_404(project_id)
    
    if request.method == 'POST':
        item.item_name = request.form.get('item_name')
        item.cost = float(request.form.get('cost', 0))
        item.description = request.form.get('description', '')
        db.session.commit()
        flash('Item updated successfully!', 'success')
        return redirect(url_for('main.project_details', id=project_id))
    
    return render_template('edit_project_item.html', item=item, project=project)

@main.route('/projects/<int:project_id>/items/<int:item_id>/toggle', methods=['POST'])
def toggle_project_item(project_id, item_id):
    item = ProjectItem.query.get_or_404(item_id)
    item.is_completed = not item.is_completed
    db.session.commit()
    return jsonify({'success': True, 'is_completed': item.is_completed})

# ===== PROJECT ITEM PAYMENTS =====
@main.route('/projects/<int:project_id>/items/<int:item_id>/payments/add', methods=['POST'])
def add_project_item_payment(project_id, item_id):
    project = Project.query.get_or_404(project_id)
    item = ProjectItem.query.get_or_404(item_id)
    
    amount = float(request.form.get('payment_amount'))
    description = request.form.get('payment_description', '')
    
    payment = ProjectItemPayment(
        project_item_id=item_id,
        amount=amount,
        description=description
    )
    db.session.add(payment)
    db.session.commit()
    flash('Payment added successfully!', 'success')
    return redirect(url_for('main.project_details', id=project_id))

@main.route('/projects/<int:project_id>/items/<int:item_id>/payments/<int:payment_id>/toggle', methods=['POST'])
def toggle_project_item_payment(project_id, item_id, payment_id):
    payment = ProjectItemPayment.query.get_or_404(payment_id)
    payment.is_paid = not payment.is_paid
    if payment.is_paid:
        payment.payment_date = datetime.utcnow()
    else:
        payment.payment_date = None
    db.session.commit()
    return jsonify({'success': True, 'is_paid': payment.is_paid})

@main.route('/projects/<int:project_id>/items/<int:item_id>/payments/<int:payment_id>/delete', methods=['POST'])
def delete_project_item_payment(project_id, item_id, payment_id):
    payment = ProjectItemPayment.query.get_or_404(payment_id)
    db.session.delete(payment)
    db.session.commit()
    flash('Payment deleted successfully!', 'success')
    return redirect(url_for('main.project_details', id=project_id))
# ===== HISTORICAL DATA =====
@main.route('/historical')
def historical_data():
    summaries = FinancialSummary.query.order_by(FinancialSummary.year.desc(), FinancialSummary.month.desc()).all()
    
    # Group by year
    data_by_year = {}
    for summary in summaries:
        if summary.year not in data_by_year:
            data_by_year[summary.year] = {'yearly': None, 'monthly': []}
        
        if summary.month:
            data_by_year[summary.year]['monthly'].append(summary)
        else:
            data_by_year[summary.year]['yearly'] = summary
            
    return render_template('historical_data.html', data_by_year=data_by_year)

@main.route('/historical/add', methods=['POST'])
def add_historical_summary():
    year = int(request.form.get('year'))
    month = request.form.get('month')
    month = int(month) if month else None
    
    total_income = float(request.form.get('total_income', 0))
    total_expense = float(request.form.get('total_expense', 0))
    notes = request.form.get('notes')
    
    # Check if exists
    existing = FinancialSummary.query.filter_by(year=year, month=month).first()
    if existing:
        existing.total_income = total_income
        existing.total_expense = total_expense
        existing.notes = notes
        flash('Historical record updated!', 'success')
    else:
        summary = FinancialSummary(
            year=year,
            month=month,
            total_income=total_income,
            total_expense=total_expense,
            notes=notes
        )
        db.session.add(summary)
        flash('Historical record added!', 'success')
        
    db.session.commit()
    return redirect(url_for('main.historical_data'))

@main.route('/historical/edit/<int:id>', methods=['POST'])
def edit_historical_summary(id):
    summary = FinancialSummary.query.get_or_404(id)
    
    year = int(request.form.get('year'))
    month = request.form.get('month')
    month = int(month) if month else None
    
    # Check for duplicates if year/month changed
    if summary.year != year or summary.month != month:
        existing = FinancialSummary.query.filter_by(year=year, month=month).first()
        if existing:
            flash(f'A record for {year}-{month if month else "Yearly"} already exists!', 'error')
            return redirect(url_for('main.historical_data'))

    summary.year = year
    summary.month = month
    summary.total_income = float(request.form.get('total_income', 0))
    summary.total_expense = float(request.form.get('total_expense', 0))
    summary.notes = request.form.get('notes')
    
    db.session.commit()
    flash('Record updated!', 'success')
    return redirect(url_for('main.historical_data'))

@main.route('/historical/delete/<int:id>', methods=['POST'])
def delete_historical_summary(id):
    summary = FinancialSummary.query.get_or_404(id)
    db.session.delete(summary)
    db.session.commit()
    flash('Record deleted!', 'success')
    return redirect(url_for('main.historical_data'))
