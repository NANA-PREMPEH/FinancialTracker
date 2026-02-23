from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from . import db
from .models import BankReconciliation, ImportHistory, Wallet, Expense, Category
from datetime import datetime
import csv
import io

banking_bp = Blueprint('banking', __name__)


@banking_bp.route('/banking')
@login_required
def banking_overview():
    wallets = Wallet.query.filter_by(user_id=current_user.id).all()
    reconciliations = BankReconciliation.query.filter_by(user_id=current_user.id).order_by(BankReconciliation.date.desc()).limit(20).all()
    imports = ImportHistory.query.filter_by(user_id=current_user.id).order_by(ImportHistory.date.desc()).limit(20).all()
    return render_template('banking.html', wallets=wallets, reconciliations=reconciliations, imports=imports)


@banking_bp.route('/banking/reconcile', methods=['POST'])
@login_required
def reconcile():
    wallet_id = int(request.form.get('wallet_id', 0))
    statement_balance = float(request.form.get('statement_balance', 0))
    wallet = Wallet.query.get_or_404(wallet_id)

    status = 'reconciled' if abs(wallet.balance - statement_balance) < 0.01 else 'discrepancy'
    rec = BankReconciliation(
        user_id=current_user.id,
        wallet_id=wallet_id,
        statement_balance=statement_balance,
        reconciled_balance=wallet.balance,
        date=datetime.utcnow(),
        status=status,
        notes=request.form.get('notes', '').strip() or None,
    )
    db.session.add(rec)
    db.session.commit()

    if status == 'reconciled':
        flash('Account reconciled successfully.', 'success')
    else:
        diff = abs(wallet.balance - statement_balance)
        flash(f'Discrepancy of GHS {diff:.2f} found between app balance and statement.', 'error')
    return redirect(url_for('banking.banking_overview'))


@banking_bp.route('/banking/import', methods=['POST'])
@login_required
def import_transactions():
    file = request.files.get('file')
    wallet_id = int(request.form.get('wallet_id', 0))
    if not file or not file.filename.endswith('.csv'):
        flash('Please upload a CSV file.', 'error')
        return redirect(url_for('banking.banking_overview'))

    wallet = Wallet.query.get_or_404(wallet_id)
    default_cat = Category.query.filter_by(name='Other').first() or Category.query.first()

    try:
        content = file.stream.read().decode('utf-8')
        reader = csv.DictReader(io.StringIO(content))
        count = 0
        for row in reader:
            # Try common CSV column names
            amount = float(row.get('Amount', row.get('amount', row.get('Value', 0))))
            desc = row.get('Description', row.get('description', row.get('Narration', 'Imported')))
            date_str = row.get('Date', row.get('date', row.get('Transaction Date', '')))

            try:
                date = datetime.strptime(date_str.strip(), '%Y-%m-%d')
            except (ValueError, AttributeError):
                try:
                    date = datetime.strptime(date_str.strip(), '%d/%m/%Y')
                except (ValueError, AttributeError):
                    date = datetime.utcnow()

            t_type = 'income' if amount > 0 else 'expense'
            expense = Expense(
                user_id=current_user.id,
                amount=abs(amount),
                description=str(desc).strip(),
                date=date,
                category_id=default_cat.id,
                wallet_id=wallet.id,
                transaction_type=t_type,
                tags='imported',
            )
            db.session.add(expense)
            if t_type == 'income':
                wallet.balance += abs(amount)
            else:
                wallet.balance -= abs(amount)
            count += 1

        history = ImportHistory(
            user_id=current_user.id,
            filename=file.filename,
            records_imported=count,
            status='completed',
        )
        db.session.add(history)
        db.session.commit()
        flash(f'Successfully imported {count} transactions.', 'success')
    except Exception as e:
        db.session.rollback()
        history = ImportHistory(
            user_id=current_user.id, filename=file.filename,
            records_imported=0, status='failed', notes=str(e)
        )
        db.session.add(history)
        db.session.commit()
        flash(f'Import failed: {str(e)}', 'error')

    return redirect(url_for('banking.banking_overview'))
