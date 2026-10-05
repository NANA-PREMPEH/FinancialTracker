from datetime import datetime
from decimal import Decimal
from math import isfinite

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from . import db
from .models import (CapitalAllocation, ChartOfAccount, EquityCapital, EquityTransaction,
                     Expense, JournalEntry, Project, ProjectCategory, Wallet, get_or_seed_project_categories)


equity_bp = Blueprint('equity', __name__, url_prefix='/equity')
TRANSACTION_TYPES = {'injection', 'partner_contribution', 'drawing'}
ALLOCATION_TYPES = {'project_funding', 'reinvestment'}
TRANSACTION_TYPE_CHOICES = (
    ('injection', 'Owner injection'),
    ('partner_contribution', 'Partner contribution'),
    ('drawing', 'Owner drawing'),
)
ALLOCATION_TYPE_CHOICES = (
    ('project_funding', 'Fund a project'),
    ('reinvestment', 'Earmark reinvestment'),
)


def _equity_for_user(equity_id):
    return EquityCapital.query.filter_by(id=equity_id, user_id=current_user.id).first_or_404()


def _overview_totals(records):
    """Return all aggregate balances displayed on the equity overview."""
    return {
        'initial': sum(record.initial_capital or 0 for record in records),
        'injections': sum(record.total_additional_injections for record in records),
        'partners': sum(record.total_partner_contributions for record in records),
        'drawings': sum(record.total_drawings for record in records),
        'contributed': sum(record.contributed_capital for record in records),
        'retained': sum(record.retained_earnings for record in records),
        'equity': sum(record.total_equity for record in records),
        'allocated': sum(record.total_allocated for record in records),
        'available': sum(record.unallocated_capital for record in records),
    }


def _record_journal_entry(transaction, category_name):
    """Post an external equity movement using existing accounts or safe defaults."""
    cash = (ChartOfAccount.query.filter_by(user_id=current_user.id, code='1000', account_type='Asset').first()
            or ChartOfAccount.query.filter_by(user_id=current_user.id, name='Equity Cash', account_type='Asset').first()
            or ChartOfAccount.query.filter_by(user_id=current_user.id, account_type='Asset').first())
    equity = (ChartOfAccount.query.filter_by(user_id=current_user.id, code='3000', account_type='Equity').first()
              or ChartOfAccount.query.filter_by(user_id=current_user.id, name='Owner Equity', account_type='Equity').first()
              or ChartOfAccount.query.filter_by(user_id=current_user.id, account_type='Equity').first())
    if not cash:
        cash = ChartOfAccount(user_id=current_user.id, code='1000', name='Equity Cash', account_type='Asset')
        db.session.add(cash)
    if not equity:
        equity = ChartOfAccount(user_id=current_user.id, code='3000', name='Owner Equity', account_type='Equity')
        db.session.add(equity)
    db.session.flush()
    if transaction.is_inflow:
        debit, credit = cash, equity
    else:
        debit, credit = equity, cash
    entry = JournalEntry(user_id=current_user.id, date=transaction.date,
        description=f'Equity {transaction.transaction_type}: {transaction.description or category_name}',
        debit_account_id=debit.id, credit_account_id=credit.id, amount=transaction.amount,
        reference=f'EQ-{transaction.id}')
    debit.balance += entry.amount
    credit.balance -= entry.amount
    db.session.add(entry)
    db.session.flush()
    transaction.journal_entry_id = entry.id


def _reverse_journal_entry(entry):
    if not entry:
        return
    debit = ChartOfAccount.query.filter_by(id=entry.debit_account_id, user_id=current_user.id).first()
    credit = ChartOfAccount.query.filter_by(id=entry.credit_account_id, user_id=current_user.id).first()
    if debit:
        debit.balance -= entry.amount
    if credit:
        credit.balance += entry.amount
    db.session.delete(entry)


@equity_bp.route('/')
@login_required
def equity_overview():
    categories = get_or_seed_project_categories(current_user.id)
    records = []
    for category in categories:
        record = EquityCapital.query.filter_by(user_id=current_user.id, category_id=category.id).first()
        if not record:
            record = EquityCapital(user_id=current_user.id, category_id=category.id)
            db.session.add(record)
        records.append(record)
    try:
        db.session.commit()
    except IntegrityError:
        # A concurrent overview request may have created the same category pool.
        db.session.rollback()
        records = [EquityCapital.query.filter_by(user_id=current_user.id, category_id=category.id).one()
                   for category in categories]
    projects = Project.query.filter_by(user_id=current_user.id).order_by(Project.name).all()
    projects_by_category = {}
    for project in projects:
        if project.category_id is not None:
            projects_by_category.setdefault(str(project.category_id), []).append(project.id)
    unreconciled_expenses_by_category = {}
    expenses = Expense.query.filter_by(user_id=current_user.id, transaction_type='expense').filter(
        Expense.project_id.isnot(None)
    ).order_by(Expense.date.desc()).all()
    for expense in expenses:
        if expense.project and expense.project.category_id and not expense.capital_allocation:
            unreconciled_expenses_by_category.setdefault(str(expense.project.category_id), []).append({
                'id': expense.id,
                'description': expense.description,
                'amount': expense.amount,
                'date': expense.date.strftime('%Y-%m-%d'),
                'project_name': expense.project.name,
            })
    return render_template('equity_capital.html', equity_records=records,
                           wallets=Wallet.query.filter_by(user_id=current_user.id).all(),
                           projects=projects,
                           projects_by_category=projects_by_category,
                           unreconciled_expenses_by_category=unreconciled_expenses_by_category,
                           totals=_overview_totals(records),
                           transaction_type_choices=TRANSACTION_TYPE_CHOICES,
                           allocation_type_choices=ALLOCATION_TYPE_CHOICES)


@equity_bp.route('/setup/<int:category_id>', methods=['POST'])
@login_required
def setup_initial_capital(category_id):
    category = ProjectCategory.query.filter_by(id=category_id, user_id=current_user.id).first_or_404()
    record = EquityCapital.query.filter_by(user_id=current_user.id, category_id=category.id).first()
    if not record:
        record = EquityCapital(user_id=current_user.id, category_id=category.id)
        db.session.add(record)
    try:
        record.initial_capital = float(request.form.get('initial_capital', 0))
        if record.initial_capital < 0:
            raise ValueError
        date = request.form.get('initial_capital_date')
        record.initial_capital_date = datetime.strptime(date, '%Y-%m-%d') if date else None
        record.business_name = request.form.get('business_name', '').strip() or None
        record.notes = request.form.get('notes', '').strip() or None
        db.session.commit()
        flash('Initial capital saved.', 'success')
    except (TypeError, ValueError):
        db.session.rollback(); flash('Enter a valid initial capital amount.', 'danger')
    except SQLAlchemyError:
        db.session.rollback(); flash('Initial capital could not be saved. Please try again.', 'danger')
    return redirect(url_for('equity.equity_overview'))


@equity_bp.route('/transaction/add/<int:equity_id>', methods=['POST'])
@login_required
def add_transaction(equity_id):
    record = _equity_for_user(equity_id)
    try:
        kind, amount = request.form.get('transaction_type'), float(request.form.get('amount', 0))
        wallet = Wallet.query.filter_by(id=request.form.get('wallet_id'), user_id=current_user.id).first()
        if kind not in TRANSACTION_TYPES or not isfinite(amount) or amount <= 0 or not wallet:
            raise ValueError('Choose a valid transaction type, amount, and wallet.')
        if kind == 'drawing' and wallet.balance < Decimal(str(amount)):
            raise ValueError('The selected wallet does not have enough cash for this drawing.')
        date = request.form.get('date')
        txn = EquityTransaction(user_id=current_user.id, equity_capital_id=record.id, transaction_type=kind,
            amount=amount, date=datetime.strptime(date, '%Y-%m-%d') if date else datetime.utcnow(),
            description=request.form.get('description', '').strip() or None,
            partner_name=request.form.get('partner_name', '').strip() or None, wallet_id=wallet.id,
            notes=request.form.get('notes', '').strip() or None)
        wallet.balance += Decimal(str(amount)) if txn.is_inflow else -Decimal(str(amount))
        db.session.add(txn); db.session.flush()
        _record_journal_entry(txn, record.category.name)
        db.session.commit(); flash('Capital movement recorded.', 'success')
    except (TypeError, ValueError) as error:
        db.session.rollback(); flash(str(error), 'danger')
    except SQLAlchemyError:
        db.session.rollback(); flash('Capital movement could not be saved. Please try again.', 'danger')
    return redirect(url_for('equity.equity_overview'))


@equity_bp.route('/transaction/delete/<int:transaction_id>', methods=['POST'])
@login_required
def delete_transaction(transaction_id):
    txn = EquityTransaction.query.filter_by(id=transaction_id, user_id=current_user.id).first_or_404()
    try:
        if txn.capital_allocations:
            raise ValueError('Remove the linked capital allocation before deleting this capital movement.')
        if txn.affects_wallet:
            txn.wallet.balance += -Decimal(str(txn.amount)) if txn.is_inflow else Decimal(str(txn.amount))
        journal_entry = txn.journal_entry
        txn.journal_entry_id = None
        _reverse_journal_entry(journal_entry)
        db.session.delete(txn); db.session.commit(); flash('Capital movement deleted and wallet reversed.', 'success')
    except ValueError as error:
        flash(str(error), 'danger')
    except SQLAlchemyError:
        db.session.rollback(); flash('Capital movement could not be deleted. Please try again.', 'danger')
    return redirect(url_for('equity.equity_overview'))


@equity_bp.route('/allocate/<int:equity_id>', methods=['POST'])
@login_required
def allocate_capital(equity_id):
    record = _equity_for_user(equity_id)
    try:
        kind, source, amount = request.form.get('allocation_type'), request.form.get('funding_source'), float(request.form.get('amount', 0))
        if kind not in ALLOCATION_TYPES or source not in {'capital', 'retained'} or not isfinite(amount) or amount <= 0:
            raise ValueError('Choose a valid allocation type, source, and amount.')
        project = None
        if kind == 'project_funding':
            project = Project.query.filter_by(id=request.form.get('project_id'), user_id=current_user.id).first()
            if not project or project.category_id != record.category_id:
                raise ValueError('Select a project in the same business category.')
        available = record.available_contributed_capital if source == 'capital' else record.available_retained_earnings
        if amount > available:
            raise ValueError(f'Only {available:,.2f} is available from this source.')
        date = request.form.get('date')
        db.session.add(CapitalAllocation(user_id=current_user.id, equity_capital_id=record.id, allocation_type=kind,
            amount=amount, date=datetime.strptime(date, '%Y-%m-%d') if date else datetime.utcnow(),
            project_id=project.id if project else None, funding_source=source,
            description=request.form.get('description', '').strip() or None, notes=request.form.get('notes', '').strip() or None))
        db.session.commit(); flash('Capital allocation recorded.', 'success')
    except (TypeError, ValueError) as error:
        db.session.rollback(); flash(str(error), 'danger')
    except SQLAlchemyError:
        db.session.rollback(); flash('Capital allocation could not be saved. Please try again.', 'danger')
    return redirect(url_for('equity.equity_overview'))


@equity_bp.route('/reconcile/<int:equity_id>', methods=['POST'])
@login_required
def reconcile_project_expense(equity_id):
    """Link a pre-existing project expense to its equity source without moving cash again."""
    record = _equity_for_user(equity_id)
    try:
        expense = Expense.query.filter_by(
            id=request.form.get('expense_id'), user_id=current_user.id, transaction_type='expense'
        ).first()
        source = request.form.get('funding_source')
        if not expense or not expense.project or expense.project.category_id != record.category_id:
            raise ValueError('Choose an unreconciled expense from a project in this business category.')
        if expense.capital_allocation:
            raise ValueError('This expense has already been reconciled to an equity allocation.')
        amount = expense.amount
        if not isfinite(amount) or amount <= 0:
            raise ValueError('The selected expense must have a positive amount.')

        historical_transaction = None
        if source == 'opening_capital':
            has_existing_contributed_history = bool(record.initial_capital or record.transactions or any(
                allocation.funding_source == 'capital' for allocation in record.allocations
            ))
            if has_existing_contributed_history:
                raise ValueError('Opening capital can only reconcile the first contributed-capital expense in this category.')
            record.initial_capital = amount
            record.initial_capital_date = expense.date
            allocation_source = 'capital'
        elif source == 'historical_contribution':
            # This documents contributed capital whose underlying cash movement
            # was already captured elsewhere. Do not change the wallet or post
            # a second cash journal entry.
            historical_transaction = EquityTransaction(
                user_id=current_user.id, equity_capital_id=record.id, transaction_type='injection',
                amount=amount, date=expense.date, wallet_id=expense.wallet_id, affects_wallet=False,
                description=f'Historical contribution for reconciled expense: {expense.description}',
                notes='Cash already recorded in transaction history; no wallet movement posted.',
            )
            db.session.add(historical_transaction)
            db.session.flush()
            allocation_source = 'capital'
        elif source == 'capital':
            if amount > record.available_contributed_capital:
                raise ValueError(f'Only {record.available_contributed_capital:,.2f} is available from contributed capital.')
            allocation_source = 'capital'
        elif source == 'retained':
            if amount > record.available_retained_earnings:
                raise ValueError(f'Only {record.available_retained_earnings:,.2f} is available from retained earnings.')
            allocation_source = 'retained'
        else:
            raise ValueError('Choose contributed capital, retained earnings, opening capital, or historical contribution.')

        db.session.add(CapitalAllocation(
            user_id=current_user.id, equity_capital_id=record.id, project_id=expense.project_id,
            expense_id=expense.id, allocation_type='project_funding', funding_source=allocation_source,
            equity_transaction_id=historical_transaction.id if historical_transaction else None,
            amount=amount, date=expense.date,
            description=f'Historical reconciliation: {expense.description}',
            notes=request.form.get('notes', '').strip() or None,
        ))
        db.session.commit()
        flash('Existing project expense reconciled to equity. Its wallet and payment history were not changed.', 'success')
    except (TypeError, ValueError) as error:
        db.session.rollback(); flash(str(error), 'danger')
    except SQLAlchemyError:
        db.session.rollback(); flash('The expense could not be reconciled. No balances were changed.', 'danger')
    return redirect(url_for('equity.equity_overview'))


@equity_bp.route('/historical-injection/<int:equity_id>', methods=['POST'])
@login_required
def add_historical_owner_injection(equity_id):
    """Record owner capital already captured as cash elsewhere, without changing wallet balance."""
    record = _equity_for_user(equity_id)
    try:
        amount = float(request.form.get('amount', 0))
        if not isfinite(amount) or amount <= 0:
            raise ValueError('Enter a valid owner-injection amount.')
        wallet = Wallet.query.filter_by(id=request.form.get('wallet_id'), user_id=current_user.id).first()
        if not wallet:
            raise ValueError('Select the wallet where the cash was already recorded.')
        project = None
        project_id = request.form.get('project_id')
        if project_id:
            project = Project.query.filter_by(id=project_id, user_id=current_user.id).first()
            if not project or project.category_id != record.category_id:
                raise ValueError('Select a project in this same business category.')
        date = request.form.get('date')
        txn = EquityTransaction(
            user_id=current_user.id, equity_capital_id=record.id, transaction_type='injection',
            amount=amount, date=datetime.strptime(date, '%Y-%m-%d') if date else datetime.utcnow(),
            wallet_id=wallet.id, affects_wallet=False,
            description=request.form.get('description', '').strip() or 'Historical owner injection',
            notes=request.form.get('notes', '').strip() or 'Cash already recorded in transaction history; no wallet movement posted.',
        )
        db.session.add(txn)
        db.session.flush()
        if project:
            db.session.add(CapitalAllocation(
                user_id=current_user.id, equity_capital_id=record.id, equity_transaction_id=txn.id,
                project_id=project.id, allocation_type='project_funding', funding_source='capital',
                amount=amount, date=txn.date,
                description=f'Owner injection allocated to {project.name}: {txn.description}',
                notes='Allocated from a historical owner injection; no wallet movement posted.',
            ))
        db.session.commit()
        flash('Historical owner injection recorded without changing the wallet.', 'success')
    except (TypeError, ValueError) as error:
        db.session.rollback(); flash(str(error), 'danger')
    except SQLAlchemyError:
        db.session.rollback(); flash('The historical owner injection could not be saved. No balances were changed.', 'danger')
    return redirect(url_for('equity.equity_overview'))


@equity_bp.route('/allocation/delete/<int:allocation_id>', methods=['POST'])
@login_required
def delete_allocation(allocation_id):
    allocation = CapitalAllocation.query.filter_by(id=allocation_id, user_id=current_user.id).first_or_404()
    try:
        db.session.delete(allocation); db.session.commit(); flash('Capital allocation removed.', 'success')
    except SQLAlchemyError:
        db.session.rollback(); flash('Capital allocation could not be deleted. Please try again.', 'danger')
    return redirect(url_for('equity.equity_overview'))
