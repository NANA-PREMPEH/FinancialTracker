import csv
import io
import json
from datetime import datetime, timedelta

from flask import Blueprint, Response, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import and_, func

from . import db
from .models import BankReconciliation, Category, Expense, ImportHistory, Wallet

banking_bp = Blueprint('banking', __name__)

# Keyword map for smart categorization during import
CATEGORY_KEYWORDS = {
    'Food': ['restaurant', 'food', 'grocery', 'supermarket', 'cafe', 'dining', 'meal',
             'lunch', 'dinner', 'breakfast', 'pizza', 'burger', 'chicken', 'rice',
             'market', 'shoprite', 'melcom', 'maxmart'],
    'Transport': ['uber', 'bolt', 'taxi', 'fuel', 'petrol', 'gas', 'transport',
                  'bus', 'fare', 'parking', 'toll', 'goil', 'shell', 'total'],
    'Utilities': ['electricity', 'water', 'internet', 'airtime', 'mtn', 'vodafone',
                  'glo', 'tigo', 'telecel', 'dstv', 'gotv', 'ecg', 'gwcl'],
    'Health': ['hospital', 'pharmacy', 'clinic', 'medical', 'doctor', 'health',
               'drug', 'medication', 'lab', 'dental'],
    'Education': ['school', 'tuition', 'books', 'fees', 'university', 'college',
                  'course', 'training', 'exam'],
    'Shopping': ['shop', 'store', 'amazon', 'jumia', 'tonaton', 'clothing',
                 'fashion', 'electronics', 'gadget'],
    'Entertainment': ['movie', 'cinema', 'netflix', 'spotify', 'game', 'concert',
                      'event', 'subscription', 'youtube'],
    'Rent': ['rent', 'lease', 'housing', 'accommodation', 'landlord'],
    'Salary': ['salary', 'wage', 'payroll', 'stipend', 'allowance', 'bonus'],
    'Transfer': ['transfer', 'deposit', 'withdrawal', 'atm', 'mobile money', 'momo'],
}


def _smart_categorize(description, user_categories):
    """Match a transaction description to the best category using keyword matching."""
    desc_lower = (description or '').lower()
    if not desc_lower:
        return None

    # Build a map of user category names to IDs
    cat_name_map = {c.name.lower(): c for c in user_categories}

    # Check keyword map against user's actual categories
    for cat_name, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in desc_lower:
                # Try exact match first
                if cat_name.lower() in cat_name_map:
                    return cat_name_map[cat_name.lower()]
                # Try partial match on user category names
                for uname, ucat in cat_name_map.items():
                    if cat_name.lower() in uname or uname in cat_name.lower():
                        return ucat

    return None


def _detect_duplicates(user_id, transactions):
    """Check imported transactions against existing ones. Returns list of duplicate indices."""
    if not transactions:
        return []

    duplicates = []
    for i, txn in enumerate(transactions):
        existing = Expense.query.filter(
            Expense.user_id == user_id,
            Expense.amount == txn['amount'],
            Expense.date == txn['date'],
            func.lower(Expense.description) == txn['description'].lower().strip(),
        ).first()
        if existing:
            duplicates.append(i)
    return duplicates


def _parse_date(date_str):
    """Try multiple date formats."""
    date_str = (date_str or '').strip()
    if not date_str:
        return datetime.utcnow()
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y', '%Y/%m/%d', '%d %b %Y', '%d %B %Y'):
        try:
            return datetime.strptime(date_str, fmt)
        except (ValueError, AttributeError):
            continue
    return datetime.utcnow()


def _parse_csv(content):
    """Parse CSV content into a list of transaction dicts."""
    reader = csv.DictReader(io.StringIO(content))
    transactions = []
    for row in reader:
        amount_str = row.get('Amount', row.get('amount', row.get('Value', row.get('value', '0'))))
        amount = float(str(amount_str).replace(',', '').strip())
        desc = row.get('Description', row.get('description', row.get('Narration',
               row.get('narration', row.get('Details', row.get('details', 'Imported'))))))
        date_str = row.get('Date', row.get('date', row.get('Transaction Date',
                   row.get('transaction_date', row.get('Txn Date', '')))))
        transactions.append({
            'amount': amount,
            'description': str(desc).strip(),
            'date': _parse_date(date_str),
        })
    return transactions


def _parse_excel(file_stream):
    """Parse Excel (.xlsx) content into a list of transaction dicts."""
    import openpyxl
    wb = openpyxl.load_workbook(file_stream, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []

    # Find header row
    headers = [str(h).strip().lower() if h else '' for h in rows[0]]

    # Map common header names
    amount_col = None
    desc_col = None
    date_col = None
    for i, h in enumerate(headers):
        if h in ('amount', 'value', 'debit', 'credit'):
            amount_col = i
        elif h in ('description', 'narration', 'details', 'memo', 'particular'):
            desc_col = i
        elif h in ('date', 'transaction date', 'txn date', 'posting date'):
            date_col = i

    if amount_col is None:
        raise ValueError("Could not find Amount column in the Excel file.")

    transactions = []
    for row in rows[1:]:
        if not row or all(cell is None for cell in row):
            continue
        raw_amount = row[amount_col] if amount_col is not None and amount_col < len(row) else 0
        amount = float(str(raw_amount).replace(',', '').strip()) if raw_amount else 0
        if amount == 0:
            continue
        desc = str(row[desc_col]).strip() if desc_col is not None and desc_col < len(row) and row[desc_col] else 'Imported'
        raw_date = row[date_col] if date_col is not None and date_col < len(row) else None
        if isinstance(raw_date, datetime):
            date = raw_date
        else:
            date = _parse_date(str(raw_date) if raw_date else '')
        transactions.append({
            'amount': amount,
            'description': desc,
            'date': date,
        })
    wb.close()
    return transactions


@banking_bp.route('/banking')
@login_required
def banking_overview():
    wallets = Wallet.query.filter_by(user_id=current_user.id).all()
    reconciliations = BankReconciliation.query.filter_by(
        user_id=current_user.id
    ).order_by(BankReconciliation.date.desc()).limit(30).all()
    imports = ImportHistory.query.filter_by(
        user_id=current_user.id
    ).order_by(ImportHistory.date.desc()).limit(30).all()

    # Recent imported transactions (last 50 tagged 'imported')
    recent_imports = Expense.query.filter(
        Expense.user_id == current_user.id,
        Expense.tags.like('%imported%'),
    ).order_by(Expense.date.desc()).limit(50).all()

    # Reconciliation chart data — last 20 reconciliations
    recon_chart = []
    for r in reversed(reconciliations[:20]):
        recon_chart.append({
            'date': r.date.strftime('%d %b'),
            'statement': r.statement_balance,
            'app': r.reconciled_balance or 0,
            'diff': abs((r.statement_balance or 0) - (r.reconciled_balance or 0)),
            'status': r.status,
        })

    # Import stats
    total_imported = db.session.query(func.sum(ImportHistory.records_imported)).filter_by(
        user_id=current_user.id, status='completed'
    ).scalar() or 0
    total_imports = ImportHistory.query.filter_by(user_id=current_user.id).count()
    failed_imports = ImportHistory.query.filter_by(user_id=current_user.id, status='failed').count()

    # Reconciliation stats
    total_recons = len(reconciliations)
    reconciled_count = sum(1 for r in reconciliations if r.status == 'reconciled')
    discrepancy_count = sum(1 for r in reconciliations if r.status == 'discrepancy')

    return render_template('banking.html',
        wallets=wallets,
        reconciliations=reconciliations,
        imports=imports,
        recent_imports=recent_imports,
        recon_chart=json.dumps(recon_chart),
        total_imported=total_imported,
        total_imports=total_imports,
        failed_imports=failed_imports,
        total_recons=total_recons,
        reconciled_count=reconciled_count,
        discrepancy_count=discrepancy_count,
    )


@banking_bp.route('/banking/reconcile', methods=['POST'])
@login_required
def reconcile():
    wallet_id = int(request.form.get('wallet_id', 0))
    statement_balance = float(request.form.get('statement_balance', 0))
    wallet = Wallet.query.get_or_404(wallet_id)

    if wallet.user_id != current_user.id:
        flash('Unauthorized.', 'error')
        return redirect(url_for('banking.banking_overview'))

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
        flash(f'Discrepancy of GHS {diff:,.2f} found between app balance and statement.', 'error')
    return redirect(url_for('banking.banking_overview'))


@banking_bp.route('/banking/import', methods=['POST'])
@login_required
def import_transactions():
    file = request.files.get('file')
    wallet_id = int(request.form.get('wallet_id', 0))
    skip_duplicates = 'skip_duplicates' in request.form

    if not file or not file.filename:
        flash('Please upload a file.', 'error')
        return redirect(url_for('banking.banking_overview'))

    filename = file.filename.lower()
    if not (filename.endswith('.csv') or filename.endswith('.xlsx')):
        flash('Unsupported file format. Please upload a CSV or Excel (.xlsx) file.', 'error')
        return redirect(url_for('banking.banking_overview'))

    wallet = Wallet.query.get_or_404(wallet_id)
    if wallet.user_id != current_user.id:
        flash('Unauthorized.', 'error')
        return redirect(url_for('banking.banking_overview'))

    # Load user categories for smart categorization
    user_categories = Category.query.filter(
        (Category.user_id == current_user.id) | (Category.user_id.is_(None))
    ).all()
    default_cat = next((c for c in user_categories if c.name.lower() == 'other'), None) or (
        user_categories[0] if user_categories else None
    )

    try:
        # Parse file
        if filename.endswith('.xlsx'):
            transactions = _parse_excel(file.stream)
        else:
            content = file.stream.read().decode('utf-8')
            transactions = _parse_csv(content)

        if not transactions:
            flash('No transactions found in the file.', 'error')
            return redirect(url_for('banking.banking_overview'))

        # Detect duplicates
        duplicate_indices = _detect_duplicates(current_user.id, transactions) if skip_duplicates else []
        skipped = 0
        count = 0
        categorized = 0

        for i, txn in enumerate(transactions):
            if i in duplicate_indices:
                skipped += 1
                continue

            # Smart categorization
            matched_cat = _smart_categorize(txn['description'], user_categories)
            if matched_cat:
                categorized += 1
            cat = matched_cat or default_cat

            t_type = 'income' if txn['amount'] > 0 else 'expense'
            expense = Expense(
                user_id=current_user.id,
                amount=abs(txn['amount']),
                description=txn['description'],
                date=txn['date'],
                category_id=cat.id if cat else 1,
                wallet_id=wallet.id,
                transaction_type=t_type,
                tags='imported',
            )
            db.session.add(expense)
            if t_type == 'income':
                wallet.balance += abs(txn['amount'])
            else:
                wallet.balance -= abs(txn['amount'])
            count += 1

        history = ImportHistory(
            user_id=current_user.id,
            filename=file.filename,
            records_imported=count,
            status='completed',
            notes=f'Auto-categorized: {categorized}, Duplicates skipped: {skipped}' if (categorized or skipped) else None,
        )
        db.session.add(history)
        db.session.commit()

        msg = f'Successfully imported {count} transactions.'
        if categorized:
            msg += f' {categorized} auto-categorized.'
        if skipped:
            msg += f' {skipped} duplicates skipped.'
        flash(msg, 'success')

    except Exception as e:
        db.session.rollback()
        history = ImportHistory(
            user_id=current_user.id, filename=file.filename,
            records_imported=0, status='failed', notes=str(e)[:500]
        )
        db.session.add(history)
        db.session.commit()
        flash(f'Import failed: {str(e)}', 'error')

    return redirect(url_for('banking.banking_overview'))


@banking_bp.route('/banking/check-duplicates', methods=['POST'])
@login_required
def check_duplicates():
    """AJAX endpoint to preview duplicates before import."""
    file = request.files.get('file')
    if not file or not file.filename:
        return {'duplicates': 0, 'total': 0}

    filename = file.filename.lower()
    try:
        if filename.endswith('.xlsx'):
            transactions = _parse_excel(file.stream)
        elif filename.endswith('.csv'):
            content = file.stream.read().decode('utf-8')
            transactions = _parse_csv(content)
        else:
            return {'duplicates': 0, 'total': 0}

        dupes = _detect_duplicates(current_user.id, transactions)
        return {'duplicates': len(dupes), 'total': len(transactions)}
    except Exception:
        return {'duplicates': 0, 'total': 0}


@banking_bp.route('/banking/export-recon-csv')
@login_required
def export_reconciliation_csv():
    """Export reconciliation history as CSV."""
    reconciliations = BankReconciliation.query.filter_by(
        user_id=current_user.id
    ).order_by(BankReconciliation.date.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Date', 'Wallet', 'Statement Balance', 'App Balance', 'Discrepancy', 'Status', 'Notes'])
    for r in reconciliations:
        wallet_name = r.wallet.name if r.wallet else 'Unknown'
        diff = abs((r.statement_balance or 0) - (r.reconciled_balance or 0))
        writer.writerow([
            r.date.strftime('%Y-%m-%d %H:%M'),
            wallet_name,
            f'{r.statement_balance:.2f}',
            f'{r.reconciled_balance:.2f}' if r.reconciled_balance else '0.00',
            f'{diff:.2f}',
            r.status,
            r.notes or '',
        ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=reconciliation_{datetime.utcnow().strftime("%Y%m%d")}.csv'}
    )
