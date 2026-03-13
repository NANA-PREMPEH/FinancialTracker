from app import create_app, db
from sqlalchemy import text

app = create_app()
with app.app_context():
    # 1. Add user_id column to tables if missing (MySQL)
    child_tables = [
        'project_item', 'project_item_payment', 'goal_task', 
        'goal_milestone', 'dividend', 'debtor_payment', 'contract_payment',
        'debt_payment'
    ]
    
    for table in child_tables:
        try:
            print(f"Adding user_id to {table}...")
            db.session.execute(text(f"ALTER TABLE `{table}` ADD COLUMN user_id INT"))
            db.session.commit()
        except Exception as e:
            print(f"Column might already exist in {table}: {e}")
            db.session.rollback()

    # 2. Populate user_id from parents
    # project_item -> project
    db.session.execute(text("""
        UPDATE project_item pi 
        JOIN project p ON pi.project_id = p.id 
        SET pi.user_id = p.user_id 
        WHERE pi.user_id IS NULL
    """))
    
    # project_item_payment -> project_item -> project
    db.session.execute(text("""
        UPDATE project_item_payment pip 
        JOIN project_item pi ON pip.project_item_id = pi.id 
        JOIN project p ON pi.project_id = p.id 
        SET pip.user_id = p.user_id 
        WHERE pip.user_id IS NULL
    """))
    
    # goal_task -> goal
    db.session.execute(text("""
        UPDATE goal_task gt 
        JOIN goal g ON gt.goal_id = g.id 
        SET gt.user_id = g.user_id 
        WHERE gt.user_id IS NULL
    """))
    
    # goal_milestone -> goal
    db.session.execute(text("""
        UPDATE goal_milestone gm 
        JOIN goal g ON gm.goal_id = g.id 
        SET gm.user_id = g.user_id 
        WHERE gm.user_id IS NULL
    """))
    
    # dividend -> investment
    db.session.execute(text("""
        UPDATE dividend d 
        JOIN investment i ON d.investment_id = i.id 
        SET d.user_id = i.user_id 
        WHERE d.user_id IS NULL
    """))
    
    # debtor_payment -> debtor
    db.session.execute(text("""
        UPDATE debtor_payment dp 
        JOIN debtor d ON dp.debtor_id = d.id 
        SET dp.user_id = d.user_id 
        WHERE dp.user_id IS NULL
    """))
    
    # contract_payment -> smc_contract
    db.session.execute(text("""
        UPDATE contract_payment cp 
        JOIN smc_contract sc ON cp.contract_id = sc.id 
        SET cp.user_id = sc.user_id 
        WHERE cp.user_id IS NULL
    """))

    # debt_payment -> creditor
    db.session.execute(text("""
        UPDATE debt_payment dp 
        JOIN creditor c ON dp.creditor_id = c.id 
        SET dp.user_id = c.user_id 
        WHERE dp.user_id IS NULL
    """))

    db.session.commit()
    print("Child migration complete.")
