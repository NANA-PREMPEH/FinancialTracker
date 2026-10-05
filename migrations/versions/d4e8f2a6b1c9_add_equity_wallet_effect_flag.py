"""add wallet effect flag to equity transactions

Revision ID: d4e8f2a6b1c9
Revises: c9e5f7a1b2d3
Create Date: 2026-10-04
"""
from alembic import op
import sqlalchemy as sa


revision = 'd4e8f2a6b1c9'
down_revision = 'c9e5f7a1b2d3'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('equity_transaction') as batch_op:
        batch_op.add_column(sa.Column('affects_wallet', sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade():
    with op.batch_alter_table('equity_transaction') as batch_op:
        batch_op.drop_column('affects_wallet')
