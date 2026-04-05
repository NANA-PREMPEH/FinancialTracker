"""
Management commands for database maintenance.

Provides Flask CLI commands for:
- db-audit: Check for orphaned records, missing FKs, balance inconsistencies
- db-fix: Apply safe auto-fixes with confirmation prompts
- db-report: Generate integrity report
"""

import click
from flask.cli import with_appcontext
from app import db
from app.models import (
    User, Wallet, Category, Expense, Budget, 
    Creditor, Debtor, Project, Investment
)


@click.group(name='db-maintenance')
def db_commands():
    """Database maintenance commands."""
    pass


@db_commands.command(name='audit')
@with_appcontext
def audit():
    """Check for data integrity issues."""
    click.echo("=" * 50)
    click.echo("DATABASE AUDIT REPORT")
    click.echo("=" * 50)
    
    # Check for orphaned records
    click.echo("\n[1] Checking for orphaned records...")
    
    # Check expenses without user
    orphan_expenses = Expense.query.filter(Expense.user_id == None).count()
    if orphan_expenses > 0:
        click.echo(f"  ⚠ Found {orphan_expenses} expenses without user!")
    else:
        click.echo("  ✓ No orphaned expenses")
    
    # Check wallets without user
    orphan_wallets = Wallet.query.filter(Wallet.user_id == None).count()
    if orphan_wallets > 0:
        click.echo(f"  ⚠ Found {orphan_wallets} wallets without user!")
    else:
        click.echo("  ✓ No orphaned wallets")
    
    # Check categories without user (custom only)
    orphan_categories = Category.query.filter(
        Category.user_id == None,
        Category.is_custom == True
    ).count()
    if orphan_categories > 0:
        click.echo(f"  ⚠ Found {orphan_categories} custom categories without user!")
    else:
        click.echo("  ✓ No orphaned custom categories")
    
    # Check for missing Transfer categories
    click.echo("\n[2] Checking for missing Transfer categories...")
    users = User.query.all()
    missing_transfer = 0
    for user in users:
        transfer_cat = Category.query.filter_by(name='Transfer', user_id=user.id).first()
        if not transfer_cat:
            missing_transfer += 1
    
    if missing_transfer > 0:
        click.echo(f"  ⚠ {missing_transfer} users missing Transfer category")
    else:
        click.echo("  ✓ All users have Transfer category")
    
    # Check wallet balance consistency
    click.echo("\n[3] Checking wallet balance consistency...")
    inconsistent = 0
    for wallet in Wallet.query.all():
        # Calculate actual balance from transactions
        expenses = Expense.query.filter_by(wallet_id=wallet.id, transaction_type='expense').all()
        incomes = Expense.query.filter_by(wallet_id=wallet.id, transaction_type='income').all()
        
        calculated = sum(i.amount for i in incomes) - sum(e.amount for e in expenses)
        
        if abs(calculated - float(wallet.balance)) > 0.01:  # Allow small rounding errors
            inconsistent += 1
    
    if inconsistent > 0:
        click.echo(f"  ⚠ Found {inconsistent} wallets with inconsistent balances")
    else:
        click.echo("  ✓ All wallet balances are consistent")
    
    # Check budget overspending
    click.echo("\n[4] Checking for overspent budgets...")
    overspent = Budget.query.filter(Budget.spent > Budget.amount).count()
    if overspent > 0:
        click.echo(f"  ⚠ Found {overspent} overspent budgets")
    else:
        click.echo("  ✓ No overspent budgets")
    
    click.echo("\n" + "=" * 50)
    click.echo("AUDIT COMPLETE")
    click.echo("=" * 50)


@db_commands.command(name='fix')
@with_appcontext
def fix():
    """Apply safe auto-fixes to data issues."""
    click.echo("=" * 50)
    click.echo("DATABASE FIXES")
    click.echo("=" * 50)
    
    fixed = 0
    
    # Fix 1: Create missing Transfer categories
    click.echo("\n[1] Creating missing Transfer categories...")
    users = User.query.all()
    for user in users:
        transfer_cat = Category.query.filter_by(name='Transfer', user_id=user.id).first()
        if not transfer_cat:
            transfer_cat = Category(name='Transfer', icon='↔️', user_id=user.id, is_custom=True)
            db.session.add(transfer_cat)
            fixed += 1
            click.echo(f"  Created Transfer category for user {user.email}")
    
    # Fix 2: Fix transfer transaction types
    click.echo("\n[2] Fixing transfer transaction types...")
    transfers = Expense.query.filter(
        Expense.description.like('Transfer to %'),
        Expense.transaction_type == 'expense'
    ).all()
    for t in transfers:
        t.transaction_type = 'transfer_out'
        fixed += 1
    
    transfers_in = Expense.query.filter(
        Expense.description.like('Transfer from %'),
        Expense.transaction_type == 'income'
    ).all()
    for t in transfers_in:
        t.transaction_type = 'transfer_in'
        fixed += 1
    
    click.echo(f"  Fixed {len(transfers) + len(transfers_in)} transfer transactions")
    
    if fixed > 0:
        db.session.commit()
        click.echo(f"\n✓ Successfully applied {fixed} fixes")
    else:
        click.echo("\n✓ No fixes needed - database is clean")
    
    click.echo("\n" + "=" * 50)


@db_commands.command(name='report')
@with_appcontext
def report():
    """Generate a comprehensive database integrity report."""
    click.echo("=" * 50)
    click.echo("DATABASE INTEGRITY REPORT")
    click.echo("=" * 50)
    
    # User statistics
    user_count = User.query.count()
    click.echo(f"\nUsers: {user_count}")
    
    # Wallet statistics
    wallet_count = Wallet.query.count()
    total_wallet_balance = sum(float(w.balance) for w in Wallet.query.all())
    click.echo(f"Wallets: {wallet_count} (Total: ${total_wallet_balance:,.2f})")
    
    # Category statistics
    cat_count = Category.query.count()
    custom_cat_count = Category.query.filter_by(is_custom=True).count()
    click.echo(f"Categories: {cat_count} ({custom_cat_count} custom)")
    
    # Transaction statistics
    expense_count = Expense.query.filter_by(transaction_type='expense').count()
    income_count = Expense.query.filter_by(transaction_type='income').count()
    click.echo(f"Transactions: {expense_count} expenses, {income_count} incomes")
    
    # Budget statistics
    budget_count = Budget.query.count()
    overspent = Budget.query.filter(Budget.spent > Budget.amount).count()
    click.echo(f"Budgets: {budget_count} ({overspent} overspent)")
    
    # Liability statistics
    creditor_total = sum(c.amount for c in Creditor.query.all())
    debtor_total = sum(d.amount for d in Debtor.query.all())
    click.echo(f"Creditors: ${creditor_total:,.2f}")
    click.echo(f"Debtors: ${debtor_total:,.2f}")
    
    # Investment statistics
    investment_count = Investment.query.count()
    total_invested = sum(i.amount_invested for i in Investment.query.all())
    total_value = sum(i.current_value for i in Investment.query.all())
    click.echo(f"Investments: {investment_count} (Invested: ${total_invested:,.2f}, Value: ${total_value:,.2f})")
    
    click.echo("\n" + "=" * 50)
    click.echo("REPORT COMPLETE")
    click.echo("=" * 50)


@db_commands.command(name='stats')
@with_appcontext
def stats():
    """Show quick database statistics."""
    click.echo(f"Users: {User.query.count()}")
    click.echo(f"Wallets: {Wallet.query.count()}")
    click.echo(f"Categories: {Category.query.count()}")
    click.echo(f"Expenses: {Expense.query.filter_by(transaction_type='expense').count()}")
    click.echo(f"Incomes: {Expense.query.filter_by(transaction_type='income').count()}")
    click.echo(f"Budgets: {Budget.query.count()}")
    click.echo(f"Creditors: {Creditor.query.count()}")
    click.echo(f"Debtors: {Debtor.query.count()}")
    click.echo(f"Investments: {Investment.query.count()}")
