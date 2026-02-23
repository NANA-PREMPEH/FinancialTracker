from flask import Blueprint, render_template, request, redirect, url_for, flash, Response
from flask_login import login_required, current_user
from . import db
from .models import Expense, Wallet, Goal, Creditor, Investment
from datetime import datetime, timedelta
from sqlalchemy import func

newsletter_bp = Blueprint('newsletter', __name__)


@newsletter_bp.route('/newsletter')
@login_required
def newsletter():
    return render_template('newsletter.html')


@newsletter_bp.route('/newsletter/generate', methods=['POST'])
@login_required
def generate_newsletter():
    now = datetime.utcnow()
    month_ago = now - timedelta(days=30)

    income = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == current_user.id, Expense.transaction_type == 'income',
        Expense.date >= month_ago
    ).scalar() or 0
    expenses = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == current_user.id, Expense.transaction_type == 'expense',
        Expense.date >= month_ago
    ).scalar() or 0

    wallets = Wallet.query.filter_by(user_id=current_user.id).all()
    total_balance = sum(w.balance for w in wallets)
    goals = Goal.query.filter_by(user_id=current_user.id, is_completed=False).all()
    debts = Creditor.query.filter_by(user_id=current_user.id).all()
    total_debt = sum(d.amount for d in debts)
    investments = Investment.query.filter_by(user_id=current_user.id).all()
    total_invested = sum(i.current_value for i in investments)

    # Top spending categories
    top_cats = db.session.query(
        db.literal_column('category.name'), func.sum(Expense.amount)
    ).join(Expense.category).filter(
        Expense.user_id == current_user.id, Expense.transaction_type == 'expense',
        Expense.date >= month_ago
    ).group_by('category.name').order_by(func.sum(Expense.amount).desc()).limit(5).all()

    return render_template('newsletter_report.html',
        income=income, expenses=expenses, net=income - expenses,
        total_balance=total_balance, goals=goals, total_debt=total_debt,
        total_invested=total_invested, top_cats=top_cats,
        month_name=now.strftime('%B %Y'), user=current_user)
