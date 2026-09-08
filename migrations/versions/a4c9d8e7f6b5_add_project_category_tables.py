"""add project category tables

Revision ID: a4c9d8e7f6b5
Revises: f3c7a2d9e8b1
Create Date: 2026-09-08

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = 'a4c9d8e7f6b5'
down_revision = 'f3c7a2d9e8b1'
branch_labels = None
depends_on = None


def upgrade():
    """Create the schema used by the Projects & Categories feature.

    The checks keep this safe for databases where part of the feature schema
    was created manually or by an earlier deployment.
    """
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if 'project_category' not in tables:
        op.create_table(
            'project_category',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['user.id']),
            sa.PrimaryKeyConstraint('id'),
        )

    if 'project_category_expense' not in tables:
        op.create_table(
            'project_category_expense',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('category_id', sa.Integer(), nullable=False),
            sa.Column('amount', sa.Float(), nullable=False, server_default='0'),
            sa.Column('expense_name', sa.String(length=200), nullable=False),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('date', sa.DateTime(), nullable=True),
            sa.Column('wallet_id', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['user.id']),
            sa.ForeignKeyConstraint(['category_id'], ['project_category.id']),
            sa.ForeignKeyConstraint(['wallet_id'], ['wallet.id']),
            sa.PrimaryKeyConstraint('id'),
        )

    # Refresh inspection after creating the category table.
    inspector = inspect(bind)
    project_columns = {column['name'] for column in inspector.get_columns('project')}
    project_foreign_keys = inspector.get_foreign_keys('project')
    has_category_fk = any(
        fk.get('referred_table') == 'project_category'
        and 'category_id' in (fk.get('constrained_columns') or [])
        for fk in project_foreign_keys
    )

    if 'category_id' not in project_columns or not has_category_fk:
        with op.batch_alter_table('project', schema=None) as batch_op:
            if 'category_id' not in project_columns:
                batch_op.add_column(sa.Column('category_id', sa.Integer(), nullable=True))
            if not has_category_fk:
                batch_op.create_foreign_key(
                    'fk_project_category',
                    'project_category',
                    ['category_id'],
                    ['id'],
                )


def downgrade():
    bind = op.get_bind()
    inspector = inspect(bind)

    if 'project' in inspector.get_table_names():
        columns = {column['name'] for column in inspector.get_columns('project')}
        foreign_keys = inspector.get_foreign_keys('project')
        has_category_fk = any(
            fk.get('name') == 'fk_project_category'
            for fk in foreign_keys
        )
        if 'category_id' in columns:
            with op.batch_alter_table('project', schema=None) as batch_op:
                if has_category_fk:
                    batch_op.drop_constraint('fk_project_category', type_='foreignkey')
                batch_op.drop_column('category_id')

    tables = set(inspect(bind).get_table_names())
    if 'project_category_expense' in tables:
        op.drop_table('project_category_expense')
    if 'project_category' in tables:
        op.drop_table('project_category')
