"""link creditor records to their wallet transactions

Revision ID: f3c7a2d9e8b1
Revises: 069d3b1994a3
Create Date: 2026-08-07
"""
from alembic import op
import sqlalchemy as sa


revision = 'f3c7a2d9e8b1'
down_revision = '069d3b1994a3'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('expense', schema=None) as batch_op:
        batch_op.add_column(sa.Column('creditor_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_expense_creditor_id', 'creditor', ['creditor_id'], ['id'])

    with op.batch_alter_table('debt_payment', schema=None) as batch_op:
        batch_op.add_column(sa.Column('expense_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_debt_payment_expense_id', 'expense', ['expense_id'], ['id'])
        batch_op.create_unique_constraint('uq_debt_payment_expense_id', ['expense_id'])


def downgrade():
    with op.batch_alter_table('debt_payment', schema=None) as batch_op:
        batch_op.drop_constraint('uq_debt_payment_expense_id', type_='unique')
        batch_op.drop_constraint('fk_debt_payment_expense_id', type_='foreignkey')
        batch_op.drop_column('expense_id')

    with op.batch_alter_table('expense', schema=None) as batch_op:
        batch_op.drop_constraint('fk_expense_creditor_id', type_='foreignkey')
        batch_op.drop_column('creditor_id')
