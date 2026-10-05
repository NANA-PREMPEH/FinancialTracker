"""link project transactions to equity allocations

Revision ID: c9e5f7a1b2d3
Revises: b8e4f1c2d3a6
Create Date: 2026-10-04
"""
from alembic import op
import sqlalchemy as sa


revision = 'c9e5f7a1b2d3'
down_revision = 'b8e4f1c2d3a6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('expense') as batch_op:
        batch_op.add_column(sa.Column('project_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_expense_project_id', 'project', ['project_id'], ['id'])
    with op.batch_alter_table('capital_allocation') as batch_op:
        batch_op.add_column(sa.Column('expense_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_capital_allocation_expense_id', 'expense', ['expense_id'], ['id'])
        batch_op.create_unique_constraint('uq_capital_allocation_expense_id', ['expense_id'])


def downgrade():
    with op.batch_alter_table('capital_allocation') as batch_op:
        batch_op.drop_constraint('uq_capital_allocation_expense_id', type_='unique')
        batch_op.drop_constraint('fk_capital_allocation_expense_id', type_='foreignkey')
        batch_op.drop_column('expense_id')
    with op.batch_alter_table('expense') as batch_op:
        batch_op.drop_constraint('fk_expense_project_id', type_='foreignkey')
        batch_op.drop_column('project_id')
