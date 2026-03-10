from flask import render_template, request, redirect, url_for, flash, send_file, Response
from flask_login import login_required, current_user
from . import db
from .models import Expense, Category, FinancialSummary
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from sqlalchemy import func, or_
import io
import csv


def register_routes(main):

    @main.route('/analytics')
    @login_required
    def analytics():
        # Category breakdown for pie chart (Expenses only) - Exclude Transfers
        transfer_cat = Category.query.filter_by(name='Transfer').first()
        transfer_id = transfer_cat.id if transfer_cat else -1

        debt_lent_cat = Category.query.filter_by(name='Money Lent', user_id=current_user.id).first()
        debt_lent_id = debt_lent_cat.id if debt_lent_cat else -1

        category_data = db.session.query(
            Category.name, Category.icon, func.sum(Expense.amount)
        ).join(Expense).filter(
            Expense.transaction_type == 'expense',
            Category.id != transfer_id
        ).group_by(Category.id).all()

        # Monthly trend for line chart (last 6 months)
        monthly_data = []
        today = datetime.utcnow()

        for i in range(5, -1, -1):
            month_date = today - relativedelta(months=i)
            month_start = datetime(month_date.year, month_date.month, 1)

            if month_start.month == 12:
                month_end = datetime(month_start.year + 1, 1, 1)
            else:
                month_end = datetime(month_start.year, month_start.month + 1, 1)

            expense_total = db.session.query(func.sum(Expense.amount)).filter(
                Expense.transaction_type == 'expense',
                Expense.date >= month_start,
                Expense.date < month_end,
                Expense.category_id != transfer_id
            ).scalar() or 0

            income_total = db.session.query(func.sum(Expense.amount)).filter(
                Expense.transaction_type == 'income',
                Expense.date >= month_start,
                Expense.date < month_end,
                Expense.category_id != transfer_id
            ).scalar() or 0

            hist_summary = FinancialSummary.query.filter_by(
                year=month_start.year,
                month=month_start.month
            ).first()

            if hist_summary:
                expense_total += hist_summary.total_expense
                income_total += hist_summary.total_income

            m_lent = db.session.query(func.sum(Expense.amount)).filter(
                Expense.user_id == current_user.id,
                Expense.transaction_type == 'expense',
                Expense.date >= month_start,
                Expense.date < month_end,
                or_(Expense.category_id == debt_lent_id, Expense.tags.ilike('%debt_lent%'))
            ).scalar() or 0

            coll_cat = Category.query.filter_by(name='Debt Collection', user_id=current_user.id).first()
            coll_id = coll_cat.id if coll_cat else -1
            rec_cat = Category.query.filter_by(name='Bad Debt Recovery', user_id=current_user.id).first()
            rec_id = rec_cat.id if rec_cat else -1

            m_recovered = db.session.query(func.sum(Expense.amount)).filter(
                Expense.user_id == current_user.id,
                Expense.transaction_type == 'income',
                Expense.date >= month_start,
                Expense.date < month_end,
                or_(
                    Expense.category_id.in_([coll_id, rec_id]),
                    Expense.tags.ilike('%debt_collection%'),
                    Expense.tags.ilike('%bad_debt_recovery%')
                )
            ).scalar() or 0

            monthly_data.append({
                'month': month_start.strftime('%b'),
                'expense': expense_total,
                'actual_expense': expense_total - m_lent,
                'income': income_total,
                'actual_income': income_total - m_recovered
            })

        # Yearly trend (Last 12 Months)
        yearly_data = []

        for i in range(11, -1, -1):
            month_date = today - relativedelta(months=i)
            month_start = datetime(month_date.year, month_date.month, 1)

            if month_start.month == 12:
                month_end = datetime(month_start.year + 1, 1, 1)
            else:
                month_end = datetime(month_start.year, month_start.month + 1, 1)

            expense_total = db.session.query(func.sum(Expense.amount)).filter(
                Expense.transaction_type == 'expense',
                Expense.date >= month_start,
                Expense.date < month_end,
                Expense.category_id != transfer_id
            ).scalar() or 0

            income_total = db.session.query(func.sum(Expense.amount)).filter(
                Expense.transaction_type == 'income',
                Expense.date >= month_start,
                Expense.date < month_end,
                Expense.category_id != transfer_id
            ).scalar() or 0

            hist_summary = FinancialSummary.query.filter_by(
                year=month_start.year,
                month=month_start.month
            ).first()

            if hist_summary:
                expense_total += hist_summary.total_expense
                income_total += hist_summary.total_income

            m_lent = db.session.query(func.sum(Expense.amount)).filter(
                Expense.user_id == current_user.id,
                Expense.transaction_type == 'expense',
                Expense.date >= month_start,
                Expense.date < month_end,
                or_(Expense.category_id == debt_lent_id, Expense.tags.ilike('%debt_lent%'))
            ).scalar() or 0

            m_recovered = db.session.query(func.sum(Expense.amount)).filter(
                Expense.user_id == current_user.id,
                Expense.transaction_type == 'income',
                Expense.date >= month_start,
                Expense.date < month_end,
                or_(
                    Expense.category_id.in_([coll_id, rec_id]),
                    Expense.tags.ilike('%debt_collection%'),
                    Expense.tags.ilike('%bad_debt_recovery%')
                )
            ).scalar() or 0

            yearly_data.append({
                'month': month_start.strftime('%b %Y'),
                'expense': expense_total,
                'actual_expense': expense_total - m_lent,
                'income': income_total,
                'actual_income': income_total - m_recovered
            })

        # Annual Overview (All Years)
        expense_years = db.session.query(func.extract('year', Expense.date)).distinct().all()
        expense_years = [int(y[0]) for y in expense_years] if expense_years else []

        hist_years = db.session.query(FinancialSummary.year).distinct().all()
        hist_years = [int(y[0]) for y in hist_years] if hist_years else []

        all_years = sorted(list(set(expense_years + hist_years)), reverse=True)

        annual_data = []
        for year in all_years:
            year_start = datetime(year, 1, 1)
            year_end = datetime(year + 1, 1, 1)

            live_expense = db.session.query(func.sum(Expense.amount)).filter(
                Expense.transaction_type == 'expense',
                Expense.date >= year_start,
                Expense.date < year_end,
                Expense.category_id != transfer_id
            ).scalar() or 0

            live_income = db.session.query(func.sum(Expense.amount)).filter(
                Expense.user_id == current_user.id,
                Expense.transaction_type == 'income',
                Expense.date >= year_start,
                Expense.date < year_end,
                Expense.category_id != transfer_id
            ).scalar() or 0

            live_money_lent = db.session.query(func.sum(Expense.amount)).filter(
                Expense.user_id == current_user.id,
                Expense.transaction_type == 'expense',
                Expense.date >= year_start,
                Expense.date < year_end,
                or_(Expense.category_id == debt_lent_id, Expense.tags.ilike('%debt_lent%')),
                Expense.category_id != transfer_id
            ).scalar() or 0

            live_m_recovered = db.session.query(func.sum(Expense.amount)).filter(
                Expense.user_id == current_user.id,
                Expense.transaction_type == 'income',
                Expense.date >= year_start,
                Expense.date < year_end,
                or_(
                    Expense.category_id.in_([coll_id, rec_id]),
                    Expense.tags.ilike('%debt_collection%'),
                    Expense.tags.ilike('%bad_debt_recovery%')
                ),
                Expense.category_id != transfer_id
            ).scalar() or 0

            hist_records = FinancialSummary.query.filter_by(year=year).all()
            hist_expense = sum(h.total_expense for h in hist_records)
            hist_income = sum(h.total_income for h in hist_records)

            annual_data.append({
                'year': year,
                'expense': live_expense + hist_expense,
                'actual_expense': live_expense + hist_expense - live_money_lent,
                'income': live_income + hist_income,
                'actual_income': live_income + hist_income - live_m_recovered
            })

        return render_template('analytics.html',
                             category_data=category_data,
                             monthly_data=monthly_data,
                             yearly_data=yearly_data,
                             annual_data=annual_data)

    # ===== EXPORT =====
    @main.route('/export/csv')
    @login_required
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

    @main.route('/export/pdf')
    @login_required
    def export_pdf():
        from .export import generate_pdf
        expenses = Expense.query.filter_by(user_id=current_user.id).order_by(Expense.date.desc()).all()
        buffer = generate_pdf(expenses, current_user)
        return send_file(buffer, mimetype='application/pdf', as_attachment=True,
                         download_name=f'transactions_{datetime.utcnow().strftime("%Y%m%d")}.pdf')

    @main.route('/export/excel')
    @login_required
    def export_excel():
        from .export import generate_excel
        expenses = Expense.query.filter_by(user_id=current_user.id).order_by(Expense.date.desc()).all()
        buffer = generate_excel(expenses, current_user)
        return send_file(buffer, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                         as_attachment=True,
                         download_name=f'transactions_{datetime.utcnow().strftime("%Y%m%d")}.xlsx')

    # ===== REPORTS =====
    @main.route('/reports')
    @login_required
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
