"""Add income_source to expense

Revision ID: c9f4a8b2e1d7
Revises: 566f01fc9d16
Create Date: 2026-05-17 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c9f4a8b2e1d7'
down_revision = '566f01fc9d16'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('expense', schema=None) as batch_op:
        batch_op.add_column(sa.Column('income_source', sa.String(length=150), nullable=True))


def downgrade():
    with op.batch_alter_table('expense', schema=None) as batch_op:
        batch_op.drop_column('income_source')
