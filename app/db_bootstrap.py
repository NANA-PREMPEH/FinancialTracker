from flask_migrate import stamp
from sqlalchemy import inspect

from . import db


def bootstrap_database():
    """Create the current schema when the configured database is effectively blank."""
    inspector = inspect(db.engine)
    existing_tables = set(inspector.get_table_names())
    managed_tables = set(db.metadata.tables.keys())
    existing_managed_tables = existing_tables & managed_tables

    if existing_managed_tables:
        return False

    db.create_all()
    stamp(revision='head')
    return True
