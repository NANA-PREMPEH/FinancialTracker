import io
from flask import Blueprint, render_template, request, redirect, url_for, flash, make_response, session
from flask_login import login_required, current_user
from . import db
from .models import Expense, Wallet, Goal, Creditor, Investment, Budget, Category
from .mail import mail, Message
from datetime import datetime, timedelta
from sqlalchemy import func
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

newsletter_bp = Blueprint('newsletter', __name__)


def _gather_report_data(user_id, period_days=30):
    """Gather all financial data for the newsletter report."""
    now = datetime.utcnow()
    period_start = now - timedelta(days=period_days)
    prev_start = period_start - timedelta(days=period_days)

    # Income & expenses
    income = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == user_id, Expense.transaction_type == 'income',
        Expense.date >= period_start
    ).scalar() or 0
    expenses = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == user_id, Expense.transaction_type == 'expense',
        Expense.date >= period_start
    ).scalar() or 0

    # Previous period for comparison
    prev_income = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == user_id, Expense.transaction_type == 'income',
        Expense.date >= prev_start, Expense.date < period_start
    ).scalar() or 0
    prev_expenses = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == user_id, Expense.transaction_type == 'expense',
        Expense.date >= prev_start, Expense.date < period_start
    ).scalar() or 0

    income_change = ((income - prev_income) / prev_income * 100) if prev_income > 0 else 0
    expense_change = ((expenses - prev_expenses) / prev_expenses * 100) if prev_expenses > 0 else 0

    # Wallets
    wallets = Wallet.query.filter_by(user_id=user_id).all()
    total_balance = sum(w.balance for w in wallets)

    # Goals
    goals = Goal.query.filter_by(user_id=user_id, is_completed=False).all()
    completed_goals = Goal.query.filter_by(user_id=user_id, is_completed=True).count()

    # Debts
    debts = Creditor.query.filter(Creditor.user_id == user_id, Creditor.amount > 0).all()
    total_debt = sum(d.amount for d in debts)

    # Investments
    investments = Investment.query.filter_by(user_id=user_id).all()
    total_invested = sum(i.current_value for i in investments)

    # Top spending categories
    top_cats = db.session.query(
        Category.name, func.sum(Expense.amount)
    ).join(Category).filter(
        Expense.user_id == user_id, Expense.transaction_type == 'expense',
        Expense.date >= period_start
    ).group_by(Category.name).order_by(func.sum(Expense.amount).desc()).limit(5).all()

    # Budget adherence
    budgets = Budget.query.filter_by(user_id=user_id, is_active=True).all()
    budget_data = []
    budgets_within = 0
    for b in budgets:
        spent = db.session.query(func.sum(Expense.amount)).filter(
            Expense.user_id == user_id, Expense.category_id == b.category_id,
            Expense.transaction_type == 'expense', Expense.date >= b.start_date
        ).scalar() or 0
        pct = (spent / b.amount * 100) if b.amount > 0 else 0
        within = spent <= b.amount
        if within:
            budgets_within += 1
        budget_data.append({
            'name': b.category.name if b.category else 'Unknown',
            'spent': float(spent), 'limit': float(b.amount),
            'pct': round(min(pct, 150), 1), 'within': within
        })
    budget_adherence = round((budgets_within / len(budgets) * 100), 1) if budgets else 0

    # Savings rate
    savings_rate = ((income - expenses) / income * 100) if income > 0 else 0

    # Spending trend (weekly for the period)
    weekly_spending = db.session.query(
        func.extract('week', Expense.date).label('wk'),
        func.sum(Expense.amount)
    ).filter(
        Expense.user_id == user_id, Expense.transaction_type == 'expense',
        Expense.date >= period_start
    ).group_by('wk').order_by('wk').all()
    weekly_data = [{'week': int(w), 'amount': round(float(a), 2)} for w, a in weekly_spending]

    return {
        'income': float(income), 'expenses': float(expenses),
        'net': float(income - expenses),
        'income_change': round(income_change, 1),
        'expense_change': round(expense_change, 1),
        'savings_rate': round(savings_rate, 1),
        'total_balance': float(total_balance), 'wallets': wallets,
        'goals': goals, 'completed_goals': completed_goals,
        'debts': debts, 'total_debt': float(total_debt),
        'investments': investments, 'total_invested': float(total_invested),
        'top_cats': top_cats,
        'budget_data': budget_data, 'budget_adherence': budget_adherence,
        'weekly_data': weekly_data,
        'period_days': period_days,
        'month_name': now.strftime('%B %Y'),
        'generated_at': now,
    }


def _build_pdf(data, user):
    """Generate PDF newsletter report."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5 * inch, bottomMargin=0.5 * inch)
    styles = getSampleStyleSheet()
    elements = []

    title_style = ParagraphStyle('NLTitle', parent=styles['Title'], fontSize=20, spaceAfter=6)
    elements.append(Paragraph(f"Financial Report — {data['month_name']}", title_style))
    elements.append(Paragraph(
        f"Prepared for {user.name} on {data['generated_at'].strftime('%d %B %Y')}",
        styles['Normal']
    ))
    elements.append(Spacer(1, 0.3 * inch))

    # Financial Summary
    elements.append(Paragraph("Financial Summary", styles['Heading2']))
    summary = [
        ["Metric", "Amount (GHS)", "Change"],
        ["Income", f"{data['income']:,.2f}", f"{data['income_change']:+.1f}%"],
        ["Expenses", f"{data['expenses']:,.2f}", f"{data['expense_change']:+.1f}%"],
        ["Net Savings", f"{data['net']:,.2f}", f"{data['savings_rate']:.1f}% rate"],
        ["Total Balance", f"{data['total_balance']:,.2f}", ""],
        ["Total Debt", f"{data['total_debt']:,.2f}", ""],
        ["Investments", f"{data['total_invested']:,.2f}", ""],
    ]
    t = Table(summary, colWidths=[2 * inch, 2 * inch, 1.5 * inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 0.3 * inch))

    # Top Categories
    if data['top_cats']:
        elements.append(Paragraph("Top Spending Categories", styles['Heading2']))
        cat_data = [["Category", "Amount (GHS)"]]
        for name, amt in data['top_cats']:
            cat_data.append([name, f"{float(amt):,.2f}"])
        ct = Table(cat_data, colWidths=[3 * inch, 2.5 * inch])
        ct.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        elements.append(ct)
        elements.append(Spacer(1, 0.3 * inch))

    # Budget Adherence
    if data['budget_data']:
        elements.append(Paragraph(f"Budget Adherence: {data['budget_adherence']}%", styles['Heading2']))
        bd = [["Budget", "Spent (GHS)", "Limit (GHS)", "Status"]]
        for b in data['budget_data']:
            bd.append([b['name'], f"{b['spent']:,.2f}", f"{b['limit']:,.2f}",
                       "Within" if b['within'] else "Over"])
        bt = Table(bd, colWidths=[1.8 * inch, 1.3 * inch, 1.3 * inch, 1.1 * inch])
        bt.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        elements.append(bt)
        elements.append(Spacer(1, 0.3 * inch))

    # Goals
    if data['goals']:
        elements.append(Paragraph("Active Goals", styles['Heading2']))
        gd = [["Goal", "Current (GHS)", "Target (GHS)", "Progress"]]
        for g in data['goals']:
            pct = (g.current_amount / g.target_amount * 100) if g.target_amount > 0 else 0
            gd.append([g.name, f"{g.current_amount:,.2f}", f"{g.target_amount:,.2f}", f"{pct:.1f}%"])
        gt = Table(gd, colWidths=[2 * inch, 1.3 * inch, 1.3 * inch, 0.9 * inch])
        gt.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        elements.append(gt)
        elements.append(Spacer(1, 0.3 * inch))

    # Debt Summary
    if data['debts']:
        elements.append(Paragraph("Debt Summary", styles['Heading2']))
        dd = [["Creditor", "Amount (GHS)", "Rate", "Type"]]
        for d in data['debts']:
            dd.append([d.name, f"{d.amount:,.2f}", f"{d.interest_rate:.1f}%", d.debt_type or '-'])
        dt2 = Table(dd, colWidths=[2 * inch, 1.3 * inch, 0.8 * inch, 1.4 * inch])
        dt2.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        elements.append(dt2)

    elements.append(Spacer(1, 0.5 * inch))
    elements.append(Paragraph(
        f"Generated by FinTracker on {data['generated_at'].strftime('%d %B %Y at %H:%M UTC')}",
        ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, textColor=colors.grey)
    ))

    doc.build(elements)
    buffer.seek(0)
    return buffer


@newsletter_bp.route('/newsletter')
@login_required
def newsletter():
    prefs = session.get('newsletter_prefs', {
        'frequency': 'monthly',
        'sections': ['summary', 'categories', 'budgets', 'goals', 'debts', 'investments', 'trends']
    })
    return render_template('newsletter.html', prefs=prefs)


@newsletter_bp.route('/newsletter/preferences', methods=['POST'])
@login_required
def newsletter_preferences():
    frequency = request.form.get('frequency', 'monthly')
    if frequency not in ('weekly', 'monthly'):
        frequency = 'monthly'
    sections = request.form.getlist('sections')
    if not sections:
        sections = ['summary']
    session['newsletter_prefs'] = {'frequency': frequency, 'sections': sections}
    flash('Newsletter preferences saved.', 'success')
    return redirect(url_for('newsletter.newsletter'))


@newsletter_bp.route('/newsletter/generate', methods=['POST'])
@login_required
def generate_newsletter():
    prefs = session.get('newsletter_prefs', {
        'frequency': 'monthly',
        'sections': ['summary', 'categories', 'budgets', 'goals', 'debts', 'investments', 'trends']
    })
    period_days = 7 if prefs.get('frequency') == 'weekly' else 30
    data = _gather_report_data(current_user.id, period_days)
    data['sections'] = prefs.get('sections', [])

    return render_template('newsletter_report.html', user=current_user, **data)


@newsletter_bp.route('/newsletter/download')
@login_required
def newsletter_download():
    prefs = session.get('newsletter_prefs', {'frequency': 'monthly'})
    period_days = 7 if prefs.get('frequency') == 'weekly' else 30
    data = _gather_report_data(current_user.id, period_days)
    buffer = _build_pdf(data, current_user)

    response = make_response(buffer.read())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = (
        f'attachment; filename=financial_report_{data["month_name"].replace(" ", "_")}.pdf'
    )
    return response


@newsletter_bp.route('/newsletter/email', methods=['POST'])
@login_required
def newsletter_email():
    """Send the financial report to the user's email."""
    prefs = session.get('newsletter_prefs', {'frequency': 'monthly'})
    period_days = 7 if prefs.get('frequency') == 'weekly' else 30
    data = _gather_report_data(current_user.id, period_days)
    data['sections'] = prefs.get('sections', [])

    # Generate PDF attachment
    pdf_buffer = _build_pdf(data, current_user)

    try:
        msg = Message(
            f'Your Financial Report — {data["month_name"]}',
            recipients=[current_user.email]
        )
        msg.html = render_template('newsletter_report.html', user=current_user, _email=True, **data)
        msg.attach(
            f'financial_report_{data["month_name"].replace(" ", "_")}.pdf',
            'application/pdf',
            pdf_buffer.read()
        )
        mail.send(msg)
        flash('Financial report sent to your email!', 'success')
    except Exception as e:
        flash(f'Failed to send email. Please check mail settings.', 'error')

    return redirect(url_for('newsletter.newsletter'))
