"""Fix missing user_id in financial_summary

Revision ID: 9aee1f55cb75
Revises: e98905970133
Create Date: 2026-03-12 20:40:28.995029

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = '9aee1f55cb75'
down_revision = 'e98905970133'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {column['name'] for column in inspector.get_columns('financial_summary')}
    foreign_keys = inspector.get_foreign_keys('financial_summary')
    has_user_fk = any('user_id' in (fk.get('constrained_columns') or []) for fk in foreign_keys)

    with op.batch_alter_table('financial_summary', schema=None) as batch_op:
        if 'user_id' not in columns:
            batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
        if not has_user_fk:
            batch_op.create_foreign_key(
                'fk_financial_summary_user_id_user',
                'user',
                ['user_id'],
                ['id'],
            )


def downgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    foreign_keys = inspector.get_foreign_keys('financial_summary')
    has_named_fk = any(
        fk.get('name') == 'fk_financial_summary_user_id_user'
        for fk in foreign_keys
    )
    columns = {column['name'] for column in inspector.get_columns('financial_summary')}

    with op.batch_alter_table('financial_summary', schema=None) as batch_op:
        if has_named_fk:
            batch_op.drop_constraint('fk_financial_summary_user_id_user', type_='foreignkey')
        if 'user_id' in columns:
            batch_op.drop_column('user_id')
