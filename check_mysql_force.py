import os
from dotenv import load_dotenv
import pymysql

# FORCE OVERRIDE
load_dotenv(override=True)

db_url = os.environ.get('DATABASE_URL')
print(f"Connecting to: {db_url}")

if not db_url or 'mysql' not in db_url:
    print("Not a MySQL URL.")
else:
    try:
        # Simple parse: mysql+pymysql://root:root@localhost:3306/fintrackdb
        part1 = db_url.split('://')[1]
        creds, host_part = part1.split('@')
        user, password = creds.split(':')
        host_db = host_part.split('/')
        host = host_db[0].split(':')[0]
        port = int(host_db[0].split(':')[1]) if ':' in host_db[0] else 3306
        db_name = host_db[1]
        
        conn = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            db=db_name
        )
        cursor = conn.cursor()
        print(f"Connected to MySQL: {db_name}")
        
        cursor.execute("SHOW TABLES;")
        tables = [t[0] for t in cursor.fetchall()]
        print("Tables:", tables)
        
        for t in ['expense', 'financial_summary', 'user', 'wallet']:
            if t in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {t};")
                print(f"Table {t}: {cursor.fetchone()[0]} records")
            else:
                print(f"Table {t}: Missing")
            
        if 'user' in tables:
            cursor.execute("SELECT id, email FROM user;")
            print("Users:", cursor.fetchall())
            
        if 'expense' in tables:
             cursor.execute("SELECT date, amount, transaction_type FROM expense ORDER BY date DESC LIMIT 5;")
             print("Recent Expenses:", cursor.fetchall())
             
        if 'financial_summary' in tables:
             cursor.execute("SELECT year, month, total_expense FROM financial_summary ORDER BY year DESC, month DESC LIMIT 5;")
             print("Recent Summaries:", cursor.fetchall())

        conn.close()
    except Exception as e:
        print(f"MySQL Error: {e}")
