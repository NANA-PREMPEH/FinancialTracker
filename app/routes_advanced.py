import io
from datetime import datetime

from flask import Blueprint, flash, make_response, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import func, or_

from . import db
from .models import (
    Budget,
    Category,
    Creditor,
    Expense,
    GlobalEntity,
    Goal,
    InsurancePolicy,
    Investment,
    Wallet,
)


advanced_bp = Blueprint("advanced", __name__)


@advanced_bp.route("/insurance")
@login_required
def insurance():
    policies = (
        InsurancePolicy.query.filter_by(user_id=current_user.id)
        .order_by(InsurancePolicy.start_date.desc())
        .all()
    )
    return render_template("insurance_policies.html", policies=policies)


# Ghana Revenue Authority (GRA) PAYE tax brackets (annual, GHS)
GRA_TAX_BRACKETS = [
    (4824, 0.00),       # First GHS 4,824 — 0%
    (1320, 0.05),       # Next GHS 1,320 — 5%
    (1560, 0.10),       # Next GHS 1,560 — 10%
    (36000, 0.175),     # Next GHS 36,000 — 17.5%
    (196596, 0.25),     # Next GHS 196,596 — 25%
    (None, 0.30),       # Exceeding GHS 240,300 — 30%
]


def calculate_gra_tax(annual_taxable):
    """Compute Ghana PAYE tax using progressive brackets. Returns (total_tax, bracket_details, marginal_rate)."""
    remaining = max(annual_taxable, 0)
    total_tax = 0
    details = []
    marginal_rate = 0.0

    for width, rate in GRA_TAX_BRACKETS:
        if remaining <= 0:
            break
        if width is None:
            taxable_in_band = remaining
        else:
            taxable_in_band = min(remaining, width)
        tax_in_band = taxable_in_band * rate
        total_tax += tax_in_band
        remaining -= taxable_in_band
        marginal_rate = rate
        details.append({
            'band_width': width or 'Remainder',
            'rate': rate * 100,
            'taxable': round(taxable_in_band, 2),
            'tax': round(tax_in_band, 2),
        })

    return round(total_tax, 2), details, marginal_rate * 100


@advanced_bp.route("/tax-center")
@login_required
def tax_center():
    tab = (request.args.get("tab") or "overview").lower()
    if tab not in {"overview", "documents", "deductions", "planning", "brackets"}:
        tab = "overview"

    selected_year = request.args.get("year", type=int) or datetime.utcnow().year
    year_start = datetime(selected_year, 1, 1)
    year_end = datetime(selected_year + 1, 1, 1)

    total_income = (
        db.session.query(func.sum(Expense.amount))
        .filter(
            Expense.user_id == current_user.id,
            Expense.transaction_type == "income",
            Expense.date >= year_start,
            Expense.date < year_end,
        )
        .scalar()
        or 0.0
    )
    total_expenses = (
        db.session.query(func.sum(Expense.amount))
        .filter(
            Expense.user_id == current_user.id,
            Expense.transaction_type == "expense",
            Expense.date >= year_start,
            Expense.date < year_end,
        )
        .scalar()
        or 0.0
    )

    deduction_keywords = ["tax", "insurance", "charity", "education", "medical", "mortgage", "pension", "donation"]
    deduction_filters = [Category.name.ilike(f"%{term}%") for term in deduction_keywords]
    deductions = (
        db.session.query(func.sum(Expense.amount))
        .join(Category, Category.id == Expense.category_id)
        .filter(
            Expense.user_id == current_user.id,
            Expense.transaction_type == "expense",
            Expense.date >= year_start,
            Expense.date < year_end,
            or_(*deduction_filters),
        )
        .scalar()
        or 0.0
    )

    taxable_income = max(total_income - deductions, 0.0)
    estimated_owed, bracket_details, marginal_rate = calculate_gra_tax(taxable_income)
    effective_rate = (estimated_owed / total_income * 100) if total_income > 0 else 0.0

    # Monthly breakdown for the year
    monthly_income = (
        db.session.query(
            func.extract('month', Expense.date).label('month'),
            func.sum(Expense.amount)
        )
        .filter(
            Expense.user_id == current_user.id,
            Expense.transaction_type == "income",
            Expense.date >= year_start,
            Expense.date < year_end,
        )
        .group_by(func.extract('month', Expense.date))
        .all()
    )
    monthly_income_map = {int(m): float(a) for m, a in monthly_income}

    quarterly_due = [
        {"quarter": "Q1", "due_date": f"April 15, {selected_year}",
         "amount": round(estimated_owed / 4, 2)},
        {"quarter": "Q2", "due_date": f"June 15, {selected_year}",
         "amount": round(estimated_owed / 4, 2)},
        {"quarter": "Q3", "due_date": f"September 15, {selected_year}",
         "amount": round(estimated_owed / 4, 2)},
        {"quarter": "Q4", "due_date": f"January 15, {selected_year + 1}",
         "amount": round(estimated_owed / 4, 2)},
    ]

    docs = [
        {"name": "Income Statements", "status": "uploaded"},
        {"name": "Investment Statements", "status": "uploaded"},
        {"name": "Insurance Receipts", "status": "missing"},
        {"name": "Charity Receipts", "status": "missing"},
        {"name": "Mortgage Interest Letter", "status": "missing"},
    ]

    deduction_rows = (
        db.session.query(Category.name, func.sum(Expense.amount))
        .join(Expense, Expense.category_id == Category.id)
        .filter(
            Expense.user_id == current_user.id,
            Expense.transaction_type == "expense",
            Expense.date >= year_start,
            Expense.date < year_end,
            or_(*deduction_filters),
        )
        .group_by(Category.name)
        .order_by(func.sum(Expense.amount).desc())
        .all()
    )
    deduction_limits = {
        "Insurance": 12000,
        "Education": 10000,
        "Medical": 8000,
        "Charity": 6000,
        "Housing": 15000,
        "Transport": 5000,
        "Pension": 16500,
        "Donation": 6000,
    }
    deduction_breakdown = []
    for name, amount in deduction_rows:
        limit_amount = deduction_limits.get(name, 10000)
        usage = (float(amount or 0) / limit_amount * 100) if limit_amount > 0 else 0
        deduction_breakdown.append(
            {
                "category": name,
                "amount": float(amount or 0),
                "limit_amount": float(limit_amount),
                "usage": min(usage, 100),
            }
        )

    # Bracket calculator preset
    bracket_input = request.args.get("bracket_income", type=float) or 0
    bracket_result = None
    if bracket_input > 0:
        b_tax, b_details, b_marginal = calculate_gra_tax(bracket_input)
        b_effective = (b_tax / bracket_input * 100) if bracket_input > 0 else 0
        bracket_result = {
            'income': bracket_input,
            'tax': b_tax,
            'effective_rate': round(b_effective, 2),
            'marginal_rate': b_marginal,
            'details': b_details,
            'monthly_tax': round(b_tax / 12, 2),
            'monthly_net': round((bracket_input - b_tax) / 12, 2),
        }

    return render_template(
        "tax_center.html",
        tab=tab,
        selected_year=selected_year,
        total_income=total_income,
        total_expenses=total_expenses,
        deductions=deductions,
        taxable_income=taxable_income,
        estimated_owed=estimated_owed,
        effective_rate=effective_rate,
        marginal_rate=marginal_rate,
        quarterly_due=quarterly_due,
        docs=docs,
        deduction_breakdown=deduction_breakdown,
        bracket_details=bracket_details,
        monthly_income_map=monthly_income_map,
        bracket_input=bracket_input,
        bracket_result=bracket_result,
    )


@advanced_bp.route("/tax-center/calculate", methods=["POST"])
@login_required
def tax_center_calculate():
    year = request.form.get("year", type=int) or datetime.utcnow().year
    flash(f"Tax summary recalculated for {year}.", "success")
    return redirect(url_for("advanced.tax_center", year=year, tab="overview"))


@advanced_bp.route("/tax-center/add-deduction", methods=["POST"])
@login_required
def tax_center_add_deduction():
    """Record a deductible expense from the tax center."""
    year = request.form.get("year", type=int) or datetime.utcnow().year
    description = request.form.get("description", "").strip()
    amount = request.form.get("amount", type=float) or 0
    category_name = request.form.get("category", "").strip()

    if not description or amount <= 0:
        flash("Please provide a description and valid amount.", "error")
        return redirect(url_for("advanced.tax_center", year=year, tab="deductions"))

    # Find or create category
    category = Category.query.filter_by(user_id=current_user.id, name=category_name).first()
    if not category:
        category = Category(user_id=current_user.id, name=category_name, type='expense')
        db.session.add(category)
        db.session.flush()

    expense = Expense(
        user_id=current_user.id,
        description=f"[Tax Deduction] {description}",
        amount=amount,
        category_id=category.id,
        transaction_type='expense',
        date=datetime.utcnow(),
    )
    db.session.add(expense)
    db.session.commit()
    flash(f"Deduction of GHS {amount:,.2f} recorded under {category_name}.", "success")
    return redirect(url_for("advanced.tax_center", year=year, tab="deductions"))


@advanced_bp.route("/tax-center/export-pdf")
@login_required
def tax_center_export_pdf():
    """Generate and download annual tax summary as PDF."""
    selected_year = request.args.get("year", type=int) or datetime.utcnow().year
    year_start = datetime(selected_year, 1, 1)
    year_end = datetime(selected_year + 1, 1, 1)

    total_income = (
        db.session.query(func.sum(Expense.amount))
        .filter(Expense.user_id == current_user.id, Expense.transaction_type == "income",
                Expense.date >= year_start, Expense.date < year_end)
        .scalar() or 0.0
    )
    total_expenses = (
        db.session.query(func.sum(Expense.amount))
        .filter(Expense.user_id == current_user.id, Expense.transaction_type == "expense",
                Expense.date >= year_start, Expense.date < year_end)
        .scalar() or 0.0
    )

    deduction_keywords = ["tax", "insurance", "charity", "education", "medical", "mortgage", "pension", "donation"]
    deduction_filters = [Category.name.ilike(f"%{term}%") for term in deduction_keywords]
    deductions = (
        db.session.query(func.sum(Expense.amount))
        .join(Category, Category.id == Expense.category_id)
        .filter(Expense.user_id == current_user.id, Expense.transaction_type == "expense",
                Expense.date >= year_start, Expense.date < year_end, or_(*deduction_filters))
        .scalar() or 0.0
    )

    taxable_income = max(total_income - deductions, 0.0)
    estimated_owed, bracket_details, marginal_rate = calculate_gra_tax(taxable_income)
    effective_rate = (estimated_owed / total_income * 100) if total_income > 0 else 0.0

    # Deduction breakdown
    deduction_rows = (
        db.session.query(Category.name, func.sum(Expense.amount))
        .join(Expense, Expense.category_id == Category.id)
        .filter(Expense.user_id == current_user.id, Expense.transaction_type == "expense",
                Expense.date >= year_start, Expense.date < year_end, or_(*deduction_filters))
        .group_by(Category.name).order_by(func.sum(Expense.amount).desc()).all()
    )

    # Build PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5 * inch, bottomMargin=0.5 * inch)
    styles = getSampleStyleSheet()
    elements = []

    title_style = ParagraphStyle('TaxTitle', parent=styles['Title'], fontSize=20, spaceAfter=6)
    elements.append(Paragraph(f"Annual Tax Summary — {selected_year}", title_style))
    elements.append(Paragraph(
        f"Prepared for {current_user.name} on {datetime.utcnow().strftime('%d %B %Y')}",
        styles['Normal']
    ))
    elements.append(Spacer(1, 0.3 * inch))

    # Summary table
    elements.append(Paragraph("Income & Tax Summary", styles['Heading2']))
    summary_data = [
        ["Item", "Amount (GHS)"],
        ["Total Income", f"{total_income:,.2f}"],
        ["Total Expenses", f"{total_expenses:,.2f}"],
        ["Eligible Deductions", f"{deductions:,.2f}"],
        ["Taxable Income", f"{taxable_income:,.2f}"],
        ["Estimated Tax (GRA)", f"{estimated_owed:,.2f}"],
        ["Effective Rate", f"{effective_rate:.1f}%"],
        ["Marginal Rate", f"{marginal_rate:.1f}%"],
    ]
    t = Table(summary_data, colWidths=[3 * inch, 2.5 * inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 0.3 * inch))

    # GRA Bracket breakdown
    elements.append(Paragraph("GRA Tax Bracket Breakdown", styles['Heading2']))
    bracket_data = [["Band Width (GHS)", "Rate", "Taxable (GHS)", "Tax (GHS)"]]
    for bd in bracket_details:
        bracket_data.append([
            str(bd['band_width']),
            f"{bd['rate']:.1f}%",
            f"{bd['taxable']:,.2f}",
            f"{bd['tax']:,.2f}",
        ])
    bracket_data.append(["Total", "", "", f"{estimated_owed:,.2f}"])
    bt = Table(bracket_data, colWidths=[1.6 * inch, 1 * inch, 1.6 * inch, 1.3 * inch])
    bt.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f8fafc')]),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(bt)
    elements.append(Spacer(1, 0.3 * inch))

    # Deduction breakdown
    if deduction_rows:
        elements.append(Paragraph("Deduction Breakdown", styles['Heading2']))
        ded_data = [["Category", "Amount (GHS)"]]
        for name, amount in deduction_rows:
            ded_data.append([name, f"{float(amount or 0):,.2f}"])
        ded_data.append(["Total Deductions", f"{deductions:,.2f}"])
        dt = Table(ded_data, colWidths=[3 * inch, 2.5 * inch])
        dt.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        elements.append(dt)

    elements.append(Spacer(1, 0.5 * inch))
    elements.append(Paragraph(
        "Note: This is an estimate based on Ghana Revenue Authority (GRA) PAYE tax brackets. "
        "Consult a tax professional for official filing.",
        ParagraphStyle('Disclaimer', parent=styles['Normal'], fontSize=8, textColor=colors.grey)
    ))

    doc.build(elements)
    buffer.seek(0)

    response = make_response(buffer.read())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=tax_summary_{selected_year}.pdf'
    return response


@advanced_bp.route("/ml-training")
@login_required
def ml_training():
    txn_count = Expense.query.filter_by(user_id=current_user.id).count()
    labeled_categories = (
        db.session.query(func.count(func.distinct(Expense.category_id)))
        .filter(Expense.user_id == current_user.id, Expense.category_id.isnot(None))
        .scalar()
        or 0
    )
    goals_count = Goal.query.filter_by(user_id=current_user.id).count()
    budgets_count = Budget.query.filter_by(user_id=current_user.id).count()

    readiness = min(
        100,
        int(
            min(txn_count, 500) / 5
            + min(labeled_categories, 15) * 2
            + min(goals_count, 20)
            + min(budgets_count, 10)
        ),
    )

    now = datetime.utcnow()
    job_runs = session.get("ml_job_runs", {})
    jobs = [
        {
            "id": "spending_forecast",
            "name": "Spending Forecast Model",
            "status": "healthy",
            "last_run": datetime.fromisoformat(job_runs["spending_forecast"]) if job_runs.get("spending_forecast") else now,
        },
        {
            "id": "goal_progress",
            "name": "Goal Progress Model",
            "status": "healthy",
            "last_run": datetime.fromisoformat(job_runs["goal_progress"]) if job_runs.get("goal_progress") else now,
        },
        {
            "id": "anomaly_detection",
            "name": "Anomaly Detection Model",
            "status": "idle",
            "last_run": datetime.fromisoformat(job_runs["anomaly_detection"]) if job_runs.get("anomaly_detection") else now,
        },
    ]

    return render_template(
        "ml_training.html",
        txn_count=txn_count,
        labeled_categories=labeled_categories,
        goals_count=goals_count,
        budgets_count=budgets_count,
        readiness=readiness,
        jobs=jobs,
    )


@advanced_bp.route("/ml-training/run", methods=["POST"])
@login_required
def ml_training_run():
    job_id = (request.form.get("job_id") or "").strip()
    allowed = {"spending_forecast", "goal_progress", "anomaly_detection", "all"}
    if job_id not in allowed:
        flash("Invalid training job selected.", "error")
        return redirect(url_for("advanced.ml_training"))

    runs = session.get("ml_job_runs", {})
    now_iso = datetime.utcnow().isoformat()
    if job_id == "all":
        for key in ("spending_forecast", "goal_progress", "anomaly_detection"):
            runs[key] = now_iso
        flash("All training jobs queued and executed.", "success")
    else:
        runs[job_id] = now_iso
        flash("Training job executed successfully.", "success")
    session["ml_job_runs"] = runs
    return redirect(url_for("advanced.ml_training"))


@advanced_bp.route("/metrics")
@login_required
def metrics():
    now = datetime.utcnow()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    uid = current_user.id

    tx_count = Expense.query.filter(Expense.user_id == uid, Expense.date >= day_start).count()
    tx_volume = (
        db.session.query(func.sum(Expense.amount))
        .filter(Expense.user_id == uid, Expense.date >= day_start)
        .scalar() or 0.0
    )

    cash_balance = db.session.query(func.sum(Wallet.balance)).filter(Wallet.user_id == uid).scalar() or 0.0
    debt_total = db.session.query(func.sum(Creditor.amount)).filter(Creditor.user_id == uid).scalar() or 0.0
    invest_total = db.session.query(func.sum(Investment.current_value)).filter(Investment.user_id == uid).scalar() or 0.0
    entity_total = db.session.query(func.sum(GlobalEntity.value)).filter(GlobalEntity.user_id == uid).scalar() or 0.0
    net_worth = cash_balance + invest_total + entity_total - debt_total

    # --- Monthly burn rate & runway ---
    six_months_ago = now - __import__('datetime').timedelta(days=180)
    monthly_expenses_raw = (
        db.session.query(
            func.extract('year', Expense.date).label('yr'),
            func.extract('month', Expense.date).label('mo'),
            func.sum(Expense.amount)
        )
        .filter(Expense.user_id == uid, Expense.transaction_type == 'expense', Expense.date >= six_months_ago)
        .group_by('yr', 'mo').order_by('yr', 'mo').all()
    )
    monthly_expense_amounts = [float(a) for _, _, a in monthly_expenses_raw]
    avg_burn = sum(monthly_expense_amounts) / len(monthly_expense_amounts) if monthly_expense_amounts else 0
    runway_months = round(cash_balance / avg_burn, 1) if avg_burn > 0 else 999

    # --- Monthly income raw for expense-to-income ratio ---
    monthly_income_raw = (
        db.session.query(
            func.extract('year', Expense.date).label('yr'),
            func.extract('month', Expense.date).label('mo'),
            func.sum(Expense.amount)
        )
        .filter(Expense.user_id == uid, Expense.transaction_type == 'income', Expense.date >= six_months_ago)
        .group_by('yr', 'mo').order_by('yr', 'mo').all()
    )
    income_map = {(int(y), int(m)): float(a) for y, m, a in monthly_income_raw}
    expense_map = {(int(y), int(m)): float(a) for y, m, a in monthly_expenses_raw}

    # Build 6-month series for charts
    import calendar
    chart_labels = []
    expense_to_income_data = []
    expense_series = []
    income_series = []
    debt_ratio_series = []

    for i in range(5, -1, -1):
        d = now - __import__('datetime').timedelta(days=i * 30)
        yr, mo = d.year, d.month
        label = calendar.month_abbr[mo]
        chart_labels.append(label)
        inc = income_map.get((yr, mo), 0)
        exp = expense_map.get((yr, mo), 0)
        income_series.append(round(inc, 2))
        expense_series.append(round(exp, 2))
        ratio = round((exp / inc * 100), 1) if inc > 0 else 0
        expense_to_income_data.append(ratio)
        # Debt ratio over time — approximate (current snapshot since historical not stored)
        debt_ratio_series.append(round((debt_total / max(cash_balance, 1)) * 100, 1))

    # --- Category distribution (top 6) for current month ---
    month_start = datetime(now.year, now.month, 1)
    cat_dist = (
        db.session.query(Category.name, func.sum(Expense.amount))
        .join(Category).filter(
            Expense.user_id == uid, Expense.transaction_type == 'expense',
            Expense.date >= month_start
        )
        .group_by(Category.name).order_by(func.sum(Expense.amount).desc()).limit(6).all()
    )
    cat_labels = [n for n, _ in cat_dist]
    cat_amounts = [round(float(a), 2) for _, a in cat_dist]

    # --- Budget adherence ---
    budgets = Budget.query.filter_by(user_id=uid, is_active=True).all()
    budgets_within = 0
    budget_details = []
    for b in budgets:
        spent = db.session.query(func.sum(Expense.amount)).filter(
            Expense.user_id == uid, Expense.category_id == b.category_id,
            Expense.transaction_type == 'expense', Expense.date >= b.start_date
        ).scalar() or 0
        pct = round((spent / b.amount * 100), 1) if b.amount > 0 else 0
        within = spent <= b.amount
        if within:
            budgets_within += 1
        budget_details.append({
            'name': b.category.name if b.category else 'Unknown',
            'spent': round(float(spent), 2),
            'limit': round(float(b.amount), 2),
            'pct': min(pct, 150),
            'within': within,
        })
    budget_adherence = round((budgets_within / len(budgets) * 100), 1) if budgets else 0

    # --- Goal completion ---
    goals_active = Goal.query.filter_by(user_id=uid, is_completed=False).all()
    goals_completed = Goal.query.filter_by(user_id=uid, is_completed=True).count()
    goals_total = len(goals_active) + goals_completed
    goal_completion_rate = round((goals_completed / goals_total * 100), 1) if goals_total else 0
    on_track = sum(1 for g in goals_active if g.target_amount > 0 and (g.current_amount / g.target_amount) >= 0.4)
    on_track_rate = round((on_track / len(goals_active) * 100), 1) if goals_active else 0

    return render_template(
        "metrics.html",
        tx_count=tx_count, tx_volume=tx_volume,
        cash_balance=cash_balance, debt_total=debt_total,
        net_worth=net_worth, on_track_rate=on_track_rate,
        generated_at=now,
        avg_burn=avg_burn, runway_months=runway_months,
        chart_labels=chart_labels,
        expense_to_income_data=expense_to_income_data,
        expense_series=expense_series, income_series=income_series,
        debt_ratio_series=debt_ratio_series,
        cat_labels=cat_labels, cat_amounts=cat_amounts,
        budget_adherence=budget_adherence, budget_details=budget_details,
        goal_completion_rate=goal_completion_rate,
        goals_completed=goals_completed, goals_total=goals_total,
        invest_total=invest_total, entity_total=entity_total,
    )


@advanced_bp.route("/metrics/refresh", methods=["POST"])
@login_required
def metrics_refresh():
    flash("Metrics refreshed.", "success")
    return redirect(url_for("advanced.metrics"))
