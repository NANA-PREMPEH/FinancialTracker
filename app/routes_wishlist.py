from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from . import db
from .models import Expense, Category, Wallet, WishlistItem
from datetime import datetime


def register_routes(main):

    @main.route('/wishlist')
    @login_required
    def wishlist():
        items = WishlistItem.query.filter_by(user_id=current_user.id).all()
        categories = Category.query.filter_by(user_id=current_user.id).all()

        # Custom sort for priority: High > Medium > Low
        priority_map = {'High': 3, 'Medium': 2, 'Low': 1}
        items.sort(key=lambda x: priority_map.get(x.priority, 1), reverse=True)

        return render_template('wishlist.html', items=items, categories=categories)

    @main.route('/wishlist/add', methods=['POST'])
    @login_required
    def add_wishlist_item():
        name = request.form.get('name')
        amount = float(request.form.get('amount', 0))
        category_id = request.form.get('category_id')
        priority = request.form.get('priority', 'Medium')
        notes = request.form.get('notes')

        item = WishlistItem(
            name=name,
            amount=amount,
            category_id=int(category_id) if category_id else None,
            priority=priority,
            notes=notes,
            user_id=current_user.id
        )
        db.session.add(item)
        db.session.commit()
        flash('Item added to wishlist!', 'success')
        return redirect(url_for('main.wishlist'))

    @main.route('/wishlist/edit/<int:id>', methods=['POST'])
    @login_required
    def edit_wishlist_item(id):
        item = WishlistItem.query.filter_by(id=id, user_id=current_user.id).first_or_404()
        item.name = request.form.get('name')
        item.amount = float(request.form.get('amount', 0))
        cat_id = request.form.get('category_id')
        item.category_id = int(cat_id) if cat_id else None
        item.priority = request.form.get('priority', 'Medium')
        item.notes = request.form.get('notes')

        db.session.commit()
        flash('Wishlist item updated!', 'success')
        return redirect(url_for('main.wishlist') + f'#wishlist-{id}')

    @main.route('/wishlist/delete/<int:id>', methods=['POST'])
    @login_required
    def delete_wishlist_item(id):
        item = WishlistItem.query.filter_by(id=id, user_id=current_user.id).first_or_404()
        db.session.delete(item)
        db.session.commit()
        flash('Item removed from wishlist.', 'success')
        return redirect(url_for('main.wishlist'))

    @main.route('/wishlist/execute/<int:id>', methods=['POST'])
    @login_required
    def execute_wishlist_item(id):
        item = WishlistItem.query.filter_by(id=id, user_id=current_user.id).first_or_404()
        wallet_id = request.form.get('wallet_id')
        if wallet_id:
            wallet = Wallet.query.filter_by(id=wallet_id, user_id=current_user.id).first_or_404()
        else:
            wallet = Wallet.query.filter_by(user_id=current_user.id).first()

        if not wallet:
            flash('No wallet found. Please create a wallet first.', 'error')
            return redirect(url_for('main.wishlist'))

        expense = Expense(
            description=item.name,
            amount=item.amount,
            category_id=item.category_id,
            wallet_id=wallet.id,
            transaction_type='expense',
            date=datetime.utcnow(),
            notes=item.notes or "Executed from Wishlist",
            user_id=current_user.id
        )

        # Deduct from wallet
        wallet.balance -= item.amount

        # Save names before deleting (accessing after commit may cause DetachedInstanceError)
        item_name = item.name
        wallet_name = wallet.name

        db.session.add(expense)
        db.session.delete(item)
        db.session.commit()

        flash(f"Executed '{item_name}'! Transaction added to {wallet_name}.", 'success')
        return redirect(url_for('main.wishlist'))
