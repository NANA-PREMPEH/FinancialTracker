import os
from dotenv import load_dotenv
import pymysql

load_dotenv(override=True)

db_url = os.environ.get('DATABASE_URL')

if not db_url or 'mysql' not in db_url:
    print("Not a MySQL URL.")
else:
    try:
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
        
        tables = ['project_item_payment', 'debt_payment', 'debtor_payment', 'contract_payment']
        for t in tables:
            cursor.execute(f"SELECT COUNT(*), SUM(amount) FROM {t};")
            res = cursor.fetchone()
            print(f"Table {t}: {res[0]} records, Total Amount: {res[1]}")
            
        conn.close()
    except Exception as e:
        print(f"MySQL Error: {e}")
