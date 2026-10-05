"""link capital allocations to equity movements

Revision ID: e7a3c5d9f2b4
Revises: d4e8f2a6b1c9
Create Date: 2026-10-05
"""
from alembic import op
import sqlalchemy as sa


revision = 'e7a3c5d9f2b4'
down_revision = 'd4e8f2a6b1c9'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('capital_allocation') as batch_op:
        batch_op.add_column(sa.Column('equity_transaction_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_capital_allocation_equity_transaction_id', 'equity_transaction',
            ['equity_transaction_id'], ['id']
        )


def downgrade():
    with op.batch_alter_table('capital_allocation') as batch_op:
        batch_op.drop_constraint('fk_capital_allocation_equity_transaction_id', type_='foreignkey')
        batch_op.drop_column('equity_transaction_id')
