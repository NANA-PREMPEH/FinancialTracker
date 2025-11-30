from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file, Response
from . import db
from .models import Expense, Category, Wallet, Budget, RecurringTransaction, ExchangeRate
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
        flash('Transaction added successfully!', 'success')
        return redirect(url_for('main.dashboard'))
    
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
        return redirect(url_for('main.dashboard'))
    
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
    return redirect(url_for('main.dashboard'))

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
        is_shared = request.form.get('is_shared') == 'on'
        
        wallet = Wallet(
            name=name,
            balance=balance,
            currency=currency,
            icon=icon,
            wallet_type=wallet_type,
            is_shared=is_shared
        )
        db.session.add(wallet)
        db.session.commit()
        flash('Wallet created successfully!', 'success')
        return redirect(url_for('main.wallets'))
    
    return render_template('add_wallet.html')

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

# ===== ANALYTICS =====
@main.route('/analytics')
def analytics():
    # Category breakdown for pie chart
    category_data = db.session.query(
        Category.name, Category.icon, func.sum(Expense.amount)
    ).join(Expense).filter(Expense.transaction_type == 'expense').group_by(Category.id).all()
    
    # Monthly trend for line chart (last 6 months)
    monthly_data = []
    for i in range(6):
        month_start = datetime.utcnow() - timedelta(days=30 * i)
        month_end = month_start + timedelta(days=30)
        total = db.session.query(func.sum(Expense.amount)).filter(
            Expense.transaction_type == 'expense',
            Expense.date >= month_start,
            Expense.date < month_end
        ).scalar() or 0
        monthly_data.append({'month': month_start.strftime('%b'), 'amount': total})
    
    monthly_data.reverse()
    
    return render_template('analytics.html', 
                         category_data=category_data,
                         monthly_data=monthly_data)

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
