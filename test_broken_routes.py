from app import create_app, db
from app.models import User
import sys
import traceback

app = create_app()
app.config['TESTING'] = True

with app.test_client() as client:
    with app.app_context():
        user = User.query.first()
        
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)
        sess['_fresh'] = True
        
    routes = [
        '/budget-planning',
        '/investments/',
        '/net-worth',
        '/fixed-assets',
        '/banking',
        '/accounting',
        '/smc',
        '/construction-works',
        '/global-finance',
        '/newsletter'
    ]
    
    with open('missing_templates.txt', 'w', encoding='utf-8') as f:
        for r in routes:
            try:
                resp = client.get(r)
                f.write(f"[{r}] 200 OK\n")
            except Exception as e:
                # Get the exception type and message
                err_type = type(e).__name__
                f.write(f"[{r}] {err_type}: {str(e)}\n")
