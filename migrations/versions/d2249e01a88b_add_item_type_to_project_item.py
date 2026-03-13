"""add item_type to project_item

Revision ID: d2249e01a88b
Revises: cf774c0d4df7
Create Date: 2025-12-19 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd2249e01a88b'
down_revision = 'cf774c0d4df7'
branch_labels = None
depends_on = None


def upgrade():
    # Create missing tables that should have been in initial migration
    op.create_table('project',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('funding_source', sa.String(length=100), nullable=False),
        sa.Column('wallet_id', sa.Integer(), nullable=True),
        sa.Column('custom_funding_source', sa.String(length=200), nullable=True),
        sa.Column('created_date', sa.DateTime(), nullable=True),
        sa.Column('is_completed', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['wallet_id'], ['wallet.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('project_item',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('item_name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('cost', sa.Float(), nullable=False),
        sa.Column('item_type', sa.String(length=20), server_default='expense', nullable=True),
        sa.Column('is_completed', sa.Boolean(), nullable=True),
        sa.Column('created_date', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['project.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('project_item_payment',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_item_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('description', sa.String(length=200), nullable=True),
        sa.Column('is_paid', sa.Boolean(), nullable=True),
        sa.Column('payment_date', sa.DateTime(), nullable=True),
        sa.Column('created_date', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['project_item_id'], ['project_item.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('creditor',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('currency', sa.String(length=10), nullable=True),
        sa.Column('description', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('payment_frequency', sa.String(length=20), nullable=True),
        sa.Column('minimum_payment', sa.Float(), nullable=True),
        sa.Column('contact_info', sa.String(length=200), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('wishlist_item',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('category_id', sa.Integer(), nullable=True),
        sa.Column('priority', sa.String(length=20), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['category_id'], ['category.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('financial_summary',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('month', sa.Integer(), nullable=True),
        sa.Column('total_income', sa.Float(), nullable=True),
        sa.Column('total_expense', sa.Float(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_column('project_item', 'item_type')
