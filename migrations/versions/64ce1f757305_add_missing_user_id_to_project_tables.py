"""add missing user_id to project tables

Revision ID: 64ce1f757305
Revises: 9aee1f55cb75
Create Date: 2026-03-12 21:41:51.662946

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = '64ce1f757305'
down_revision = '9aee1f55cb75'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)

    table_configs = [
        ('project', 'fk_project_user'),
        ('project_item', 'fk_project_item_user'),
        ('project_item_payment', 'fk_project_item_payment_user'),
    ]

    for table_name, fk_name in table_configs:
        columns = {column['name'] for column in inspector.get_columns(table_name)}
        foreign_keys = inspector.get_foreign_keys(table_name)
        has_user_fk = any('user_id' in (fk.get('constrained_columns') or []) for fk in foreign_keys)

        with op.batch_alter_table(table_name, schema=None) as batch_op:
            if 'user_id' not in columns:
                batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
            if not has_user_fk:
                batch_op.create_foreign_key(fk_name, 'user', ['user_id'], ['id'])


def downgrade():
    bind = op.get_bind()
    inspector = inspect(bind)

    table_configs = [
        ('project_item_payment', 'fk_project_item_payment_user'),
        ('project_item', 'fk_project_item_user'),
        ('project', 'fk_project_user'),
    ]

    for table_name, fk_name in table_configs:
        columns = {column['name'] for column in inspector.get_columns(table_name)}
        foreign_keys = inspector.get_foreign_keys(table_name)
        has_named_fk = any(fk.get('name') == fk_name for fk in foreign_keys)

        with op.batch_alter_table(table_name, schema=None) as batch_op:
            if has_named_fk:
                batch_op.drop_constraint(fk_name, type_='foreignkey')
            if 'user_id' in columns:
                batch_op.drop_column('user_id')
