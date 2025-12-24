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
    # Attempt to add column, handle if exists (though usually migration IS the act of adding)
    # Since we manually added it, this script serves as the record.
    # We won't add complex "if not exists" logic here because standard alembic doesn't.
    # We rely on 'flask db stamp head' to skip running this on the current verified DB.
    op.add_column('project_item', sa.Column('item_type', sa.String(length=20), server_default='expense', nullable=True))


def downgrade():
    op.drop_column('project_item', 'item_type')
