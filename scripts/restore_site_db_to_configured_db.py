import sqlite3
import sys
from pathlib import Path

from sqlalchemy import inspect, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app, db


SOURCE_DB = Path('instance/site.db')
SKIP_TABLES = {'alembic_version', 'backup_history'}


def fetch_sqlite_rows(connection, table_name):
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()
    cursor.execute(f'SELECT * FROM "{table_name}"')
    rows = cursor.fetchall()
    return [dict(row) for row in rows]


def main():
    if not SOURCE_DB.exists():
        raise SystemExit(f'Source database not found: {SOURCE_DB}')

    app = create_app()
    with app.app_context():
        inspector = inspect(db.engine)
        target_tables = set(inspector.get_table_names())
        managed_tables = [table.name for table in db.metadata.sorted_tables]

        with sqlite3.connect(SOURCE_DB) as source_conn:
            source_cursor = source_conn.cursor()
            source_cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            source_tables = {row[0] for row in source_cursor.fetchall()}

            target_user_count = db.session.execute(text('SELECT COUNT(*) FROM user')).scalar_one()
            if target_user_count:
                raise SystemExit('Target database already has users; aborting to avoid overwriting data.')

            imported_counts = {}
            with db.engine.begin() as target_conn:
                target_conn.execute(text('SET FOREIGN_KEY_CHECKS=0'))

                for table_name in managed_tables:
                    if table_name in SKIP_TABLES:
                        continue
                    if table_name not in target_tables or table_name not in source_tables:
                        continue

                    rows = fetch_sqlite_rows(source_conn, table_name)
                    if not rows:
                        continue

                    target_columns = {column['name'] for column in inspector.get_columns(table_name)}
                    cleaned_rows = [
                        {key: value for key, value in row.items() if key in target_columns}
                        for row in rows
                    ]

                    columns = list(cleaned_rows[0].keys())
                    quoted_columns = ', '.join(f'`{column}`' for column in columns)
                    placeholders = ', '.join(f':{column}' for column in columns)

                    target_conn.execute(
                        text(f'INSERT INTO `{table_name}` ({quoted_columns}) VALUES ({placeholders})'),
                        cleaned_rows,
                    )
                    imported_counts[table_name] = len(cleaned_rows)

                target_conn.execute(text('SET FOREIGN_KEY_CHECKS=1'))

        if not imported_counts:
            print('No rows were imported.')
            return

        for table_name, row_count in imported_counts.items():
            print(f'Imported {row_count} rows into {table_name}')


if __name__ == '__main__':
    main()
