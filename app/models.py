from . import db
from datetime import datetime

class Wallet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    balance = db.Column(db.Float, default=0.0)
    currency = db.Column(db.String(10), default='GHS')
    icon = db.Column(db.String(10), default='💰')
    wallet_type = db.Column(db.String(20), default='cash')  # cash, bank, crypto, ewallet
    account_number = db.Column(db.String(50), nullable=True)  # For bank accounts
    is_shared = db.Column(db.Boolean, default=False)
    expenses = db.relationship('Expense', backref='wallet', lazy=True)

    def __repr__(self):
        return f'<Wallet {self.name}>'

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    icon = db.Column(db.String(10), default='📝')
    is_custom = db.Column(db.Boolean, default=False)
    expenses = db.relationship('Expense', backref='category', lazy=True)
    budgets = db.relationship('Budget', backref='category', lazy=True)

    def __repr__(self):
        return f'<Category {self.name}>'

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(200), nullable=False)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    wallet_id = db.Column(db.Integer, db.ForeignKey('wallet.id'), nullable=False)
    notes = db.Column(db.Text, nullable=True)
    tags = db.Column(db.String(200), nullable=True)
    receipt_path = db.Column(db.String(300), nullable=True)
    transaction_type = db.Column(db.String(20), default='expense')

    def __repr__(self):
        return f'<Expense {self.amount} - {self.description}>'

class Budget(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    period = db.Column(db.String(20), default='monthly')  # weekly, monthly, yearly
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=True)
    notify_at_75 = db.Column(db.Boolean, default=True)
    notify_at_90 = db.Column(db.Boolean, default=True)
    notify_at_100 = db.Column(db.Boolean, default=True)
    is_active = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f'<Budget {self.category.name} - {self.amount}>'

class RecurringTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
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
    
    def __repr__(self):
        return f'<Project {self.name}>'
    
    @property
    def total_cost(self):
        return sum(item.cost for item in self.items)

class ProjectItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    item_name = db.Column(db.String(200), nullable=False)
    cost = db.Column(db.Float, nullable=False, default=0.0)
    is_completed = db.Column(db.Boolean, default=False)
    created_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<ProjectItem {self.item_name} - {self.cost}>'
