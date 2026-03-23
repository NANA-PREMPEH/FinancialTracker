from flask import render_template, request, redirect, url_for, flash, send_file, Response
from flask_login import login_required, current_user
from . import db
from .models import Expense, Category, FinancialSummary, ProjectItem, ProjectItemPayment, DebtPayment, DebtorPayment, ContractPayment
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from sqlalchemy import func, or_
import io
import csv


def register_routes(main):
    def _get_transfer_filter():
        transfer_cat = Category.query.filter_by(name='Transfer', user_id=current_user.id).first()
        transfer_id = transfer_cat.id if transfer_cat else -1
        transfer_types = ('transfer', 'transfer_out', 'transfer_in')
        
        # Robust Transfer Filter (Handles NULLs)
        transfer_filter = or_(
            Expense.transaction_type.in_(transfer_types),
            func.coalesce(Expense.tags, '').ilike('%transfer%'),
            func.coalesce(Expense.description, '').ilike('Transfer %')
        )
        if transfer_id != -1:
            transfer_filter = or_(transfer_filter, Expense.category_id == transfer_id)
        return transfer_filter


    @main.route('/analytics')
    @login_required
    def analytics():
        # Category breakdown for pie chart (Expenses only) - Exclude Transfers
        transfer_filter = _get_transfer_filter()

        debt_lent_cat = Category.query.filter_by(name='Money Lent', user_id=current_user.id).first()
        debt_lent_id = debt_lent_cat.id if debt_lent_cat else -1

        category_data = db.session.query(
            Category.name, Category.icon, func.sum(Expense.amount)
        ).join(Expense).filter(
            Expense.user_id == current_user.id,
            Expense.transaction_type == 'expense',
            ~transfer_filter
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

            hist_summary = FinancialSummary.query.filter_by(
                user_id=current_user.id,
                year=month_start.year,
                month=month_start.month
            ).first()

            if hist_summary:
                # Use Historical ground truth if available
                expense_total = hist_summary.total_expense
                income_total = hist_summary.total_income
                # We assume FinancialSummary is the final word (no extras needed)
                # But for 'Actuals' (Spent - Lent), we'd need m_lent if the summary doesn't already subtract it.
                # Usually summaries are gross, let's keep it simple or check if user has m_lent in summary.
                # (Models show they are separate: actual_expense is there too but maybe not filled).
                m_lent = 0 
                m_recovered = 0
                m_extra_debtor_inc = 0
                m_extra_contract_inc = 0
            else:
                # Live query
                expense_total = db.session.query(func.sum(Expense.amount)).filter(
                    Expense.user_id == current_user.id,
                    Expense.transaction_type == 'expense',
                    Expense.date >= month_start,
                    Expense.date < month_end,
                    ~transfer_filter
                ).scalar() or 0

                income_total = db.session.query(func.sum(Expense.amount)).filter(
                    Expense.user_id == current_user.id,
                    Expense.transaction_type == 'income',
                    Expense.date >= month_start,
                    Expense.date < month_end,
                    ~transfer_filter
                ).scalar() or 0

                m_lent = db.session.query(func.sum(Expense.amount)).filter(
                    Expense.user_id == current_user.id,
                    Expense.transaction_type == 'expense',
                    Expense.date >= month_start,
                    Expense.date < month_end,
                    or_(Expense.category_id == debt_lent_id, Expense.tags.ilike('%debt_lent%'))
                ).scalar() or 0

                m_extra_debt_exp = db.session.query(func.sum(DebtPayment.amount)).filter(
                    DebtPayment.user_id == current_user.id,
                    DebtPayment.date >= month_start,
                    DebtPayment.date < month_end
                ).scalar() or 0

                m_extra_debtor_inc = db.session.query(func.sum(DebtorPayment.amount)).filter(
                    DebtorPayment.user_id == current_user.id,
                    DebtorPayment.date >= month_start,
                    DebtorPayment.date < month_end
                ).scalar() or 0

                m_extra_contract_inc = db.session.query(func.sum(ContractPayment.amount)).filter(
                    ContractPayment.user_id == current_user.id,
                    ContractPayment.payment_date >= month_start,
                    ContractPayment.payment_date < month_end
                ).scalar() or 0

                expense_total += m_extra_debt_exp
                income_total += m_extra_debtor_inc + m_extra_contract_inc

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
                        func.coalesce(Expense.tags, '').ilike('%debt_collection%'),
                        func.coalesce(Expense.tags, '').ilike('%bad_debt_recovery%')
                    )
                ).scalar() or 0

            monthly_data.append({
                'month': month_start.strftime('%b'),
                'expense': expense_total,
                'actual_expense': expense_total - m_lent,
                'income': income_total,
                'actual_income': income_total - m_recovered - m_extra_debtor_inc - m_extra_contract_inc
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

            hist_summary = FinancialSummary.query.filter_by(
                user_id=current_user.id,
                year=month_start.year,
                month=month_start.month
            ).first()

            if hist_summary:
                expense_total = hist_summary.total_expense
                income_total = hist_summary.total_income
                m_lent = 0
                m_recovered = 0
                y_extra_debtor_inc = 0
                y_extra_contract_inc = 0
            else:
                expense_total = db.session.query(func.sum(Expense.amount)).filter(
                    Expense.user_id == current_user.id,
                    Expense.transaction_type == 'expense',
                    Expense.date >= month_start,
                    Expense.date < month_end,
                    ~transfer_filter
                ).scalar() or 0

                income_total = db.session.query(func.sum(Expense.amount)).filter(
                    Expense.user_id == current_user.id,
                    Expense.transaction_type == 'income',
                    Expense.date >= month_start,
                    Expense.date < month_end,
                    ~transfer_filter
                ).scalar() or 0

                m_lent = db.session.query(func.sum(Expense.amount)).filter(
                    Expense.user_id == current_user.id,
                    Expense.transaction_type == 'expense',
                    Expense.date >= month_start,
                    Expense.date < month_end,
                    or_(Expense.category_id == debt_lent_id, Expense.tags.ilike('%debt_lent%'))
                ).scalar() or 0

                # Extra payments for this month (Yearly Trend)
                y_extra_debt_exp = db.session.query(func.sum(DebtPayment.amount)).filter(
                    DebtPayment.user_id == current_user.id,
                    DebtPayment.date >= month_start,
                    DebtPayment.date < month_end
                ).scalar() or 0

                y_extra_debtor_inc = db.session.query(func.sum(DebtorPayment.amount)).filter(
                    DebtorPayment.user_id == current_user.id,
                    DebtorPayment.date >= month_start,
                    DebtorPayment.date < month_end
                ).scalar() or 0

                y_extra_contract_inc = db.session.query(func.sum(ContractPayment.amount)).filter(
                    ContractPayment.user_id == current_user.id,
                    ContractPayment.payment_date >= month_start,
                    ContractPayment.payment_date < month_end
                ).scalar() or 0

                expense_total += y_extra_debt_exp
                income_total += y_extra_debtor_inc + y_extra_contract_inc

                m_recovered = db.session.query(func.sum(Expense.amount)).filter(
                    Expense.user_id == current_user.id,
                    Expense.transaction_type == 'income',
                    Expense.date >= month_start,
                    Expense.date < month_end,
                    or_(
                        Expense.category_id.in_([coll_id, rec_id]),
                        func.coalesce(Expense.tags, '').ilike('%debt_collection%'),
                        func.coalesce(Expense.tags, '').ilike('%bad_debt_recovery%')
                    )
                ).scalar() or 0

            yearly_data.append({
                'month': month_start.strftime('%b %Y'),
                'expense': expense_total,
                'actual_expense': expense_total - m_lent,
                'income': income_total,
                'actual_income': income_total - m_recovered - y_extra_debtor_inc - y_extra_contract_inc
            })

        # Annual Overview (All Years)
        expense_years = db.session.query(func.extract('year', Expense.date)).distinct().all()
        expense_years = [int(y[0]) for y in expense_years] if expense_years else []

        hist_years = db.session.query(FinancialSummary.year).filter_by(user_id=current_user.id).distinct().all()
        hist_years = [int(y[0]) for y in hist_years] if hist_years else []

        all_years = sorted(list(set(expense_years + hist_years)), reverse=True)

        annual_data = []
        for year in all_years:
            y_expense = 0
            y_income = 0
            y_lent = 0
            y_recovered = 0

            # Check for a Yearly Summary first (month=None)
            yearly_hist = FinancialSummary.query.filter_by(
                user_id=current_user.id, year=year, month=None
            ).first()

            if yearly_hist:
                y_expense = yearly_hist.total_expense or 0
                y_income = yearly_hist.total_income or 0
                # If a yearly summary exists, we assume it covers the historical ground truth
                # and Act will default to Total unless we have more info.
            else:
                # Process each month in the year for correct de-duplication
                for m in range(1, 13):
                    m_start = datetime(year, m, 1)
                    if m == 12:
                        m_end = datetime(year + 1, 1, 1)
                    else:
                        m_end = datetime(year, m + 1, 1)

                    hist_m = FinancialSummary.query.filter_by(
                        user_id=current_user.id, year=year, month=m
                    ).first()

                    if hist_m:
                        y_expense += (hist_m.total_expense or 0)
                        y_income += (hist_m.total_income or 0)
                    else:
                        # Sum Live Expenses + Extras
                        m_live_exp = db.session.query(func.sum(Expense.amount)).filter(
                            Expense.user_id == current_user.id,
                            Expense.transaction_type == 'expense',
                            Expense.date >= m_start,
                            Expense.date < m_end,
                            ~transfer_filter
                        ).scalar() or 0

                        m_live_inc = db.session.query(func.sum(Expense.amount)).filter(
                            Expense.user_id == current_user.id,
                            Expense.transaction_type == 'income',
                            Expense.date >= m_start,
                            Expense.date < m_end,
                            ~transfer_filter
                        ).scalar() or 0

                        m_live_lent = db.session.query(func.sum(Expense.amount)).filter(
                            Expense.user_id == current_user.id,
                            Expense.transaction_type == 'expense',
                            Expense.date >= m_start,
                            Expense.date < m_end,
                            or_(Expense.category_id == debt_lent_id, Expense.tags.ilike('%debt_lent%'))
                        ).scalar() or 0

                        # Extra payments (Annual)
                        m_extra_d_exp = db.session.query(func.sum(DebtPayment.amount)).filter(
                            DebtPayment.user_id == current_user.id,
                            DebtPayment.date >= m_start,
                            DebtPayment.date < m_end
                        ).scalar() or 0

                        m_extra_dr_inc = db.session.query(func.sum(DebtorPayment.amount)).filter(
                            DebtorPayment.user_id == current_user.id,
                            DebtorPayment.date >= m_start,
                            DebtorPayment.date < m_end
                        ).scalar() or 0

                        m_extra_c_inc = db.session.query(func.sum(ContractPayment.amount)).filter(
                            ContractPayment.user_id == current_user.id,
                            ContractPayment.payment_date >= m_start,
                            ContractPayment.payment_date < m_end
                        ).scalar() or 0

                        m_live_recovered = db.session.query(func.sum(Expense.amount)).filter(
                            Expense.user_id == current_user.id,
                            Expense.transaction_type == 'income',
                            Expense.date >= m_start,
                            Expense.date < m_end,
                            or_(
                                Expense.category_id.in_([coll_id, rec_id]),
                                func.coalesce(Expense.tags, '').ilike('%debt_collection%'),
                                func.coalesce(Expense.tags, '').ilike('%bad_debt_recovery%')
                            )
                        ).scalar() or 0

                        y_expense += (m_live_exp + m_extra_d_exp)
                        y_income += (m_live_inc + m_extra_dr_inc + m_extra_c_inc)
                        y_lent += m_live_lent
                        y_recovered += (m_live_recovered + m_extra_dr_inc + m_extra_c_inc)

            annual_data.append({
                'year': year,
                'expense': y_expense,
                'actual_expense': y_expense - y_lent,
                'income': y_income,
                'actual_income': y_income - y_recovered
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
        expenses = Expense.query.filter_by(user_id=current_user.id).order_by(Expense.date.desc()).all()

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
        # Reports Queries with Transfer Filter
        transfer_filter = _get_transfer_filter()
        week_start = now - timedelta(days=7)
        weekly_expenses = db.session.query(
            Category.name, func.sum(Expense.amount)
        ).join(Category).filter(
            Expense.user_id == current_user.id, 
            Expense.date >= week_start, 
            Expense.transaction_type == 'expense',
            ~transfer_filter
        ).group_by(Category.name).all()

        month_start = datetime(now.year, now.month, 1)
        monthly_expenses = db.session.query(
            Category.name, func.sum(Expense.amount)
        ).join(Category).filter(
            Expense.user_id == current_user.id, 
            Expense.date >= month_start, 
            Expense.transaction_type == 'expense',
            ~transfer_filter
        ).group_by(Category.name).all()

        quarter_start = now - timedelta(days=90)
        quarterly_expenses = db.session.query(
            Category.name, func.sum(Expense.amount)
        ).join(Category).filter(
            Expense.user_id == current_user.id, 
            Expense.date >= quarter_start, 
            Expense.transaction_type == 'expense',
            ~transfer_filter
        ).group_by(Category.name).all()

        year_start = datetime(now.year, 1, 1)
        yearly_expenses = db.session.query(
            Category.name, func.sum(Expense.amount)
        ).join(Category).filter(
            Expense.user_id == current_user.id, 
            Expense.date >= year_start, 
            Expense.transaction_type == 'expense',
            ~transfer_filter
        ).group_by(Category.name).all()

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
