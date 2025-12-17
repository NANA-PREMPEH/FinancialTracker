import logging
from sqlalchemy import text
from app import create_app, db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = create_app()

with app.app_context():
    try:
        # Check if column exists first (MySQL specific or generic)
        # For MySQL, we can try to add it and catch exception, or check information_schema.
        # Simplest is to try adding it.
        
        logger.info("Attempting to add 'item_type' column to 'project_item' table...")
        
        with db.engine.connect() as connection:
            # Using transaction
            trans = connection.begin()
            try:
                # RAW SQL (MySQL syntax compatible)
                connection.execute(text("ALTER TABLE project_item ADD COLUMN item_type VARCHAR(20) DEFAULT 'expense'"))
                trans.commit()
                logger.info("Successfully added 'item_type' column.")
            except Exception as e:
                trans.rollback()
                if "Duplicate column" in str(e) or "1060" in str(e): # 1060 is Duplicate column name code
                     logger.info("Column 'item_type' already exists.")
                else:
                    # Provide more details if it's another error
                    logger.error(f"Error executing ALTER TABLE: {e}")
                    # Verify if column exists via description
                    try:
                        result = connection.execute(text("DESCRIBE project_item"))
                        columns = [row[0] for row in result]
                        if 'item_type' in columns:
                             logger.info("Verified: Column 'item_type' exists.")
                        else:
                             logger.error("Verified: Column 'item_type' DOES NOT exist.")
                    except Exception as verify_err:
                        logger.error(f"Could not verify column existence: {verify_err}")

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
