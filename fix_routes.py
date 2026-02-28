import io

with open('app/routes.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = '''                return redirect(url_for('main.add_expense'))
                
            # Create the withdrawal record (source wallet)
            expense_out = Expense('''

if target not in content:
    target = target.replace('\n', '\r\n')

replacement = '''                return redirect(url_for('main.add_expense'))
                
            # Ensure "Transfer" category exists for this user
            transfer_cat = Category.query.filter_by(name='Transfer', user_id=current_user.id).first()
            if not transfer_cat:
                transfer_cat = Category(name='Transfer', icon='??', user_id=current_user.id)
                db.session.add(transfer_cat)
                db.session.flush() # flush to get ID
            category_id = transfer_cat.id
                
            # Create the withdrawal record (source wallet)
            expense_out = Expense('''

if '\r\n' in target:
    replacement = replacement.replace('\n', '\r\n')

if target in content:
    new_content = content.replace(target, replacement)
    with open('app/routes.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print('Success')
else:
    print('Target not found')
