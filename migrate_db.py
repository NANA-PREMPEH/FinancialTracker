import sqlite3
import pymysql
from datetime import datetime

# Configuration
SQLITE_DB = 'instance/expenses.db'
MYSQL_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'root',
    'database': 'fintrackdb',
    'cursorclass': pymysql.cursors.DictCursor
}

def get_sqlite_connection():
    conn = sqlite3.connect(SQLITE_DB)
    conn.row_factory = sqlite3.Row
    return conn

def get_mysql_connection(db_name=None):
    config = MYSQL_CONFIG.copy()
    if db_name:
        config['database'] = db_name
    else:
        del config['database']
    return pymysql.connect(**config)

def create_database():
    conn = get_mysql_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {MYSQL_CONFIG['database']}")
        print(f"Database '{MYSQL_CONFIG['database']}' created or already exists.")
    finally:
        conn.close()

def create_mysql_tables(cursor):
    # Create tables in dependency order
    
    # Category
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS category (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(50) NOT NULL UNIQUE,
        icon VARCHAR(10) DEFAULT '📝',
        is_custom BOOLEAN DEFAULT FALSE
    )
    """)

    # Wallet
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS wallet (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        balance FLOAT DEFAULT 0.0,
        currency VARCHAR(10) DEFAULT 'GHS',
        icon VARCHAR(10) DEFAULT '💰',
        wallet_type VARCHAR(20) DEFAULT 'cash',
        is_shared BOOLEAN DEFAULT FALSE
    )
    """)

    # Expense
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS expense (
        id INT AUTO_INCREMENT PRIMARY KEY,
        amount FLOAT NOT NULL,
        description VARCHAR(200) NOT NULL,
        date DATETIME NOT NULL,
        category_id INT NOT NULL,
        wallet_id INT NOT NULL,
        notes TEXT,
        tags VARCHAR(200),
        receipt_path VARCHAR(300),
        transaction_type VARCHAR(20) DEFAULT 'expense',
        FOREIGN KEY (category_id) REFERENCES category(id),
        FOREIGN KEY (wallet_id) REFERENCES wallet(id)
    )
    """)

    # Budget
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS budget (
        id INT AUTO_INCREMENT PRIMARY KEY,
        category_id INT NOT NULL,
        amount FLOAT NOT NULL,
        period VARCHAR(20) DEFAULT 'monthly',
        start_date DATETIME NOT NULL,
        end_date DATETIME,
        notify_at_75 BOOLEAN DEFAULT TRUE,
        notify_at_90 BOOLEAN DEFAULT TRUE,
        notify_at_100 BOOLEAN DEFAULT TRUE,
        is_active BOOLEAN DEFAULT TRUE,
        FOREIGN KEY (category_id) REFERENCES category(id)
    )
    """)

    # RecurringTransaction
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS recurring_transaction (
        id INT AUTO_INCREMENT PRIMARY KEY,
        amount FLOAT NOT NULL,
        description VARCHAR(200) NOT NULL,
        category_id INT NOT NULL,
        wallet_id INT NOT NULL,
        transaction_type VARCHAR(20) DEFAULT 'expense',
        frequency VARCHAR(20) NOT NULL,
        start_date DATETIME NOT NULL,
        end_date DATETIME,
        last_created DATETIME,
        next_due DATETIME,
        is_active BOOLEAN DEFAULT TRUE,
        notes TEXT,
        FOREIGN KEY (category_id) REFERENCES category(id),
        FOREIGN KEY (wallet_id) REFERENCES wallet(id)
    )
    """)
    
    # ExchangeRate
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS exchange_rate (
        id INT AUTO_INCREMENT PRIMARY KEY,
        from_currency VARCHAR(10) NOT NULL,
        to_currency VARCHAR(10) NOT NULL,
        rate FLOAT NOT NULL,
        date DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

def migrate_data():
    print("Starting migration...")
    
    create_database()
    
    sqlite_conn = get_sqlite_connection()
    mysql_conn = get_mysql_connection(MYSQL_CONFIG['database'])
    
    try:
        sqlite_cursor = sqlite_conn.cursor()
        
        # Debug: List tables
        sqlite_cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = sqlite_cursor.fetchall()
        print("SQLite Tables:", [t['name'] for t in tables])
        
        mysql_cursor = mysql_conn.cursor()
        
        # 1. Create Tables
        print("Creating MySQL tables...")
        create_mysql_tables(mysql_cursor)
        
        # 2. Migrate Categories
        print("Migrating Categories...")
        sqlite_cursor.execute("SELECT * FROM category")
        categories = sqlite_cursor.fetchall()
        for cat in categories:
            mysql_cursor.execute(
                "INSERT IGNORE INTO category (id, name, icon, is_custom) VALUES (%s, %s, %s, %s)",
                (cat['id'], cat['name'], cat['icon'], cat['is_custom'])
            )
            
        # 3. Migrate Wallets
        print("Migrating Wallets...")
        sqlite_cursor.execute("SELECT * FROM wallet")
        wallets = sqlite_cursor.fetchall()
        for wallet in wallets:
            mysql_cursor.execute(
                "INSERT IGNORE INTO wallet (id, name, balance, currency, icon, wallet_type, is_shared) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (wallet['id'], wallet['name'], wallet['balance'], wallet['currency'], wallet['icon'], wallet['wallet_type'], wallet['is_shared'])
            )
            
        # 4. Migrate Expenses
        print("Migrating Expenses...")
        sqlite_cursor.execute("SELECT * FROM expense")
        expenses = sqlite_cursor.fetchall()
        for exp in expenses:
            mysql_cursor.execute(
                """INSERT IGNORE INTO expense 
                (id, amount, description, date, category_id, wallet_id, notes, tags, receipt_path, transaction_type) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (exp['id'], exp['amount'], exp['description'], exp['date'], exp['category_id'], exp['wallet_id'], exp['notes'], exp['tags'], exp['receipt_path'], exp['transaction_type'])
            )

        # 5. Migrate Budgets
        print("Migrating Budgets...")
        sqlite_cursor.execute("SELECT * FROM budget")
        budgets = sqlite_cursor.fetchall()
        for budget in budgets:
            mysql_cursor.execute(
                """INSERT IGNORE INTO budget 
                (id, category_id, amount, period, start_date, end_date, notify_at_75, notify_at_90, notify_at_100, is_active) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (budget['id'], budget['category_id'], budget['amount'], budget['period'], budget['start_date'], budget['end_date'], budget['notify_at_75'], budget['notify_at_90'], budget['notify_at_100'], budget['is_active'])
            )

        # 6. Migrate Recurring Transactions
        print("Migrating Recurring Transactions...")
        sqlite_cursor.execute("SELECT * FROM recurring_transaction")
        recurring = sqlite_cursor.fetchall()
        for rec in recurring:
            mysql_cursor.execute(
                """INSERT IGNORE INTO recurring_transaction 
                (id, amount, description, category_id, wallet_id, transaction_type, frequency, start_date, end_date, last_created, next_due, is_active, notes) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (rec['id'], rec['amount'], rec['description'], rec['category_id'], rec['wallet_id'], rec['transaction_type'], rec['frequency'], rec['start_date'], rec['end_date'], rec['last_created'], rec['next_due'], rec['is_active'], rec['notes'])
            )
            
        mysql_conn.commit()
        print("Migration completed successfully!")
        
    except Exception as e:
        print(f"Error during migration: {e}")
        mysql_conn.rollback()
    finally:
        sqlite_conn.close()
        mysql_conn.close()

if __name__ == "__main__":
    migrate_data()
