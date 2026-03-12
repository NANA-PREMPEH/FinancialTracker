from . import db
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), default='user')  # user, admin
    default_currency = db.Column(db.String(10), default='GHS')
    theme_preference = db.Column(db.String(10), default='system')  # light, dark, system
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    email_verified = db.Column(db.Boolean, default=False)
    totp_secret = db.Column(db.String(32), nullable=True)
    totp_enabled = db.Column(db.Boolean, default=False)
    oauth_provider = db.Column(db.String(20), nullable=True)
    oauth_id = db.Column(db.String(200), nullable=True)
    push_prefs = db.Column(db.JSON, default=lambda: {
        'budget_alerts': True,
        'goal_milestones': True,
        'large_transactions': True,
        'payment_due': True,
        'recurring_processed': True,
    })

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.email}>'

class Wallet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    name = db.Column(db.String(100), nullable=False)
    balance = db.Column(db.Float, default=0.0)
    currency = db.Column(db.String(10), default='GHS')
    icon = db.Column(db.String(10), default='💰')
    wallet_type = db.Column(db.String(20), default='cash')  # cash, bank, crypto, ewallet
    account_number = db.Column(db.String(50), nullable=True)  # For bank accounts
    is_shared = db.Column(db.Boolean, default=False)
    user = db.relationship('User', backref=db.backref('wallets', cascade='all, delete-orphan'), lazy=True)
    expenses = db.relationship('Expense', backref='wallet', lazy=True)

    def __repr__(self):
        return f'<Wallet {self.name}>'


class WalletShare(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    wallet_id = db.Column(db.Integer, db.ForeignKey('wallet.id'), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    shared_with_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    permission = db.Column(db.String(20), default='view')  # view, contribute, manage
    accepted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    wallet = db.relationship('Wallet', backref=db.backref('shares', cascade='all, delete-orphan', lazy=True))
    owner = db.relationship('User', foreign_keys=[owner_id], backref=db.backref('wallet_shares_sent', lazy=True))
    shared_with = db.relationship('User', foreign_keys=[shared_with_id], backref=db.backref('wallet_shares_received', lazy=True))

    def __repr__(self):
        return f'<WalletShare wallet={self.wallet_id} to user={self.shared_with_id} ({self.permission})>'


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    name = db.Column(db.String(50), nullable=False)
    icon = db.Column(db.String(10), default='📝')
    is_custom = db.Column(db.Boolean, default=False)
    user = db.relationship('User', backref=db.backref('categories', cascade='all, delete-orphan'), lazy=True)
    expenses = db.relationship('Expense', backref='category', lazy=True)
    budgets = db.relationship('Budget', backref='category', lazy=True)

    def __repr__(self):
        return f'<Category {self.name}>'

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(200), nullable=False)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    wallet_id = db.Column(db.Integer, db.ForeignKey('wallet.id'), nullable=False)
    notes = db.Column(db.Text, nullable=True)
    tags = db.Column(db.String(200), nullable=True)
    receipt_path = db.Column(db.String(300), nullable=True)
    transaction_type = db.Column(db.String(20), default='expense')
    original_amount = db.Column(db.Float, nullable=True)
    original_currency = db.Column(db.String(10), nullable=True)

    user = db.relationship('User', backref=db.backref('_user_expenses', cascade='all, delete-orphan'), lazy=True)

    def __repr__(self):
        return f'<Expense {self.amount} - {self.description}>'

class Budget(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    period = db.Column(db.String(20), default='monthly')  # weekly, monthly, yearly
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=True)
    notify_at_75 = db.Column(db.Boolean, default=True)
    notify_at_90 = db.Column(db.Boolean, default=True)
    notify_at_100 = db.Column(db.Boolean, default=True)
    is_active = db.Column(db.Boolean, default=True)

    user = db.relationship('User', backref=db.backref('_user_budgets', cascade='all, delete-orphan'), lazy=True)

    def __repr__(self):
        return f'<Budget {self.category.name} - {self.amount}>'

class RecurringTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(200), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    wallet_id = db.Column(db.Integer, db.ForeignKey('wallet.id'), nullable=False)
    transaction_type = db.Column(db.String(20), default='expense')
    frequency = db.Column(db.String(20), nullable=False)  # daily, weekly, monthly, yearly
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=True)
    last_created = db.Column(db.DateTime, nullable=True)
    next_due = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    notes = db.Column(db.Text, nullable=True)
    
    # Relationships
    category = db.relationship('Category', backref='recurring_transactions', lazy=True)
    wallet = db.relationship('Wallet', backref='recurring_transactions', lazy=True)

    user = db.relationship('User', backref=db.backref('_user_recurringtransactions', cascade='all, delete-orphan'), lazy=True)

    def __repr__(self):
        return f'<RecurringTransaction {self.description} - {self.frequency}>'

class ExchangeRate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    from_currency = db.Column(db.String(10), nullable=False)
    to_currency = db.Column(db.String(10), nullable=False)
    rate = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<ExchangeRate {self.from_currency}/{self.to_currency} = {self.rate}>'

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)  # Optional description
    funding_source = db.Column(db.String(100), nullable=False)  # Predefined or custom
    wallet_id = db.Column(db.Integer, db.ForeignKey('wallet.id'), nullable=True)  # If funded from wallet
    custom_funding_source = db.Column(db.String(200), nullable=True)  # Custom funding source
    created_date = db.Column(db.DateTime, default=datetime.utcnow)
    is_completed = db.Column(db.Boolean, default=False)
    
    # Relationships
    items = db.relationship('ProjectItem', backref='project', lazy=True, cascade='all, delete-orphan')
    wallet = db.relationship('Wallet', backref='projects', lazy=True)
    
    user = db.relationship('User', backref=db.backref('_user_projects', cascade='all, delete-orphan'), lazy=True)

    def __repr__(self):
        return f'<Project {self.name}>'
    
    @property
    def total_cost(self):
        """Total Projected Expense"""
        return sum(item.cost for item in self.items if getattr(item, 'item_type', 'expense') != 'income')

    @property
    def total_income(self):
        """Total Projected Income"""
        return sum(item.cost for item in self.items if getattr(item, 'item_type', 'expense') == 'income')

    @property
    def paid_expense(self):
        """Total Paid Expense (Completed)"""
        return sum(item.total_paid for item in self.items if getattr(item, 'item_type', 'expense') != 'income')

    @property
    def paid_income(self):
        """Total Received Income"""
        return sum(item.total_paid for item in self.items if getattr(item, 'item_type', 'expense') == 'income')

class ProjectItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    item_name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    cost = db.Column(db.Float, nullable=False, default=0.0)
    item_type = db.Column(db.String(20), default='expense')  # 'expense' or 'income'
    is_completed = db.Column(db.Boolean, default=False)
    created_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship for payments
    payments = db.relationship('ProjectItemPayment', backref='project_item', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<ProjectItem {self.item_name} - {self.cost}>'
    
    @property
    def total_paid(self):
        """Calculate total amount paid for this item"""
        return sum(payment.amount for payment in self.payments if payment.is_paid)

class ProjectItemPayment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_item_id = db.Column(db.Integer, db.ForeignKey('project_item.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(200), nullable=True)
    is_paid = db.Column(db.Boolean, default=False)
    payment_date = db.Column(db.DateTime, nullable=True)
    created_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<ProjectItemPayment {self.amount} - {self.description}>'

class FinancialSummary(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=True)  # 1-12, or None for yearly summary
    total_income = db.Column(db.Float, default=0.0)
    total_expense = db.Column(db.Float, default=0.0)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('_user_financialsummaries', cascade='all, delete-orphan'), lazy=True)

    def __repr__(self):
        period = f"{self.year}-{self.month}" if self.month else str(self.year)
        return f'<FinancialSummary {period}: +{self.total_income} / -{self.total_expense}>'

class WishlistItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    name = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)
    priority = db.Column(db.String(20), default='Medium') # Low, Medium, High
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship
    category = db.relationship('Category', backref='wishlist_items')

    user = db.relationship('User', backref=db.backref('_user_wishlistitems', cascade='all, delete-orphan'), lazy=True)

    def __repr__(self):
        return f'<WishlistItem {self.name}: {self.amount}>'

class Creditor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    name = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False, default=0.0)
    currency = db.Column(db.String(10), default='GHS')
    description = db.Column(db.String(200), nullable=True)
    debt_type = db.Column(db.String(50), default='Personal Loan')
    interest_rate = db.Column(db.Float, default=0.0)
    original_amount = db.Column(db.Float, nullable=True)
    due_date = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='active')
    payment_frequency = db.Column(db.String(20), nullable=True)
    minimum_payment = db.Column(db.Float, default=0.0)
    contact_info = db.Column(db.String(200), nullable=True)
    priority = db.Column(db.Integer, default=3)
    notes = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('_user_creditors', cascade='all, delete-orphan'), lazy=True)

    @property
    def computed_status(self):
        if self.amount <= 0:
            return 'paid_off'
        if self.due_date and self.due_date < datetime.utcnow():
            return 'overdue'
        return self.status or 'active'

    @property
    def progress_percent(self):
        if not self.original_amount or self.original_amount <= 0:
            return 0
        paid = self.original_amount - self.amount
        return min(round((paid / self.original_amount) * 100, 1), 100)

    @property
    def days_until_due(self):
        if not self.due_date:
            return None
        return (self.due_date - datetime.utcnow()).days

    def __repr__(self):
        return f'<Creditor {self.name}: {self.amount}>'

class Debtor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    name = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False, default=0.0)
    currency = db.Column(db.String(10), default='GHS')
    description = db.Column(db.String(200), nullable=True)
    debt_type = db.Column(db.String(50), default='Money Lent')
    interest_rate = db.Column(db.Float, default=0.0)
    original_amount = db.Column(db.Float, nullable=True)
    due_date = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='active')
    payment_frequency = db.Column(db.String(20), nullable=True)
    minimum_payment = db.Column(db.Float, default=0.0)
    contact_info = db.Column(db.String(200), nullable=True)
    priority = db.Column(db.Integer, default=3)
    notes = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('_user_debtors', cascade='all, delete-orphan'), lazy=True)

    @property
    def computed_status(self):
        if self.status == 'bad_debt':
            return 'bad_debt'
        if self.amount <= 0:
            return 'paid_off'
        if self.due_date and self.due_date < datetime.utcnow():
            return 'overdue'
        return self.status or 'active'

    @property
    def progress_percent(self):
        if not self.original_amount or self.original_amount <= 0:
            return 0
        collected = self.original_amount - self.amount
        return min(round((collected / self.original_amount) * 100, 1), 100)

    @property
    def days_until_due(self):
        if not self.due_date:
            return None
        return (self.due_date - datetime.utcnow()).days

    def __repr__(self):
        return f'<Debtor {self.name}: {self.amount}>'


# ===== PHASE 2: Financial Goals =====
class Goal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    name = db.Column(db.String(150), nullable=False)
    target_amount = db.Column(db.Float, nullable=False)
    current_amount = db.Column(db.Float, default=0.0)
    deadline = db.Column(db.DateTime, nullable=True)
    goal_type = db.Column(db.String(50), default='Custom')
    icon = db.Column(db.String(10), default='🎯')
    color = db.Column(db.String(20), default='#6366f1')
    priority = db.Column(db.Integer, default=3)
    notes = db.Column(db.Text, nullable=True)
    is_completed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def progress(self):
        if self.target_amount <= 0:
            return 100
        return min(round((self.current_amount / self.target_amount) * 100, 1), 100)

    user = db.relationship('User', backref=db.backref('_user_goals', cascade='all, delete-orphan'), lazy=True)

    def __repr__(self):
        return f'<Goal {self.name}: {self.current_amount}/{self.target_amount}>'


class GoalTask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    goal_id = db.Column(db.Integer, db.ForeignKey('goal.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    due_date = db.Column(db.DateTime, nullable=True)
    priority = db.Column(db.Integer, default=3)
    is_completed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    goal = db.relationship('Goal', backref=db.backref('tasks', lazy=True, cascade='all, delete-orphan'))

    def __repr__(self):
        return f'<GoalTask {self.title}>'


class GoalMilestone(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    goal_id = db.Column(db.Integer, db.ForeignKey('goal.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    target_amount = db.Column(db.Float, nullable=False)
    is_completed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    goal = db.relationship('Goal', backref=db.backref('milestones', lazy=True, cascade='all, delete-orphan'))

    def __repr__(self):
        return f'<GoalMilestone {self.title}>'


# ===== PHASE 3: Investments & Net Worth =====
class Investment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    name = db.Column(db.String(150), nullable=False)
    investment_type = db.Column(db.String(50), nullable=False)  # Stocks, Bonds, Mutual Fund, ETF, Real Estate, Crypto, Fixed Deposit, Treasury Bill
    amount_invested = db.Column(db.Float, nullable=False, default=0.0)
    current_value = db.Column(db.Float, nullable=False, default=0.0)
    purchase_date = db.Column(db.DateTime, nullable=True)
    platform = db.Column(db.String(100), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    dividends = db.relationship('Dividend', backref='investment', lazy=True, cascade='all, delete-orphan')

    @property
    def roi(self):
        if self.amount_invested <= 0:
            return 0
        return round(((self.current_value - self.amount_invested) / self.amount_invested) * 100, 2)

    user = db.relationship('User', backref=db.backref('_user_investments', cascade='all, delete-orphan'), lazy=True)

    def __repr__(self):
        return f'<Investment {self.name}: {self.current_value}>'


class Dividend(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    investment_id = db.Column(db.Integer, db.ForeignKey('investment.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    notes = db.Column(db.String(200), nullable=True)

    def __repr__(self):
        return f'<Dividend {self.amount}>'


class InsurancePolicy(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    provider = db.Column(db.String(150), nullable=False)
    policy_number = db.Column(db.String(100), nullable=True)
    policy_type = db.Column(db.String(50), nullable=False)  # Life, Health, Auto, Home, Other
    premium = db.Column(db.Float, nullable=False, default=0.0)
    coverage = db.Column(db.Float, nullable=True)
    start_date = db.Column(db.DateTime, nullable=True)
    end_date = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('_user_insurancepolicies', cascade='all, delete-orphan'), lazy=True)

    def __repr__(self):
        return f'<InsurancePolicy {self.provider}: {self.policy_type}>'


class PensionScheme(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    name = db.Column(db.String(150), nullable=False)
    scheme_type = db.Column(db.String(50), nullable=False)  # SSNIT, Tier2, Tier3, Private, Employer
    contributions = db.Column(db.Float, default=0.0)
    employer_match = db.Column(db.Float, default=0.0)
    balance = db.Column(db.Float, default=0.0)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('_user_pensionschemes', cascade='all, delete-orphan'), lazy=True)

    def __repr__(self):
        return f'<PensionScheme {self.name}: {self.balance}>'


class SSNITContribution(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    month = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    employer = db.Column(db.String(150), nullable=True)
    employee_number = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('_user_ssnitcontributions', cascade='all, delete-orphan'), lazy=True)

    def __repr__(self):
        return f'<SSNITContribution {self.year}-{self.month}: {self.amount}>'


class NetWorthSnapshot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    total_assets = db.Column(db.Float, default=0.0)
    total_liabilities = db.Column(db.Float, default=0.0)
    net_worth = db.Column(db.Float, default=0.0)
    breakdown_json = db.Column(db.Text, nullable=True)  # JSON string of detailed breakdown

    user = db.relationship('User', backref=db.backref('_user_networthsnapshots', cascade='all, delete-orphan'), lazy=True)

    def __repr__(self):
        return f'<NetWorthSnapshot {self.date}: {self.net_worth}>'


class FixedAsset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    name = db.Column(db.String(150), nullable=False)
    asset_category = db.Column(db.String(50), nullable=False)  # Land, Buildings, Vehicles, Equipment
    purchase_date = db.Column(db.DateTime, nullable=True)
    purchase_price = db.Column(db.Float, nullable=False, default=0.0)
    current_value = db.Column(db.Float, nullable=False, default=0.0)
    location = db.Column(db.String(200), nullable=True)
    condition = db.Column(db.String(50), default='Good')  # Excellent, Good, Fair, Poor
    depreciation_rate = db.Column(db.Float, default=0.0)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('_user_fixedassets', cascade='all, delete-orphan'), lazy=True)

    def __repr__(self):
        return f'<FixedAsset {self.name}: {self.current_value}>'


# ===== PHASE 4: Cash Flow & Budget Planning =====
class CashFlowProjection(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    month = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    projected_income = db.Column(db.Float, default=0.0)
    projected_expenses = db.Column(db.Float, default=0.0)
    actual_income = db.Column(db.Float, default=0.0)
    actual_expenses = db.Column(db.Float, default=0.0)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('_user_cashflowprojections', cascade='all, delete-orphan'), lazy=True)

    def __repr__(self):
        return f'<CashFlowProjection {self.year}-{self.month}>'


class CashFlowAlert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    alert_type = db.Column(db.String(50), nullable=False)  # negative_cashflow, spending_spike, low_balance
    threshold = db.Column(db.Float, nullable=True)
    message = db.Column(db.String(300), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('_user_cashflowalerts', cascade='all, delete-orphan'), lazy=True)

    def __repr__(self):
        return f'<CashFlowAlert {self.alert_type}>'


class BudgetPeriod(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    name = db.Column(db.String(100), nullable=False)
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    total_budget = db.Column(db.Float, default=0.0)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('_user_budgetperiods', cascade='all, delete-orphan'), lazy=True)

    def __repr__(self):
        return f'<BudgetPeriod {self.name}>'


# ===== PHASE 5: Calendar =====
class CalendarEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    event_type = db.Column(db.String(50), default='Custom')  # Bill Due, Income Expected, Goal Deadline, Budget Review, Custom
    event_date = db.Column(db.DateTime, nullable=False)
    amount = db.Column(db.Float, nullable=True)
    reminder_date = db.Column(db.DateTime, nullable=True)
    reminder_enabled = db.Column(db.Boolean, default=False)
    is_recurring = db.Column(db.Boolean, default=False)
    color = db.Column(db.String(20), default='#6366f1')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('_user_calendarevents', cascade='all, delete-orphan'), lazy=True)

    def __repr__(self):
        return f'<CalendarEvent {self.title}: {self.event_date}>'


# ===== PHASE 6: Automation =====
class AutomationRule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    name = db.Column(db.String(150), nullable=False)
    trigger_type = db.Column(db.String(50), nullable=False)  # transaction_created, budget_exceeded, goal_progress, recurring_processed
    condition = db.Column(db.Text, nullable=True)  # JSON conditions
    action_type = db.Column(db.String(50), nullable=False)  # send_notification, add_tags, auto_categorize, call_webhook
    action_params = db.Column(db.Text, nullable=True)  # JSON params
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('_user_automationrules', cascade='all, delete-orphan'), lazy=True)

    def __repr__(self):
        return f'<AutomationRule {self.name}>'


class WebhookEndpoint(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    name = db.Column(db.String(150), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    events = db.Column(db.String(500), nullable=True)  # Comma-separated event types
    secret = db.Column(db.String(200), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('_user_webhookendpoints', cascade='all, delete-orphan'), lazy=True)

    def __repr__(self):
        return f'<WebhookEndpoint {self.name}>'


# ===== PHASE 7: Banking & Accounting =====
class BankReconciliation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    wallet_id = db.Column(db.Integer, db.ForeignKey('wallet.id'), nullable=False)
    statement_balance = db.Column(db.Float, nullable=False)
    reconciled_balance = db.Column(db.Float, nullable=True)
    date = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, reconciled, discrepancy
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    wallet = db.relationship('Wallet', backref='reconciliations', lazy=True)

    user = db.relationship('User', backref=db.backref('_user_bankreconciliations', cascade='all, delete-orphan'), lazy=True)

    def __repr__(self):
        return f'<BankReconciliation {self.date}: {self.status}>'


class ImportHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    filename = db.Column(db.String(200), nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    records_imported = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default='completed')  # completed, failed, partial
    notes = db.Column(db.Text, nullable=True)

    user = db.relationship('User', backref=db.backref('_user_importhistories', cascade='all, delete-orphan'), lazy=True)

    def __repr__(self):
        return f'<ImportHistory {self.filename}: {self.records_imported}>'


class ChartOfAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    code = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    account_type = db.Column(db.String(50), nullable=False)  # Asset, Liability, Equity, Revenue, Expense
    parent_id = db.Column(db.Integer, db.ForeignKey('chart_of_account.id'), nullable=True)
    balance = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    children = db.relationship('ChartOfAccount', backref=db.backref('parent', remote_side='ChartOfAccount.id'), lazy=True)

    user = db.relationship('User', backref=db.backref('_user_chartofaccounts', cascade='all, delete-orphan'), lazy=True)

    def __repr__(self):
        return f'<ChartOfAccount {self.code}: {self.name}>'


class JournalEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    description = db.Column(db.String(300), nullable=False)
    debit_account_id = db.Column(db.Integer, db.ForeignKey('chart_of_account.id'), nullable=False)
    credit_account_id = db.Column(db.Integer, db.ForeignKey('chart_of_account.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    reference = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    debit_account = db.relationship('ChartOfAccount', foreign_keys=[debit_account_id], backref='debit_entries')
    credit_account = db.relationship('ChartOfAccount', foreign_keys=[credit_account_id], backref='credit_entries')

    user = db.relationship('User', backref=db.backref('_user_journalentries', cascade='all, delete-orphan'), lazy=True)

    def __repr__(self):
        return f'<JournalEntry {self.date}: {self.amount}>'


# ===== PHASE 8: Commitments & Debts =====
class Commitment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    name = db.Column(db.String(150), nullable=False)
    commitment_category = db.Column(db.String(50), nullable=False)  # Church Levy, Church Group, Ceremony, Donation, Dues, Family Support, Harvest, Custom
    amount = db.Column(db.Float, nullable=False, default=0.0)
    frequency = db.Column(db.String(20), default='one_time')  # one_time, weekly, monthly, yearly
    due_date = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), default='pending')  # pending, paid, overdue
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('_user_commitments', cascade='all, delete-orphan'), lazy=True)

    def __repr__(self):
        return f'<Commitment {self.name}: {self.amount}>'


class DebtPayment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    creditor_id = db.Column(db.Integer, db.ForeignKey('creditor.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    notes = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    creditor = db.relationship('Creditor', backref=db.backref('payments', cascade='all, delete-orphan'), lazy=True)

    def __repr__(self):
        return f'<DebtPayment {self.amount}>'


class DebtorPayment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    debtor_id = db.Column(db.Integer, db.ForeignKey('debtor.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    notes = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    debtor = db.relationship('Debtor', backref=db.backref('payments', cascade='all, delete-orphan'), lazy=True)

    def __repr__(self):
        return f'<DebtorPayment {self.amount}>'


# ===== PHASE 9: Notifications =====
class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    title = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)
    notification_type = db.Column(db.String(50), default='info')  # info, budget_alert, goal_milestone, bill_reminder, spending_alert
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('_user_notifications', cascade='all, delete-orphan'), lazy=True)

    def __repr__(self):
        return f'<Notification {self.title}>'


class NotificationPreference(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    notification_type = db.Column(db.String(50), nullable=False)
    enabled = db.Column(db.Boolean, default=True)

    user = db.relationship('User', backref=db.backref('_user_notificationpreferences', cascade='all, delete-orphan'), lazy=True)

    def __repr__(self):
        return f'<NotificationPreference {self.notification_type}: {self.enabled}>'


# ===== PHASE 1.2: Security =====
class SecurityEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    event_type = db.Column(db.String(50), nullable=False)  # login, logout, password_change, failed_login, data_export
    ip_address = db.Column(db.String(50), nullable=True)
    details = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('_user_securityevents', cascade='all, delete-orphan'), lazy=True)

    def __repr__(self):
        return f'<SecurityEvent {self.event_type}: {self.created_at}>'


class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    table_name = db.Column(db.String(50), nullable=True)
    record_id = db.Column(db.Integer, nullable=True)
    details = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('_user_auditlogs', cascade='all, delete-orphan'), lazy=True)

    def __repr__(self):
        return f'<AuditLog {self.action}: {self.table_name}>'


# ===== PHASE 10.3: API Keys =====
class ApiKey(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    name = db.Column(db.String(100), nullable=False)
    key_hash = db.Column(db.String(256), nullable=False)
    permissions = db.Column(db.String(500), default='read')  # Comma-separated: read, write_transactions, write_budgets, write_goals
    is_active = db.Column(db.Boolean, default=True)
    last_used = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('_user_apikeies', cascade='all, delete-orphan'), lazy=True)

    def __repr__(self):
        return f'<ApiKey {self.name}>'


# ===== PHASE 12: Domain-Specific =====
class SMCContract(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    contract_number = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    contract_value = db.Column(db.Float, default=0.0)
    start_date = db.Column(db.DateTime, nullable=True)
    end_date = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(30), default='active')  # active, completed, suspended
    location = db.Column(db.String(200), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('_user_smccontracts', cascade='all, delete-orphan'), lazy=True)

    def __repr__(self):
        return f'<SMCContract {self.contract_number}>'


class ContractPayment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    contract_id = db.Column(db.Integer, db.ForeignKey('smc_contract.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(200), nullable=True)
    payment_date = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, paid, processing
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    contract = db.relationship('SMCContract', backref=db.backref('payments', cascade='all, delete-orphan'), lazy=True)

    def __repr__(self):
        return f'<ContractPayment {self.amount}>'


class ConstructionWork(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    project_name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    location = db.Column(db.String(200), nullable=True)
    budget = db.Column(db.Float, default=0.0)
    spent = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(30), default='planning')  # planning, in_progress, completed, on_hold
    start_date = db.Column(db.DateTime, nullable=True)
    end_date = db.Column(db.DateTime, nullable=True)
    contractor = db.Column(db.String(200), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('_user_constructionworks', cascade='all, delete-orphan'), lazy=True)

    def __repr__(self):
        return f'<ConstructionWork {self.project_name}>'


class GlobalEntity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    name = db.Column(db.String(150), nullable=False)
    entity_type = db.Column(db.String(50), nullable=False)  # Business, Partnership, Shareholding
    ownership_percent = db.Column(db.Float, default=100.0)
    value = db.Column(db.Float, default=0.0)
    description = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('_user_globalentities', cascade='all, delete-orphan'), lazy=True)

    def __repr__(self):
        return f'<GlobalEntity {self.name}>'


class PasswordResetToken(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    token = db.Column(db.String(256), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False)
    user = db.relationship('User', backref=db.backref('reset_tokens', cascade='all, delete-orphan'), lazy=True)

    def is_expired(self):
        return datetime.utcnow() > self.expires_at

    def __repr__(self):
        return f'<PasswordResetToken {self.id}>'


class EmailVerificationToken(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    token = db.Column(db.String(256), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False)
    user = db.relationship('User', backref=db.backref('verification_tokens', cascade='all, delete-orphan'), lazy=True)

    def is_expired(self):
        return datetime.utcnow() > self.expires_at

    def __repr__(self):
        return f'<EmailVerificationToken {self.id}>'


class PushSubscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    endpoint = db.Column(db.Text, nullable=False)
    p256dh = db.Column(db.String(256), nullable=False)
    auth = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref=db.backref('push_subscriptions', cascade='all, delete-orphan'), lazy=True)

    def __repr__(self):
        return f'<PushSubscription {self.id}>'
