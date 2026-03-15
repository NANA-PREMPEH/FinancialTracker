from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, Response
from flask_login import login_required, current_user
from . import db
from .models import (
    Wallet, Category, Expense, Budget, RecurringTransaction,
    Project, ProjectItem, ProjectItemPayment,
    FinancialSummary, WishlistItem,
    Creditor, DebtPayment, Debtor, DebtorPayment,
    Goal, GoalTask, GoalMilestone,
    Investment, Dividend, InsurancePolicy, PensionScheme, SSNITContribution,
    NetWorthSnapshot, FixedAsset,
    CashFlowProjection, CashFlowAlert, BudgetPeriod,
    CalendarEvent, AutomationRule, WebhookEndpoint,
    BankReconciliation, ChartOfAccount, JournalEntry,
    Commitment, SMCContract, ContractPayment, ConstructionWork, GlobalEntity,
    NotificationPreference, BackupHistory
)
from datetime import datetime
import json
import hashlib

backup_bp = Blueprint('backup', __name__)

APP_VERSION = '2.0'
BACKUP_FORMAT_VERSION = '2.0'


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────
def _dt(val):
    """Serialize a datetime to ISO string or None."""
    return val.isoformat() if val else None


def _build_full_backup(uid):
    """Build the complete backup dict for a user, covering ALL models."""
    user = db.session.get(current_user.__class__, uid)

    data = {
        'wallets': [{
            'name': w.name, 'balance': w.balance, 'currency': w.currency,
            'icon': w.icon, 'wallet_type': w.wallet_type,
            'account_number': w.account_number, 'is_shared': w.is_shared
        } for w in Wallet.query.filter_by(user_id=uid).all()],

        'categories': [{
            'name': c.name, 'icon': c.icon, 'is_custom': c.is_custom
        } for c in Category.query.filter_by(user_id=uid).all()],

        'expenses': [{
            'amount': e.amount, 'description': e.description,
            'date': _dt(e.date),
            'category': e.category.name if e.category else '',
            'wallet': e.wallet.name if e.wallet else '',
            'notes': e.notes, 'tags': e.tags,
            'transaction_type': e.transaction_type,
            'original_amount': e.original_amount,
            'original_currency': e.original_currency
        } for e in Expense.query.filter_by(user_id=uid).all()],

        'budgets': [{
            'category': b.category.name if b.category else '',
            'amount': b.amount, 'period': b.period,
            'start_date': _dt(b.start_date), 'end_date': _dt(b.end_date),
            'notify_at_75': b.notify_at_75, 'notify_at_90': b.notify_at_90,
            'notify_at_100': b.notify_at_100, 'is_active': b.is_active
        } for b in Budget.query.filter_by(user_id=uid).all()],

        'recurring_transactions': [{
            'amount': r.amount, 'description': r.description,
            'category': r.category.name if r.category else '',
            'wallet': r.wallet.name if r.wallet else '',
            'transaction_type': r.transaction_type, 'frequency': r.frequency,
            'start_date': _dt(r.start_date), 'end_date': _dt(r.end_date),
            'last_created': _dt(r.last_created), 'next_due': _dt(r.next_due),
            'is_active': r.is_active, 'notes': r.notes
        } for r in RecurringTransaction.query.filter_by(user_id=uid).all()],

        'projects': [{
            'name': p.name, 'description': p.description,
            'funding_source': p.funding_source,
            'wallet': p.wallet.name if p.wallet else None,
            'custom_funding_source': p.custom_funding_source,
            'is_completed': p.is_completed,
            'created_date': _dt(p.created_date),
            'items': [{
                'item_name': it.item_name, 'description': it.description,
                'cost': it.cost, 'item_type': it.item_type,
                'is_completed': it.is_completed,
                'created_date': _dt(it.created_date),
                'payments': [{
                    'amount': pay.amount, 'description': pay.description,
                    'is_paid': pay.is_paid,
                    'payment_date': _dt(pay.payment_date),
                    'created_date': _dt(pay.created_date)
                } for pay in it.payments]
            } for it in p.items]
        } for p in Project.query.filter_by(user_id=uid).all()],

        'financial_summaries': [{
            'year': fs.year, 'month': fs.month,
            'total_income': fs.total_income, 'total_expense': fs.total_expense,
            'notes': fs.notes
        } for fs in FinancialSummary.query.filter_by(user_id=uid).all()],

        'wishlist': [{
            'name': w.name, 'amount': w.amount,
            'category': w.category.name if w.category else None,
            'priority': w.priority, 'notes': w.notes
        } for w in WishlistItem.query.filter_by(user_id=uid).all()],

        'creditors': [{
            'name': c.name, 'amount': c.amount, 'currency': c.currency,
            'description': c.description, 'debt_type': c.debt_type,
            'interest_rate': c.interest_rate, 'original_amount': c.original_amount,
            'due_date': _dt(c.due_date), 'status': c.status,
            'payment_frequency': c.payment_frequency,
            'minimum_payment': c.minimum_payment,
            'contact_info': c.contact_info, 'priority': c.priority,
            'notes': c.notes,
            'payments': [{
                'amount': dp.amount, 'date': _dt(dp.date), 'notes': dp.notes
            } for dp in c.payments]
        } for c in Creditor.query.filter_by(user_id=uid).all()],

        'debtors': [{
            'name': d.name, 'amount': d.amount, 'currency': d.currency,
            'description': d.description, 'debt_type': d.debt_type,
            'interest_rate': d.interest_rate, 'original_amount': d.original_amount,
            'due_date': _dt(d.due_date), 'status': d.status,
            'payment_frequency': d.payment_frequency,
            'minimum_payment': d.minimum_payment,
            'contact_info': d.contact_info, 'priority': d.priority,
            'notes': d.notes,
            'payments': [{
                'amount': dp.amount, 'date': _dt(dp.date), 'notes': dp.notes
            } for dp in d.payments]
        } for d in Debtor.query.filter_by(user_id=uid).all()],

        'goals': [{
            'name': g.name, 'target_amount': g.target_amount,
            'current_amount': g.current_amount, 'deadline': _dt(g.deadline),
            'goal_type': g.goal_type, 'icon': g.icon, 'color': g.color,
            'priority': g.priority, 'notes': g.notes,
            'is_completed': g.is_completed,
            'tasks': [{
                'title': t.title, 'description': t.description,
                'due_date': _dt(t.due_date), 'priority': t.priority,
                'is_completed': t.is_completed
            } for t in g.tasks],
            'milestones': [{
                'title': m.title, 'target_amount': m.target_amount,
                'is_completed': m.is_completed
            } for m in g.milestones]
        } for g in Goal.query.filter_by(user_id=uid).all()],

        'investments': [{
            'name': i.name, 'investment_type': i.investment_type,
            'amount_invested': i.amount_invested,
            'current_value': i.current_value,
            'purchase_date': _dt(i.purchase_date),
            'platform': i.platform, 'notes': i.notes,
            'dividends': [{
                'amount': d.amount, 'date': _dt(d.date), 'notes': d.notes
            } for d in i.dividends]
        } for i in Investment.query.filter_by(user_id=uid).all()],

        'insurance_policies': [{
            'provider': ip.provider, 'policy_number': ip.policy_number,
            'policy_type': ip.policy_type, 'premium': ip.premium,
            'coverage': ip.coverage, 'start_date': _dt(ip.start_date),
            'end_date': _dt(ip.end_date), 'notes': ip.notes
        } for ip in InsurancePolicy.query.filter_by(user_id=uid).all()],

        'pension_schemes': [{
            'name': ps.name, 'scheme_type': ps.scheme_type,
            'contributions': ps.contributions,
            'employer_match': ps.employer_match,
            'balance': ps.balance, 'notes': ps.notes
        } for ps in PensionScheme.query.filter_by(user_id=uid).all()],

        'ssnit_contributions': [{
            'month': sc.month, 'year': sc.year, 'amount': sc.amount,
            'employer': sc.employer, 'employee_number': sc.employee_number
        } for sc in SSNITContribution.query.filter_by(user_id=uid).all()],

        'net_worth_snapshots': [{
            'date': _dt(nw.date), 'total_assets': nw.total_assets,
            'total_liabilities': nw.total_liabilities,
            'net_worth': nw.net_worth, 'breakdown_json': nw.breakdown_json
        } for nw in NetWorthSnapshot.query.filter_by(user_id=uid).all()],

        'fixed_assets': [{
            'name': fa.name, 'asset_category': fa.asset_category,
            'purchase_date': _dt(fa.purchase_date),
            'purchase_price': fa.purchase_price,
            'current_value': fa.current_value, 'location': fa.location,
            'condition': fa.condition,
            'depreciation_rate': fa.depreciation_rate, 'notes': fa.notes
        } for fa in FixedAsset.query.filter_by(user_id=uid).all()],

        'cashflow_projections': [{
            'month': cf.month, 'year': cf.year,
            'projected_income': cf.projected_income,
            'projected_expenses': cf.projected_expenses,
            'actual_income': cf.actual_income,
            'actual_expenses': cf.actual_expenses, 'notes': cf.notes
        } for cf in CashFlowProjection.query.filter_by(user_id=uid).all()],

        'cashflow_alerts': [{
            'alert_type': ca.alert_type, 'threshold': ca.threshold,
            'message': ca.message, 'is_active': ca.is_active
        } for ca in CashFlowAlert.query.filter_by(user_id=uid).all()],

        'budget_periods': [{
            'name': bp.name, 'start_date': _dt(bp.start_date),
            'end_date': _dt(bp.end_date), 'total_budget': bp.total_budget,
            'notes': bp.notes
        } for bp in BudgetPeriod.query.filter_by(user_id=uid).all()],

        'calendar_events': [{
            'title': ce.title, 'description': ce.description,
            'event_type': ce.event_type, 'event_date': _dt(ce.event_date),
            'amount': ce.amount, 'reminder_date': _dt(ce.reminder_date),
            'reminder_enabled': ce.reminder_enabled,
            'is_recurring': ce.is_recurring, 'color': ce.color
        } for ce in CalendarEvent.query.filter_by(user_id=uid).all()],

        'automation_rules': [{
            'name': ar.name, 'trigger_type': ar.trigger_type,
            'condition': ar.condition, 'action_type': ar.action_type,
            'action_params': ar.action_params, 'is_active': ar.is_active
        } for ar in AutomationRule.query.filter_by(user_id=uid).all()],

        'webhook_endpoints': [{
            'name': we.name, 'url': we.url, 'events': we.events,
            'secret': we.secret, 'is_active': we.is_active
        } for we in WebhookEndpoint.query.filter_by(user_id=uid).all()],

        'bank_reconciliations': [{
            'wallet': br.wallet.name if br.wallet else '',
            'statement_balance': br.statement_balance,
            'reconciled_balance': br.reconciled_balance,
            'date': _dt(br.date), 'status': br.status, 'notes': br.notes
        } for br in BankReconciliation.query.filter_by(user_id=uid).all()],

        'chart_of_accounts': [{
            'code': coa.code, 'name': coa.name,
            'account_type': coa.account_type, 'balance': coa.balance,
            'parent_code': coa.parent.code if coa.parent else None
        } for coa in ChartOfAccount.query.filter_by(user_id=uid).all()],

        'journal_entries': [{
            'date': _dt(je.date), 'description': je.description,
            'debit_account_code': je.debit_account.code if je.debit_account else '',
            'credit_account_code': je.credit_account.code if je.credit_account else '',
            'amount': je.amount, 'reference': je.reference
        } for je in JournalEntry.query.filter_by(user_id=uid).all()],

        'commitments': [{
            'name': cm.name, 'commitment_category': cm.commitment_category,
            'amount': cm.amount, 'frequency': cm.frequency,
            'due_date': _dt(cm.due_date), 'status': cm.status, 'notes': cm.notes
        } for cm in Commitment.query.filter_by(user_id=uid).all()],

        'smc_contracts': [{
            'contract_number': sc.contract_number, 'title': sc.title,
            'description': sc.description, 'contract_value': sc.contract_value,
            'start_date': _dt(sc.start_date), 'end_date': _dt(sc.end_date),
            'status': sc.status, 'location': sc.location, 'notes': sc.notes,
            'payments': [{
                'amount': cp.amount, 'description': cp.description,
                'payment_date': _dt(cp.payment_date), 'status': cp.status
            } for cp in sc.payments]
        } for sc in SMCContract.query.filter_by(user_id=uid).all()],

        'construction_works': [{
            'project_name': cw.project_name, 'description': cw.description,
            'location': cw.location, 'budget': cw.budget, 'spent': cw.spent,
            'status': cw.status, 'start_date': _dt(cw.start_date),
            'end_date': _dt(cw.end_date), 'contractor': cw.contractor,
            'notes': cw.notes
        } for cw in ConstructionWork.query.filter_by(user_id=uid).all()],

        'global_entities': [{
            'name': ge.name, 'entity_type': ge.entity_type,
            'ownership_percent': ge.ownership_percent,
            'value': ge.value, 'description': ge.description,
            'notes': ge.notes
        } for ge in GlobalEntity.query.filter_by(user_id=uid).all()],

        'notification_preferences': [{
            'notification_type': np.notification_type, 'enabled': np.enabled
        } for np in NotificationPreference.query.filter_by(user_id=uid).all()],
    }

    return data


def _count_records(data):
    """Count total records across all data keys."""
    total = 0
    for key, val in data.items():
        if key.startswith('_') or key in ('backup_date', 'backup_version', 'app_version', 'user', 'checksum', 'record_count'):
            continue
        if isinstance(val, list):
            total += len(val)
            # Count nested records (e.g. project items, payments)
            for item in val:
                if isinstance(item, dict):
                    for k, v in item.items():
                        if isinstance(v, list):
                            total += len(v)
                            for sub in v:
                                if isinstance(sub, dict):
                                    for sk, sv in sub.items():
                                        if isinstance(sv, list):
                                            total += len(sv)
    return total


def _compute_checksum(data_dict):
    """Compute SHA-256 checksum of the data payload (excluding the checksum field itself)."""
    clean = {k: v for k, v in data_dict.items() if k != 'checksum'}
    raw = json.dumps(clean, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def _parse_dt(val):
    """Parse an ISO datetime string back to a datetime object."""
    if not val:
        return None
    try:
        return datetime.fromisoformat(val)
    except (ValueError, TypeError):
        return None


# ──────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────
@backup_bp.route('/backup')
@login_required
def backup_page():
    uid = current_user.id
    history = BackupHistory.query.filter_by(user_id=uid).order_by(BackupHistory.created_at.desc()).limit(20).all()

    # Stats
    total_records = 0
    model_counts = {}
    models_to_count = [
        ('Wallets', Wallet), ('Categories', Category), ('Transactions', Expense),
        ('Budgets', Budget), ('Goals', Goal), ('Creditors', Creditor),
        ('Debtors', Debtor), ('Investments', Investment), ('Projects', Project),
        ('Commitments', Commitment), ('Insurance', InsurancePolicy),
        ('Fixed Assets', FixedAsset), ('Calendar Events', CalendarEvent),
    ]
    for label, model in models_to_count:
        count = model.query.filter_by(user_id=uid).count()
        model_counts[label] = count
        total_records += count

    last_backup = BackupHistory.query.filter_by(
        user_id=uid, status='completed'
    ).order_by(BackupHistory.created_at.desc()).first()

    return render_template('backup.html',
                           history=history,
                           total_records=total_records,
                           model_counts=model_counts,
                           last_backup=last_backup)


@backup_bp.route('/backup/create', methods=['POST'])
@login_required
def create_backup():
    uid = current_user.id
    backup_type = request.form.get('backup_type', 'manual')

    data = _build_full_backup(uid)

    # Add metadata
    data['backup_date'] = datetime.utcnow().isoformat()
    data['backup_version'] = BACKUP_FORMAT_VERSION
    data['app_version'] = APP_VERSION
    data['user'] = {'name': current_user.name, 'email': current_user.email}

    record_count = _count_records(data)
    data['record_count'] = record_count
    data['checksum'] = _compute_checksum(data)

    json_str = json.dumps(data, indent=2, default=str)
    file_name = f'fintracker_backup_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.json'

    # Log to history
    try:
        entry = BackupHistory(
            user_id=uid,
            backup_type=backup_type,
            file_name=file_name,
            file_size=len(json_str.encode('utf-8')),
            record_count=record_count,
            checksum=data['checksum'],
            status='completed',
            notes=f'Full backup with {record_count} records'
        )
        db.session.add(entry)
        db.session.commit()
    except Exception:
        db.session.rollback()

    return Response(
        json_str,
        mimetype='application/json',
        headers={'Content-Disposition': f'attachment;filename={file_name}'}
    )


@backup_bp.route('/backup/restore', methods=['POST'])
@login_required
def restore_backup():
    file = request.files.get('file')
    if not file or not file.filename.endswith('.json'):
        flash('Please upload a valid JSON backup file.', 'error')
        return redirect(url_for('backup.backup_page'))

    try:
        raw = file.stream.read().decode('utf-8')
        data = json.loads(raw)
    except Exception as e:
        flash(f'Failed to read backup file: {str(e)}', 'error')
        return redirect(url_for('backup.backup_page'))

    # Verify checksum if present
    if 'checksum' in data:
        expected = data['checksum']
        actual = _compute_checksum(data)
        if expected != actual:
            flash('⚠️ Backup integrity check FAILED. The file may be corrupted or tampered with. Restore aborted.', 'error')
            return redirect(url_for('backup.backup_page'))

    uid = current_user.id
    restore_mode = request.form.get('restore_mode', 'replace')

    # ── Step 1: Create pre-restore safety snapshot ──
    try:
        safety_data = _build_full_backup(uid)
        safety_data['backup_date'] = datetime.utcnow().isoformat()
        safety_data['backup_version'] = BACKUP_FORMAT_VERSION
        safety_data['app_version'] = APP_VERSION
        safety_data['user'] = {'name': current_user.name, 'email': current_user.email}
        safety_count = _count_records(safety_data)
        safety_data['record_count'] = safety_count
        safety_data['checksum'] = _compute_checksum(safety_data)

        safety_entry = BackupHistory(
            user_id=uid,
            backup_type='pre_restore',
            file_name=f'pre_restore_snapshot_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.json',
            file_size=len(json.dumps(safety_data).encode('utf-8')),
            record_count=safety_count,
            checksum=safety_data['checksum'],
            status='completed',
            notes='Automatic safety snapshot before restore'
        )
        db.session.add(safety_entry)
        db.session.commit()
    except Exception:
        db.session.rollback()

    # ── Step 2: Perform restore ──
    try:
        if restore_mode == 'replace':
            _restore_replace(uid, data)
        else:
            _restore_merge(uid, data)

        restored_count = _count_records(data)

        # Log restore event
        restore_entry = BackupHistory(
            user_id=uid,
            backup_type='restore',
            file_name=file.filename,
            file_size=len(raw.encode('utf-8')),
            record_count=restored_count,
            checksum=data.get('checksum', ''),
            status='completed',
            notes=f'{restore_mode.title()} restore: {restored_count} records'
        )
        db.session.add(restore_entry)
        db.session.commit()

        flash(f'✅ Restore completed successfully! {restored_count} records restored using {restore_mode} mode. '
              f'A safety snapshot was created before restore.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Restore failed: {str(e)}. No data was changed.', 'error')

    return redirect(url_for('backup.backup_page'))


def _restore_replace(uid, data):
    """Clear all user data and insert from backup."""
    # Delete in dependency order (children first)
    _delete_all_user_data(uid)
    db.session.flush()

    # Re-insert from backup
    _insert_from_backup(uid, data)
    db.session.commit()


def _restore_merge(uid, data):
    """Merge: only add records that don't already exist (by natural key)."""
    _insert_from_backup(uid, data, merge=True)
    db.session.commit()


def _delete_all_user_data(uid):
    """Delete ALL user-owned records in dependency-safe order."""
    # Deeply nested first
    ProjectItemPayment.query.filter_by(user_id=uid).delete()
    ProjectItem.query.filter_by(user_id=uid).delete()

    ContractPayment.query.filter(
        ContractPayment.contract_id.in_(
            db.session.query(SMCContract.id).filter_by(user_id=uid)
        )
    ).delete(synchronize_session=False)

    DebtPayment.query.filter_by(user_id=uid).delete()
    DebtorPayment.query.filter_by(user_id=uid).delete()

    # Delete dividends via investment ids
    Dividend.query.filter_by(user_id=uid).delete()

    # Delete goal children
    GoalTask.query.filter_by(user_id=uid).delete()
    GoalMilestone.query.filter_by(user_id=uid).delete()

    # Delete journal entries before chart of accounts
    JournalEntry.query.filter_by(user_id=uid).delete()

    # Delete reconciliations before wallets
    BankReconciliation.query.filter_by(user_id=uid).delete()

    # Main entities
    Expense.query.filter_by(user_id=uid).delete()
    Budget.query.filter_by(user_id=uid).delete()
    RecurringTransaction.query.filter_by(user_id=uid).delete()
    Project.query.filter_by(user_id=uid).delete()
    FinancialSummary.query.filter_by(user_id=uid).delete()
    WishlistItem.query.filter_by(user_id=uid).delete()
    Creditor.query.filter_by(user_id=uid).delete()
    Debtor.query.filter_by(user_id=uid).delete()
    Goal.query.filter_by(user_id=uid).delete()
    Investment.query.filter_by(user_id=uid).delete()
    InsurancePolicy.query.filter_by(user_id=uid).delete()
    PensionScheme.query.filter_by(user_id=uid).delete()
    SSNITContribution.query.filter_by(user_id=uid).delete()
    NetWorthSnapshot.query.filter_by(user_id=uid).delete()
    FixedAsset.query.filter_by(user_id=uid).delete()
    CashFlowProjection.query.filter_by(user_id=uid).delete()
    CashFlowAlert.query.filter_by(user_id=uid).delete()
    BudgetPeriod.query.filter_by(user_id=uid).delete()
    CalendarEvent.query.filter_by(user_id=uid).delete()
    AutomationRule.query.filter_by(user_id=uid).delete()
    WebhookEndpoint.query.filter_by(user_id=uid).delete()
    ChartOfAccount.query.filter_by(user_id=uid).delete()
    Commitment.query.filter_by(user_id=uid).delete()
    SMCContract.query.filter_by(user_id=uid).delete()
    ConstructionWork.query.filter_by(user_id=uid).delete()
    GlobalEntity.query.filter_by(user_id=uid).delete()
    NotificationPreference.query.filter_by(user_id=uid).delete()

    # Categories and Wallets last (referenced by many)
    Category.query.filter_by(user_id=uid).delete()
    Wallet.query.filter_by(user_id=uid).delete()


def _insert_from_backup(uid, data, merge=False):
    """Insert records from backup data. If merge=True, skip existing by natural key."""

    # ── Wallets ──
    wallet_map = {}  # name -> Wallet obj
    for w in data.get('wallets', []):
        if merge:
            existing = Wallet.query.filter_by(user_id=uid, name=w['name']).first()
            if existing:
                wallet_map[w['name']] = existing
                continue
        obj = Wallet(user_id=uid, name=w['name'], balance=w.get('balance', 0),
                     currency=w.get('currency', 'GHS'), icon=w.get('icon', '💰'),
                     wallet_type=w.get('wallet_type', 'cash'),
                     account_number=w.get('account_number'),
                     is_shared=w.get('is_shared', False))
        db.session.add(obj)
        db.session.flush()
        wallet_map[w['name']] = obj

    # ── Categories ──
    cat_map = {}  # name -> Category obj
    for c in data.get('categories', []):
        if merge:
            existing = Category.query.filter_by(user_id=uid, name=c['name']).first()
            if existing:
                cat_map[c['name']] = existing
                continue
        obj = Category(user_id=uid, name=c['name'], icon=c.get('icon', '📝'),
                       is_custom=c.get('is_custom', False))
        db.session.add(obj)
        db.session.flush()
        cat_map[c['name']] = obj

    # ── Expenses ──
    for e in data.get('expenses', []):
        cat = cat_map.get(e.get('category'))
        wal = wallet_map.get(e.get('wallet'))
        if not cat or not wal:
            continue
        obj = Expense(user_id=uid, amount=e['amount'], description=e.get('description', ''),
                      date=_parse_dt(e.get('date')) or datetime.utcnow(),
                      category_id=cat.id, wallet_id=wal.id,
                      notes=e.get('notes'), tags=e.get('tags'),
                      transaction_type=e.get('transaction_type', 'expense'),
                      original_amount=e.get('original_amount'),
                      original_currency=e.get('original_currency'))
        db.session.add(obj)

    # ── Budgets ──
    for b in data.get('budgets', []):
        cat = cat_map.get(b.get('category'))
        if not cat:
            continue
        obj = Budget(user_id=uid, category_id=cat.id, amount=b['amount'],
                     period=b.get('period', 'monthly'),
                     start_date=_parse_dt(b.get('start_date')) or datetime.utcnow(),
                     end_date=_parse_dt(b.get('end_date')),
                     notify_at_75=b.get('notify_at_75', True),
                     notify_at_90=b.get('notify_at_90', True),
                     notify_at_100=b.get('notify_at_100', True),
                     is_active=b.get('is_active', True))
        db.session.add(obj)

    # ── Recurring Transactions ──
    for r in data.get('recurring_transactions', []):
        cat = cat_map.get(r.get('category'))
        wal = wallet_map.get(r.get('wallet'))
        if not cat or not wal:
            continue
        obj = RecurringTransaction(
            user_id=uid, amount=r['amount'], description=r.get('description', ''),
            category_id=cat.id, wallet_id=wal.id,
            transaction_type=r.get('transaction_type', 'expense'),
            frequency=r.get('frequency', 'monthly'),
            start_date=_parse_dt(r.get('start_date')) or datetime.utcnow(),
            end_date=_parse_dt(r.get('end_date')),
            last_created=_parse_dt(r.get('last_created')),
            next_due=_parse_dt(r.get('next_due')),
            is_active=r.get('is_active', True), notes=r.get('notes'))
        db.session.add(obj)

    # ── Projects (with items and payments) ──
    for p in data.get('projects', []):
        if merge and Project.query.filter_by(user_id=uid, name=p['name']).first():
            continue
        wal = wallet_map.get(p.get('wallet'))
        proj = Project(user_id=uid, name=p['name'], description=p.get('description'),
                       funding_source=p.get('funding_source', 'Self'),
                       wallet_id=wal.id if wal else None,
                       custom_funding_source=p.get('custom_funding_source'),
                       is_completed=p.get('is_completed', False),
                       created_date=_parse_dt(p.get('created_date')) or datetime.utcnow())
        db.session.add(proj)
        db.session.flush()
        for it in p.get('items', []):
            item = ProjectItem(user_id=uid, project_id=proj.id,
                               item_name=it['item_name'], description=it.get('description'),
                               cost=it.get('cost', 0), item_type=it.get('item_type', 'expense'),
                               is_completed=it.get('is_completed', False),
                               created_date=_parse_dt(it.get('created_date')) or datetime.utcnow())
            db.session.add(item)
            db.session.flush()
            for pay in it.get('payments', []):
                payment = ProjectItemPayment(
                    user_id=uid, project_item_id=item.id,
                    amount=pay['amount'], description=pay.get('description'),
                    is_paid=pay.get('is_paid', False),
                    payment_date=_parse_dt(pay.get('payment_date')),
                    created_date=_parse_dt(pay.get('created_date')) or datetime.utcnow())
                db.session.add(payment)

    # ── Financial Summaries ──
    for fs in data.get('financial_summaries', []):
        if merge and FinancialSummary.query.filter_by(user_id=uid, year=fs['year'], month=fs.get('month')).first():
            continue
        obj = FinancialSummary(user_id=uid, year=fs['year'], month=fs.get('month'),
                               total_income=fs.get('total_income', 0),
                               total_expense=fs.get('total_expense', 0),
                               notes=fs.get('notes'))
        db.session.add(obj)

    # ── Wishlist ──
    for w in data.get('wishlist', []):
        if merge and WishlistItem.query.filter_by(user_id=uid, name=w['name']).first():
            continue
        cat = cat_map.get(w.get('category'))
        obj = WishlistItem(user_id=uid, name=w['name'], amount=w.get('amount', 0),
                           category_id=cat.id if cat else None,
                           priority=w.get('priority', 'Medium'), notes=w.get('notes'))
        db.session.add(obj)

    # ── Creditors (with payments) ──
    for c in data.get('creditors', []):
        if merge and Creditor.query.filter_by(user_id=uid, name=c['name']).first():
            continue
        cred = Creditor(user_id=uid, name=c['name'], amount=c.get('amount', 0),
                        currency=c.get('currency', 'GHS'), description=c.get('description'),
                        debt_type=c.get('debt_type', 'Personal Loan'),
                        interest_rate=c.get('interest_rate', 0),
                        original_amount=c.get('original_amount'),
                        due_date=_parse_dt(c.get('due_date')),
                        status=c.get('status', 'active'),
                        payment_frequency=c.get('payment_frequency'),
                        minimum_payment=c.get('minimum_payment', 0),
                        contact_info=c.get('contact_info'),
                        priority=c.get('priority', 3), notes=c.get('notes'))
        db.session.add(cred)
        db.session.flush()
        for dp in c.get('payments', []):
            pay = DebtPayment(user_id=uid, creditor_id=cred.id,
                              amount=dp['amount'],
                              date=_parse_dt(dp.get('date')) or datetime.utcnow(),
                              notes=dp.get('notes'))
            db.session.add(pay)

    # ── Debtors (with payments) ──
    for d in data.get('debtors', []):
        if merge and Debtor.query.filter_by(user_id=uid, name=d['name']).first():
            continue
        dbt = Debtor(user_id=uid, name=d['name'], amount=d.get('amount', 0),
                     currency=d.get('currency', 'GHS'), description=d.get('description'),
                     debt_type=d.get('debt_type', 'Money Lent'),
                     interest_rate=d.get('interest_rate', 0),
                     original_amount=d.get('original_amount'),
                     due_date=_parse_dt(d.get('due_date')),
                     status=d.get('status', 'active'),
                     payment_frequency=d.get('payment_frequency'),
                     minimum_payment=d.get('minimum_payment', 0),
                     contact_info=d.get('contact_info'),
                     priority=d.get('priority', 3), notes=d.get('notes'))
        db.session.add(dbt)
        db.session.flush()
        for dp in d.get('payments', []):
            pay = DebtorPayment(user_id=uid, debtor_id=dbt.id,
                                amount=dp['amount'],
                                date=_parse_dt(dp.get('date')) or datetime.utcnow(),
                                notes=dp.get('notes'))
            db.session.add(pay)

    # ── Goals (with tasks and milestones) ──
    for g in data.get('goals', []):
        if merge and Goal.query.filter_by(user_id=uid, name=g['name']).first():
            continue
        goal = Goal(user_id=uid, name=g['name'],
                    target_amount=g.get('target_amount', 0),
                    current_amount=g.get('current_amount', 0),
                    deadline=_parse_dt(g.get('deadline')),
                    goal_type=g.get('goal_type', 'Custom'),
                    icon=g.get('icon', '🎯'), color=g.get('color', '#6366f1'),
                    priority=g.get('priority', 3), notes=g.get('notes'),
                    is_completed=g.get('is_completed', False))
        db.session.add(goal)
        db.session.flush()
        for t in g.get('tasks', []):
            task = GoalTask(user_id=uid, goal_id=goal.id, title=t['title'],
                            description=t.get('description'),
                            due_date=_parse_dt(t.get('due_date')),
                            priority=t.get('priority', 3),
                            is_completed=t.get('is_completed', False))
            db.session.add(task)
        for m in g.get('milestones', []):
            ms = GoalMilestone(user_id=uid, goal_id=goal.id, title=m['title'],
                               target_amount=m.get('target_amount', 0),
                               is_completed=m.get('is_completed', False))
            db.session.add(ms)

    # ── Investments (with dividends) ──
    for i in data.get('investments', []):
        if merge and Investment.query.filter_by(user_id=uid, name=i['name']).first():
            continue
        inv = Investment(user_id=uid, name=i['name'],
                         investment_type=i.get('investment_type', 'Other'),
                         amount_invested=i.get('amount_invested', 0),
                         current_value=i.get('current_value', 0),
                         purchase_date=_parse_dt(i.get('purchase_date')),
                         platform=i.get('platform'), notes=i.get('notes'))
        db.session.add(inv)
        db.session.flush()
        for d in i.get('dividends', []):
            div = Dividend(user_id=uid, investment_id=inv.id,
                           amount=d['amount'],
                           date=_parse_dt(d.get('date')) or datetime.utcnow(),
                           notes=d.get('notes'))
            db.session.add(div)

    # ── Insurance Policies ──
    for ip in data.get('insurance_policies', []):
        if merge and InsurancePolicy.query.filter_by(user_id=uid, provider=ip['provider'], policy_type=ip['policy_type']).first():
            continue
        obj = InsurancePolicy(user_id=uid, provider=ip['provider'],
                              policy_number=ip.get('policy_number'),
                              policy_type=ip['policy_type'],
                              premium=ip.get('premium', 0),
                              coverage=ip.get('coverage'),
                              start_date=_parse_dt(ip.get('start_date')),
                              end_date=_parse_dt(ip.get('end_date')),
                              notes=ip.get('notes'))
        db.session.add(obj)

    # ── Pension Schemes ──
    for ps in data.get('pension_schemes', []):
        if merge and PensionScheme.query.filter_by(user_id=uid, name=ps['name']).first():
            continue
        obj = PensionScheme(user_id=uid, name=ps['name'],
                            scheme_type=ps.get('scheme_type', 'Private'),
                            contributions=ps.get('contributions', 0),
                            employer_match=ps.get('employer_match', 0),
                            balance=ps.get('balance', 0), notes=ps.get('notes'))
        db.session.add(obj)

    # ── SSNIT Contributions ──
    for sc in data.get('ssnit_contributions', []):
        if merge and SSNITContribution.query.filter_by(user_id=uid, year=sc['year'], month=sc['month']).first():
            continue
        obj = SSNITContribution(user_id=uid, month=sc['month'], year=sc['year'],
                                amount=sc['amount'], employer=sc.get('employer'),
                                employee_number=sc.get('employee_number'))
        db.session.add(obj)

    # ── Net Worth Snapshots ──
    for nw in data.get('net_worth_snapshots', []):
        obj = NetWorthSnapshot(user_id=uid, date=_parse_dt(nw.get('date')) or datetime.utcnow(),
                               total_assets=nw.get('total_assets', 0),
                               total_liabilities=nw.get('total_liabilities', 0),
                               net_worth=nw.get('net_worth', 0),
                               breakdown_json=nw.get('breakdown_json'))
        db.session.add(obj)

    # ── Fixed Assets ──
    for fa in data.get('fixed_assets', []):
        if merge and FixedAsset.query.filter_by(user_id=uid, name=fa['name']).first():
            continue
        obj = FixedAsset(user_id=uid, name=fa['name'],
                         asset_category=fa.get('asset_category', 'Equipment'),
                         purchase_date=_parse_dt(fa.get('purchase_date')),
                         purchase_price=fa.get('purchase_price', 0),
                         current_value=fa.get('current_value', 0),
                         location=fa.get('location'),
                         condition=fa.get('condition', 'Good'),
                         depreciation_rate=fa.get('depreciation_rate', 0),
                         notes=fa.get('notes'))
        db.session.add(obj)

    # ── Cash Flow Projections ──
    for cf in data.get('cashflow_projections', []):
        if merge and CashFlowProjection.query.filter_by(user_id=uid, year=cf['year'], month=cf['month']).first():
            continue
        obj = CashFlowProjection(user_id=uid, month=cf['month'], year=cf['year'],
                                 projected_income=cf.get('projected_income', 0),
                                 projected_expenses=cf.get('projected_expenses', 0),
                                 actual_income=cf.get('actual_income', 0),
                                 actual_expenses=cf.get('actual_expenses', 0),
                                 notes=cf.get('notes'))
        db.session.add(obj)

    # ── Cash Flow Alerts ──
    for ca in data.get('cashflow_alerts', []):
        obj = CashFlowAlert(user_id=uid, alert_type=ca['alert_type'],
                            threshold=ca.get('threshold'),
                            message=ca.get('message'),
                            is_active=ca.get('is_active', True))
        db.session.add(obj)

    # ── Budget Periods ──
    for bp_data in data.get('budget_periods', []):
        if merge and BudgetPeriod.query.filter_by(user_id=uid, name=bp_data['name']).first():
            continue
        obj = BudgetPeriod(user_id=uid, name=bp_data['name'],
                           start_date=_parse_dt(bp_data.get('start_date')) or datetime.utcnow(),
                           end_date=_parse_dt(bp_data.get('end_date')) or datetime.utcnow(),
                           total_budget=bp_data.get('total_budget', 0),
                           notes=bp_data.get('notes'))
        db.session.add(obj)

    # ── Calendar Events ──
    for ce in data.get('calendar_events', []):
        if merge and CalendarEvent.query.filter_by(user_id=uid, title=ce['title'], event_date=_parse_dt(ce.get('event_date'))).first():
            continue
        obj = CalendarEvent(user_id=uid, title=ce['title'],
                            description=ce.get('description'),
                            event_type=ce.get('event_type', 'Custom'),
                            event_date=_parse_dt(ce.get('event_date')) or datetime.utcnow(),
                            amount=ce.get('amount'),
                            reminder_date=_parse_dt(ce.get('reminder_date')),
                            reminder_enabled=ce.get('reminder_enabled', False),
                            is_recurring=ce.get('is_recurring', False),
                            color=ce.get('color', '#6366f1'))
        db.session.add(obj)

    # ── Automation Rules ──
    for ar in data.get('automation_rules', []):
        if merge and AutomationRule.query.filter_by(user_id=uid, name=ar['name']).first():
            continue
        obj = AutomationRule(user_id=uid, name=ar['name'],
                             trigger_type=ar['trigger_type'],
                             condition=ar.get('condition'),
                             action_type=ar['action_type'],
                             action_params=ar.get('action_params'),
                             is_active=ar.get('is_active', True))
        db.session.add(obj)

    # ── Webhook Endpoints ──
    for we in data.get('webhook_endpoints', []):
        if merge and WebhookEndpoint.query.filter_by(user_id=uid, name=we['name']).first():
            continue
        obj = WebhookEndpoint(user_id=uid, name=we['name'], url=we['url'],
                              events=we.get('events'), secret=we.get('secret'),
                              is_active=we.get('is_active', True))
        db.session.add(obj)

    # ── Bank Reconciliations ──
    for br_data in data.get('bank_reconciliations', []):
        wal = wallet_map.get(br_data.get('wallet'))
        if not wal:
            continue
        obj = BankReconciliation(user_id=uid, wallet_id=wal.id,
                                 statement_balance=br_data['statement_balance'],
                                 reconciled_balance=br_data.get('reconciled_balance'),
                                 date=_parse_dt(br_data.get('date')) or datetime.utcnow(),
                                 status=br_data.get('status', 'pending'),
                                 notes=br_data.get('notes'))
        db.session.add(obj)

    # ── Chart of Accounts ──
    coa_map = {}
    for coa in data.get('chart_of_accounts', []):
        if merge and ChartOfAccount.query.filter_by(user_id=uid, code=coa['code']).first():
            existing = ChartOfAccount.query.filter_by(user_id=uid, code=coa['code']).first()
            coa_map[coa['code']] = existing
            continue
        obj = ChartOfAccount(user_id=uid, code=coa['code'], name=coa['name'],
                             account_type=coa['account_type'],
                             balance=coa.get('balance', 0))
        db.session.add(obj)
        db.session.flush()
        coa_map[coa['code']] = obj
    # Set parent references
    for coa in data.get('chart_of_accounts', []):
        if coa.get('parent_code') and coa['code'] in coa_map and coa['parent_code'] in coa_map:
            coa_map[coa['code']].parent_id = coa_map[coa['parent_code']].id

    # ── Journal Entries ──
    for je in data.get('journal_entries', []):
        debit = coa_map.get(je.get('debit_account_code'))
        credit = coa_map.get(je.get('credit_account_code'))
        if not debit or not credit:
            continue
        obj = JournalEntry(user_id=uid,
                           date=_parse_dt(je.get('date')) or datetime.utcnow(),
                           description=je['description'],
                           debit_account_id=debit.id,
                           credit_account_id=credit.id,
                           amount=je['amount'],
                           reference=je.get('reference'))
        db.session.add(obj)

    # ── Commitments ──
    for cm in data.get('commitments', []):
        if merge and Commitment.query.filter_by(user_id=uid, name=cm['name']).first():
            continue
        obj = Commitment(user_id=uid, name=cm['name'],
                         commitment_category=cm.get('commitment_category', 'Custom'),
                         amount=cm.get('amount', 0),
                         frequency=cm.get('frequency', 'one_time'),
                         due_date=_parse_dt(cm.get('due_date')),
                         status=cm.get('status', 'pending'),
                         notes=cm.get('notes'))
        db.session.add(obj)

    # ── SMC Contracts (with payments) ──
    for sc in data.get('smc_contracts', []):
        if merge and SMCContract.query.filter_by(user_id=uid, contract_number=sc['contract_number']).first():
            continue
        contract = SMCContract(user_id=uid,
                               contract_number=sc['contract_number'],
                               title=sc['title'],
                               description=sc.get('description'),
                               contract_value=sc.get('contract_value', 0),
                               start_date=_parse_dt(sc.get('start_date')),
                               end_date=_parse_dt(sc.get('end_date')),
                               status=sc.get('status', 'active'),
                               location=sc.get('location'),
                               notes=sc.get('notes'))
        db.session.add(contract)
        db.session.flush()
        for cp in sc.get('payments', []):
            pay = ContractPayment(user_id=uid, contract_id=contract.id,
                                  amount=cp['amount'],
                                  description=cp.get('description'),
                                  payment_date=_parse_dt(cp.get('payment_date')) or datetime.utcnow(),
                                  status=cp.get('status', 'pending'))
            db.session.add(pay)

    # ── Construction Works ──
    for cw in data.get('construction_works', []):
        if merge and ConstructionWork.query.filter_by(user_id=uid, project_name=cw['project_name']).first():
            continue
        obj = ConstructionWork(user_id=uid, project_name=cw['project_name'],
                               description=cw.get('description'),
                               location=cw.get('location'),
                               budget=cw.get('budget', 0), spent=cw.get('spent', 0),
                               status=cw.get('status', 'planning'),
                               start_date=_parse_dt(cw.get('start_date')),
                               end_date=_parse_dt(cw.get('end_date')),
                               contractor=cw.get('contractor'),
                               notes=cw.get('notes'))
        db.session.add(obj)

    # ── Global Entities ──
    for ge in data.get('global_entities', []):
        if merge and GlobalEntity.query.filter_by(user_id=uid, name=ge['name']).first():
            continue
        obj = GlobalEntity(user_id=uid, name=ge['name'],
                           entity_type=ge.get('entity_type', 'Business'),
                           ownership_percent=ge.get('ownership_percent', 100),
                           value=ge.get('value', 0),
                           description=ge.get('description'),
                           notes=ge.get('notes'))
        db.session.add(obj)

    # ── Notification Preferences ──
    for np_data in data.get('notification_preferences', []):
        if merge and NotificationPreference.query.filter_by(user_id=uid, notification_type=np_data['notification_type']).first():
            continue
        obj = NotificationPreference(user_id=uid,
                                     notification_type=np_data['notification_type'],
                                     enabled=np_data.get('enabled', True))
        db.session.add(obj)

    db.session.flush()


# ──────────────────────────────────────────────
# API Endpoints
# ──────────────────────────────────────────────
@backup_bp.route('/backup/preview', methods=['POST'])
@login_required
def preview_backup():
    """Parse an uploaded backup file and return a summary without restoring."""
    file = request.files.get('file')
    if not file or not file.filename.endswith('.json'):
        return jsonify({'error': 'Please upload a valid JSON file.'}), 400

    try:
        raw = file.stream.read().decode('utf-8')
        data = json.loads(raw)
    except Exception as e:
        return jsonify({'error': f'Failed to parse: {str(e)}'}), 400

    # Build summary
    summary = {}
    entity_keys = [
        ('wallets', 'Wallets'), ('categories', 'Categories'),
        ('expenses', 'Transactions'), ('budgets', 'Budgets'),
        ('recurring_transactions', 'Recurring'), ('projects', 'Projects'),
        ('financial_summaries', 'Summaries'), ('wishlist', 'Wishlist'),
        ('creditors', 'Creditors'), ('debtors', 'Debtors'),
        ('goals', 'Goals'), ('investments', 'Investments'),
        ('insurance_policies', 'Insurance'), ('pension_schemes', 'Pensions'),
        ('ssnit_contributions', 'SSNIT'), ('net_worth_snapshots', 'Net Worth'),
        ('fixed_assets', 'Fixed Assets'), ('cashflow_projections', 'Cash Flow'),
        ('calendar_events', 'Calendar'), ('automation_rules', 'Automation'),
        ('commitments', 'Commitments'), ('smc_contracts', 'SMC Contracts'),
        ('construction_works', 'Construction'), ('global_entities', 'Global Entities'),
        ('chart_of_accounts', 'Accounts'), ('journal_entries', 'Journal Entries'),
    ]
    total = 0
    for key, label in entity_keys:
        count = len(data.get(key, []))
        if count > 0:
            summary[label] = count
            total += count

    # Check integrity
    checksum_valid = None
    if 'checksum' in data:
        expected = data['checksum']
        actual = _compute_checksum(data)
        checksum_valid = (expected == actual)

    return jsonify({
        'backup_date': data.get('backup_date'),
        'backup_version': data.get('backup_version'),
        'user': data.get('user', {}),
        'record_count': total,
        'entities': summary,
        'checksum_valid': checksum_valid,
        'file_size': len(raw)
    })


@backup_bp.route('/backup/verify', methods=['POST'])
@login_required
def verify_backup():
    """Verify a backup file's integrity via checksum."""
    file = request.files.get('file')
    if not file or not file.filename.endswith('.json'):
        return jsonify({'error': 'Please upload a valid JSON file.'}), 400

    try:
        raw = file.stream.read().decode('utf-8')
        data = json.loads(raw)
    except Exception as e:
        return jsonify({'error': f'Failed to parse: {str(e)}'}), 400

    if 'checksum' not in data:
        return jsonify({
            'valid': False,
            'message': 'No checksum found in this backup file. It may be from an older version.'
        })

    expected = data['checksum']
    actual = _compute_checksum(data)

    return jsonify({
        'valid': expected == actual,
        'message': 'Backup integrity verified — file is intact.' if expected == actual
                   else 'Checksum mismatch — file may be corrupted or tampered with.',
        'expected_checksum': expected[:12] + '...',
        'actual_checksum': actual[:12] + '...',
        'backup_date': data.get('backup_date'),
        'record_count': data.get('record_count', 0)
    })


@backup_bp.route('/backup/history')
@login_required
def backup_history():
    """Return backup history as JSON."""
    uid = current_user.id
    entries = BackupHistory.query.filter_by(user_id=uid).order_by(BackupHistory.created_at.desc()).limit(50).all()
    return jsonify([{
        'id': e.id,
        'backup_type': e.backup_type,
        'file_name': e.file_name,
        'file_size': e.file_size,
        'record_count': e.record_count,
        'checksum': e.checksum[:12] + '...' if e.checksum else None,
        'status': e.status,
        'notes': e.notes,
        'created_at': e.created_at.isoformat() if e.created_at else None
    } for e in entries])
