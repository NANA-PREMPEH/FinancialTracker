import os
import sys
from app import create_app, db
from app.models import Expense, Category, User

app = create_app()

with app.app_context():
    users = User.query.all()
    updated = 0
    for user in users:
        transfer_cat = Category.query.filter_by(name='Transfer', user_id=user.id).first()
        if not transfer_cat:
            transfer_cat = Category(name='Transfer', icon='??', user_id=user.id)
            db.session.add(transfer_cat)
            db.session.commit()
            
        transfers = Expense.query.filter(
            Expense.user_id == user.id,
            (Expense.description.like('Transfer to %') | Expense.description.like('Transfer from %'))
        ).all()
        
        for t in transfers:
            if t.category_id != transfer_cat.id:
                t.category_id = transfer_cat.id
                updated += 1
            # Fix transaction_type for transfers that were wrongly stored as 'expense'/'income'
            if t.transaction_type == 'expense' and t.description.startswith('Transfer to '):
                t.transaction_type = 'transfer_out'
                updated += 1
            elif t.transaction_type == 'income' and t.description.startswith('Transfer from '):
                t.transaction_type = 'transfer_in'
                updated += 1

    db.session.commit()
    print(f'Successfully updated {updated} existing transfer records.')
