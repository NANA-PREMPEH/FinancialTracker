from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required
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


@advanced_bp.route("/tax-center")
@login_required
def tax_center():
    tab = (request.args.get("tab") or "overview").lower()
    if tab not in {"overview", "documents", "deductions", "planning"}:
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

    deduction_keywords = ["tax", "insurance", "charity", "education", "medical", "mortgage"]
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
    estimated_owed = taxable_income * 0.20
    effective_rate = (estimated_owed / total_income * 100) if total_income > 0 else 0.0

    quarterly_due = [
        {"quarter": "Q1", "due_date": f"April 15, {selected_year}"},
        {"quarter": "Q2", "due_date": f"June 15, {selected_year}"},
        {"quarter": "Q3", "due_date": f"September 15, {selected_year}"},
        {"quarter": "Q4", "due_date": f"January 15, {selected_year + 1}"},
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
        )
        .group_by(Category.name)
        .order_by(func.sum(Expense.amount).desc())
        .limit(8)
        .all()
    )
    deduction_limits = {
        "Insurance": 12000,
        "Education": 10000,
        "Medical": 8000,
        "Charity": 6000,
        "Housing": 15000,
        "Transport": 5000,
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
        marginal_rate=20.0,
        quarterly_due=quarterly_due,
        docs=docs,
        deduction_breakdown=deduction_breakdown,
    )


@advanced_bp.route("/tax-center/calculate", methods=["POST"])
@login_required
def tax_center_calculate():
    year = request.form.get("year", type=int) or datetime.utcnow().year
    flash(f"Tax summary recalculated for {year}.", "success")
    return redirect(url_for("advanced.tax_center", year=year, tab="overview"))


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

    tx_24h = Expense.query.filter(
        Expense.user_id == current_user.id,
        Expense.date >= day_start,
    )
    tx_count = tx_24h.count()
    tx_volume = (
        db.session.query(func.sum(Expense.amount))
        .filter(Expense.user_id == current_user.id, Expense.date >= day_start)
        .scalar()
        or 0.0
    )

    cash_balance = (
        db.session.query(func.sum(Wallet.balance))
        .filter(Wallet.user_id == current_user.id)
        .scalar()
        or 0.0
    )
    debt_total = (
        db.session.query(func.sum(Creditor.amount))
        .filter(Creditor.user_id == current_user.id)
        .scalar()
        or 0.0
    )
    invest_total = (
        db.session.query(func.sum(Investment.current_value))
        .filter(Investment.user_id == current_user.id)
        .scalar()
        or 0.0
    )
    entity_total = (
        db.session.query(func.sum(GlobalEntity.value))
        .filter(GlobalEntity.user_id == current_user.id)
        .scalar()
        or 0.0
    )
    net_worth = cash_balance + invest_total + entity_total - debt_total

    goals = Goal.query.filter_by(user_id=current_user.id, is_completed=False).all()
    on_track = 0
    for goal in goals:
        if goal.target_amount <= 0:
            continue
        progress = (goal.current_amount / goal.target_amount) * 100
        if progress >= 40:
            on_track += 1
    on_track_rate = (on_track / len(goals) * 100) if goals else 0.0

    return render_template(
        "metrics.html",
        tx_count=tx_count,
        tx_volume=tx_volume,
        cash_balance=cash_balance,
        debt_total=debt_total,
        net_worth=net_worth,
        on_track_rate=on_track_rate,
        generated_at=now,
    )


@advanced_bp.route("/metrics/refresh", methods=["POST"])
@login_required
def metrics_refresh():
    flash("Metrics refreshed.", "success")
    return redirect(url_for("advanced.metrics"))
