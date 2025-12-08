import logging
from app import create_app,db
from app.models import FinancialSummary

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = create_app()

with app.app_context():
    try:
        db.create_all()
        logger.info("Database tables updated successfully!")
        
        # Verify table existence
        inspector = db.inspect(db.engine)
        tables = inspector.get_table_names()
        if 'financial_summary' in tables:
            logger.info("financial_summary table confirmed.")
        else:
            logger.error("financial_summary table NOT found.")
            
    except Exception as e:
        logger.error(f"Error updating database: {e}")
