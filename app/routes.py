from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from . import db
from .models import (Expense, Category, Wallet, Budget, FinancialSummary,
                     Creditor, WalletShare, ProjectItem, ProjectItemPayment,
                     DebtPayment, DebtorPayment, ContractPayment)
from .utils import get_exchange_rate
from datetime import datetime, timedelta
from sqlalchemy import func, or_
import requests

main = Blueprint('main', __name__)


# ===== SHARED HELPERS =====
def get_accessible_wallets(user_id):
    """Get wallets the user owns + wallets shared with them (contribute or manage permission)."""
    owned = Wallet.query.filter_by(user_id=user_id).all()

    shared_shares = WalletShare.query.filter_by(
        shared_with_id=user_id,
        accepted=True
    ).filter(WalletShare.permission.in_(['contribute', 'manage'])).all()

    shared_wallet_ids = [s.wallet_id for s in shared_shares]
    shared = Wallet.query.filter(Wallet.id.in_(shared_wallet_ids)).all() if shared_wallet_ids else []

    return list(owned) + list(shared)


def can_access_wallet(user_id, wallet_id):
    """Check if user can access a specific wallet (own or shared with contribute/manage)."""
    wallet = Wallet.query.get(wallet_id)
    if not wallet:
        return False

    if wallet.user_id == user_id:
        return True

    share = WalletShare.query.filter_by(
        wallet_id=wallet_id,
        shared_with_id=user_id,
        accepted=True
    ).filter(WalletShare.permission.in_(['contribute', 'manage'])).first()

    return share is not None


# ===== DASHBOARD =====
@main.route('/')
@login_required
def dashboard():
    wallets = Wallet.query.filter_by(user_id=current_user.id).all()
    # Exclude Transfer category
    transfer_cat = Category.query.filter_by(name='Transfer', user_id=current_user.id).first()
    transfer_id = transfer_cat.id if transfer_cat else -1
    transfer_types = ('transfer', 'transfer_out', 'transfer_in')
    # Updated Robust Transfer Filter (Handles NULL tags/description)
    transfer_filters = [
        Expense.transaction_type.in_(transfer_types),
        func.coalesce(Expense.tags, '').ilike('%transfer%'),
        func.coalesce(Expense.description, '').ilike('Transfer %')
    ]
    if transfer_id != -1:
        transfer_filters.append(Expense.category_id == transfer_id)
    transfer_filter = or_(*transfer_filters)

    recent_expenses = Expense.query.filter(
        Expense.user_id == current_user.id,
        ~transfer_filter
    ).order_by(Expense.date.desc()).limit(5).all()

    dashboard_start_date = datetime(2024, 1, 1)

    # --- De-duplication Logic ---
    # Find latest month covered by summaries to avoid double-counting in totals
    latest_summary = FinancialSummary.query.filter_by(user_id=current_user.id).order_by(
        FinancialSummary.year.desc(), FinancialSummary.month.desc()).first()
    
    if latest_summary:
        ly, lm = latest_summary.year, latest_summary.month or 12
        if lm == 12:
            live_totals_start = datetime(ly + 1, 1, 1)
        else:
            live_totals_start = datetime(ly, lm + 1, 1)
    else:
        live_totals_start = dashboard_start_date

    # Live totals from the Expense table (starting after latest history)
    total_expenses = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == current_user.id,
        Expense.transaction_type == 'expense',
        Expense.date >= live_totals_start,
        ~transfer_filter
    ).scalar() or 0
    total_income = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == current_user.id,
        Expense.transaction_type == 'income',
        Expense.date >= live_totals_start,
        ~transfer_filter
    ).scalar() or 0

    # Add Historical Data to Totals (starting from 2024)
    hist_expenses = db.session.query(func.sum(FinancialSummary.total_expense)).filter(
        FinancialSummary.user_id == current_user.id,
        FinancialSummary.year >= 2024
    ).scalar() or 0
    hist_income = db.session.query(func.sum(FinancialSummary.total_income)).filter(
        FinancialSummary.user_id == current_user.id,
        FinancialSummary.year >= 2024
    ).scalar() or 0

    total_expenses += hist_expenses
    total_income += hist_income
    # --- Unified Actuals: Extra Payments (Live) ---
    # Only include payments from months NOT covered by historical sums
    # Debt Payments (Expense)
    extra_debt_expense = db.session.query(func.sum(DebtPayment.amount)).filter(
        DebtPayment.user_id == current_user.id,
        DebtPayment.date >= live_totals_start
    ).scalar() or 0

    # Debtor Payments (Income)
    extra_debtor_income = db.session.query(func.sum(DebtorPayment.amount)).filter(
        DebtorPayment.user_id == current_user.id,
        DebtorPayment.date >= live_totals_start
    ).scalar() or 0

    # Contract Payments (Income)
    extra_contract_income = db.session.query(func.sum(ContractPayment.amount)).filter(
        ContractPayment.user_id == current_user.id,
        ContractPayment.payment_date >= live_totals_start
    ).scalar() or 0

    total_expenses += extra_debt_expense
    total_income += extra_debtor_income + extra_contract_income
    # ---------------------------------------------
    # ---------------------------------------------


    # Get all-time Money Lent (Live) - starting from 2024
    debt_lent_cat = Category.query.filter_by(name='Money Lent', user_id=current_user.id).first()
    debt_lent_id = debt_lent_cat.id if debt_lent_cat else -1
    total_money_lent = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == current_user.id,
        Expense.transaction_type == 'expense',
        Expense.date >= dashboard_start_date,
        or_(Expense.category_id == debt_lent_id, Expense.tags.ilike('%debt_lent%')),
        ~transfer_filter
    ).scalar() or 0

    # Get all-time Debt Recoveries/Collections (Live) - starting from 2024
    coll_cat = Category.query.filter_by(name='Debt Collection', user_id=current_user.id).first()
    coll_id = coll_cat.id if coll_cat else -1
    rec_cat = Category.query.filter_by(name='Bad Debt Recovery', user_id=current_user.id).first()
    rec_id = rec_cat.id if rec_cat else -1

    total_m_recovered = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == current_user.id,
        Expense.transaction_type == 'income',
        Expense.date >= dashboard_start_date,
        or_(
            Expense.category_id.in_([coll_id, rec_id]),
            Expense.tags.ilike('%debt_collection%'),
            Expense.tags.ilike('%bad_debt_recovery%')
        ),
        ~transfer_filter
    ).scalar() or 0

    actual_total_expenses = total_expenses - total_money_lent
    actual_total_income = total_income - total_m_recovered - extra_debtor_income - extra_contract_income

    # Get the oldest date for Total Expenses context (respecting 2024 start)
    oldest_expense = db.session.query(func.min(Expense.date)).filter(
        Expense.user_id == current_user.id,
        Expense.transaction_type == 'expense',
        Expense.date >= dashboard_start_date,
        ~transfer_filter
    ).scalar()
    oldest_hist = db.session.query(func.min(FinancialSummary.year)).filter(
        FinancialSummary.user_id == current_user.id,
        FinancialSummary.year >= 2024
    ).scalar()

    oldest_date = dashboard_start_date
    if oldest_expense and oldest_expense > oldest_date:
        # If the actual first expense is later than Jan 1, 2024, we could show that,
        # but the request says "start from Jan 2024", so showing Jan 1 2024 as the baseline is better.
        pass

    if oldest_hist:
        hist_date = datetime(oldest_hist, 1, 1)
        if hist_date > oldest_date:
            # Similar logic as above
            pass

    # Calculate total wallet balance in GHS
    total_wallet_balance = 0
    for wallet in wallets:
        if wallet.currency == 'GHS':
            total_wallet_balance += wallet.balance
        else:
            current_rate = get_exchange_rate(wallet.currency, 'GHS')
            total_wallet_balance += wallet.balance * current_rate

    # Calculate current month's expenses
    now = datetime.utcnow()
    month_start = datetime(now.year, now.month, 1)
    monthly_expenses = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == current_user.id,
        Expense.transaction_type == 'expense',
        Expense.date >= month_start,
        ~transfer_filter
    ).scalar() or 0

    # Current month's extra expenses
    curr_extra_debt_exp = db.session.query(func.sum(DebtPayment.amount)).filter(
        DebtPayment.user_id == current_user.id,
        DebtPayment.date >= month_start
    ).scalar() or 0

    monthly_expenses += curr_extra_debt_exp


    # Calculate current year's expenses
    year_start = datetime(now.year, 1, 1)
    yearly_expenses = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == current_user.id,
        Expense.transaction_type == 'expense',
        Expense.date >= year_start,
        ~transfer_filter
    ).scalar() or 0

    # Add Historical Data for Current Year
    hist_yearly_expenses = db.session.query(func.sum(FinancialSummary.total_expense)).filter(
        FinancialSummary.user_id == current_user.id,
        FinancialSummary.year == now.year
    ).scalar() or 0

    yearly_expenses += hist_yearly_expenses

    # Calculate yearly money lent
    yearly_money_lent = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == current_user.id,
        Expense.transaction_type == 'expense',
        Expense.date >= year_start,
        or_(Expense.category_id == debt_lent_id, Expense.tags.ilike('%debt_lent%')),
        ~transfer_filter
    ).scalar() or 0
    actual_yearly_expenses = yearly_expenses - yearly_money_lent

    # Budget alerts
    budgets = Budget.query.filter_by(user_id=current_user.id, is_active=True).all()
    budget_alerts = []
    for budget in budgets:
        now = datetime.utcnow()
        if budget.period == 'weekly':
            effective_start = now - timedelta(days=now.weekday())
        elif budget.period == 'monthly':
            effective_start = datetime(now.year, now.month, 1)
        elif budget.period == 'yearly':
            effective_start = datetime(now.year, 1, 1)
        else:
            effective_start = budget.start_date

        spent = db.session.query(func.sum(Expense.amount)).filter(
            Expense.user_id == current_user.id,
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

    # Calculate total debt and net balance
    creditors = Creditor.query.filter_by(user_id=current_user.id).all()
    total_debt = sum(c.amount for c in creditors)
    net_wallet_balance = total_wallet_balance - total_debt

    # Calculate actual monthly trend
    debt_lent_cat = Category.query.filter_by(name='Money Lent', user_id=current_user.id).first()
    debt_lent_id = debt_lent_cat.id if debt_lent_cat else -1

    monthly_lent = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == current_user.id,
        Expense.transaction_type == 'expense',
        Expense.date >= month_start,
        or_(Expense.category_id == debt_lent_id, Expense.tags.ilike('%debt_lent%'))
    ).scalar() or 0

    actual_monthly_trend = monthly_expenses - monthly_lent

    # Category spending data for doughnut chart (current month)
    category_spending = db.session.query(
        Category.name, Category.icon, func.sum(Expense.amount)
    ).join(Expense, Expense.category_id == Category.id).filter(
        Expense.user_id == current_user.id,
        Expense.transaction_type == 'expense',
        Expense.date >= month_start,
        ~transfer_filter
    ).group_by(Category.id).order_by(func.sum(Expense.amount).desc()).all()

    chart_categories = [row[0] for row in category_spending]
    chart_amounts = [float(row[2]) for row in category_spending]

    # Monthly trend data for the last 6 months
    monthly_trend = []
    for i in range(5, -1, -1):
        m = now.month - i
        y = now.year
        while m <= 0:
            m += 12
            y -= 1
        m_start = datetime(y, m, 1)
        if m == 12:
            m_end = datetime(y + 1, 1, 1)
        else:
            m_end = datetime(y, m + 1, 1)
        hist_summary = FinancialSummary.query.filter_by(
            user_id=current_user.id,
            year=y,
            month=m
        ).first()

        if hist_summary:
            # If historical summary exists, use it as ground truth for that month
            m_total = hist_summary.total_expense
        else:
            # Otherwise use live data
            m_total = db.session.query(func.sum(Expense.amount)).filter(
                Expense.user_id == current_user.id,
                Expense.transaction_type == 'expense',
                Expense.date >= m_start,
                Expense.date < m_end,
                ~transfer_filter
            ).scalar() or 0

        # Extra payments for this month (Debt Only)
        m_extra_debt_exp = db.session.query(func.sum(DebtPayment.amount)).filter(
            DebtPayment.user_id == current_user.id,
            DebtPayment.date >= m_start,
            DebtPayment.date < m_end
        ).scalar() or 0

        m_total += m_extra_debt_exp


        m_lent = db.session.query(func.sum(Expense.amount)).filter(
            Expense.user_id == current_user.id,
            Expense.transaction_type == 'expense',
            Expense.date >= m_start,
            Expense.date < m_end,
            or_(Expense.category_id == debt_lent_id, Expense.tags.ilike('%debt_lent%'))
        ).scalar() or 0

        monthly_trend.append({
            'label': m_start.strftime('%b'),
            'amount': float(m_total),
            'actual_amount': float(m_total) - float(m_lent)
        })

    trend_labels = [m['label'] for m in monthly_trend]
    trend_amounts = [m['amount'] for m in monthly_trend]
    actual_trend_amounts = [m['actual_amount'] for m in monthly_trend]

    # Check creditor payment due dates (fires push if approaching)
    try:
        from .push_events import check_creditor_due_dates
        check_creditor_due_dates(current_user.id)
    except Exception:
        pass

    return render_template('dashboard.html',
                         wallets=wallets,
                         creditors=creditors,
                         total_debt=total_debt,
                         net_wallet_balance=net_wallet_balance,
                         recent_expenses=recent_expenses,
                         total_expenses=total_expenses,
                         actual_total_expenses=actual_total_expenses,
                         total_income=total_income,
                         actual_total_income=actual_total_income,
                         monthly_expenses=monthly_expenses,
                         yearly_expenses=yearly_expenses,
                         actual_yearly_expenses=actual_yearly_expenses,
                         actual_monthly_trend=actual_monthly_trend,
                         total_wallet_balance=total_wallet_balance,
                         current_date=now,
                         oldest_date=oldest_date,
                         budget_alerts=budget_alerts,
                         chart_categories=chart_categories,
                         chart_amounts=chart_amounts,
                         trend_labels=trend_labels,
                         trend_amounts=trend_amounts,
                         actual_trend_amounts=actual_trend_amounts)


# ===== CATEGORIES =====
@main.route('/categories')
@login_required
def categories():
    all_categories = Category.query.filter_by(user_id=current_user.id).all()
    return render_template('categories.html', categories=all_categories)

@main.route('/categories/add', methods=['POST'])
@login_required
def add_category():
    name = request.form.get('name')
    icon = request.form.get('icon', '\U0001f4dd')

    category = Category(name=name, icon=icon, is_custom=True, user_id=current_user.id)
    db.session.add(category)
    db.session.commit()
    flash('Category created successfully!', 'success')
    return redirect(url_for('main.categories'))

@main.route('/categories/delete/<int:id>', methods=['POST'])
@login_required
def delete_category(id):
    category = Category.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    if not category.is_custom:
        flash('Cannot delete default categories!', 'error')
        return redirect(url_for('main.categories'))

    db.session.delete(category)
    db.session.commit()
    flash('Category deleted successfully!', 'success')
    return redirect(url_for('main.categories'))


# ===== CURRENCY CONVERSION =====
@main.route('/api/convert-currency', methods=['POST'])
@login_required
def convert_currency():
    try:
        amount = float(request.json.get('amount', 0))
        from_currency = request.json.get('from_currency', 'GHS').upper()

        api_url = f'https://api.exchangerate-api.com/v4/latest/{from_currency}'

        response = requests.get(api_url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            rates = data.get('rates', {})

            target_currencies = ['GHS', 'USD', 'EUR', 'GBP', 'JPY', 'CNY']
            conversions = {}
            for curr in target_currencies:
                if curr == from_currency:
                    conversions[curr] = amount
                else:
                    conversions[curr] = amount * rates.get(curr, 0)

            return jsonify({
                'success': True,
                'from_currency': from_currency,
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


# ===== HISTORICAL DATA =====
@main.route('/historical')
@login_required
def historical_data():
    summaries = FinancialSummary.query.filter_by(user_id=current_user.id).order_by(FinancialSummary.year.desc(), FinancialSummary.month.desc()).all()

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
@login_required
def add_historical_summary():
    year = int(request.form.get('year'))
    month = request.form.get('month')
    month = int(month) if month else None

    total_income = float(request.form.get('total_income', 0))
    total_expense = float(request.form.get('total_expense', 0))
    notes = request.form.get('notes')

    existing = FinancialSummary.query.filter_by(year=year, month=month, user_id=current_user.id).first()
    if existing:
        existing.total_income = total_income
        existing.total_expense = total_expense
        existing.notes = notes
        flash('Historical record updated!', 'success')
    else:
        summary = FinancialSummary(
            user_id=current_user.id,
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
@login_required
def edit_historical_summary(id):
    summary = FinancialSummary.query.filter_by(id=id, user_id=current_user.id).first_or_404()

    year = int(request.form.get('year'))
    month = request.form.get('month')
    month = int(month) if month else None

    if summary.year != year or summary.month != month:
        existing = FinancialSummary.query.filter_by(year=year, month=month, user_id=current_user.id).first()
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
    return redirect(url_for('main.historical_data') + f'#historical-{id}')

@main.route('/historical/delete/<int:id>', methods=['POST'])
@login_required
def delete_historical_summary(id):
    summary = FinancialSummary.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    db.session.delete(summary)
    db.session.commit()
    flash('Record deleted!', 'success')
    return redirect(url_for('main.historical_data'))


# ===== REGISTER EXTRACTED ROUTE MODULES =====
from .routes_expenses import register_routes as _reg_expenses
from .routes_wallets import register_routes as _reg_wallets
from .routes_budgets import register_routes as _reg_budgets
from .routes_recurring import register_routes as _reg_recurring
from .routes_analytics import register_routes as _reg_analytics
from .routes_creditors import register_routes as _reg_creditors
from .routes_debtors import register_routes as _reg_debtors
from .routes_projects import register_routes as _reg_projects
from .routes_wishlist import register_routes as _reg_wishlist

_reg_expenses(main)
_reg_wallets(main)
_reg_budgets(main)
_reg_recurring(main)
_reg_analytics(main)
_reg_creditors(main)
_reg_debtors(main)
_reg_projects(main)
_reg_wishlist(main)
