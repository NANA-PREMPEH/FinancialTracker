"""add equity capital tracking

Revision ID: b8e4f1c2d3a6
Revises: a4c9d8e7f6b5
Create Date: 2026-10-04
"""
from alembic import op
import sqlalchemy as sa

revision = 'b8e4f1c2d3a6'
down_revision = 'a4c9d8e7f6b5'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('equity_capital',
        sa.Column('id', sa.Integer(), primary_key=True), sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('category_id', sa.Integer(), nullable=False, unique=True), sa.Column('initial_capital', sa.Float(), nullable=True),
        sa.Column('initial_capital_date', sa.DateTime(), nullable=True), sa.Column('business_name', sa.String(200)),
        sa.Column('notes', sa.Text()), sa.Column('created_at', sa.DateTime()), sa.Column('updated_at', sa.DateTime()),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']), sa.ForeignKeyConstraint(['category_id'], ['project_category.id']))
    op.create_table('equity_transaction',
        sa.Column('id', sa.Integer(), primary_key=True), sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('equity_capital_id', sa.Integer(), nullable=False), sa.Column('transaction_type', sa.String(30), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False), sa.Column('date', sa.DateTime(), nullable=False),
        sa.Column('description', sa.String(300)), sa.Column('partner_name', sa.String(150)), sa.Column('wallet_id', sa.Integer(), nullable=False),
        sa.Column('journal_entry_id', sa.Integer()), sa.Column('notes', sa.Text()), sa.Column('created_at', sa.DateTime()),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']), sa.ForeignKeyConstraint(['equity_capital_id'], ['equity_capital.id']),
        sa.ForeignKeyConstraint(['wallet_id'], ['wallet.id']), sa.ForeignKeyConstraint(['journal_entry_id'], ['journal_entry.id']))
    op.create_table('capital_allocation',
        sa.Column('id', sa.Integer(), primary_key=True), sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('equity_capital_id', sa.Integer(), nullable=False), sa.Column('allocation_type', sa.String(30), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False), sa.Column('date', sa.DateTime(), nullable=False), sa.Column('description', sa.String(300)),
        sa.Column('project_id', sa.Integer()), sa.Column('funding_source', sa.String(30), nullable=False), sa.Column('notes', sa.Text()), sa.Column('created_at', sa.DateTime()),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']), sa.ForeignKeyConstraint(['equity_capital_id'], ['equity_capital.id']), sa.ForeignKeyConstraint(['project_id'], ['project.id']))


def downgrade():
    op.drop_table('capital_allocation')
    op.drop_table('equity_transaction')
    op.drop_table('equity_capital')
