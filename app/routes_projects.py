from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from . import db
from .models import (Wallet, Project, ProjectItem, ProjectItemPayment,
                     ProjectCategory, ProjectCategoryExpense,
                     get_or_seed_project_categories)
from datetime import datetime


def register_routes(main):

    @main.route('/projects')
    @login_required
    def projects():
        categories = get_or_seed_project_categories(current_user.id)
        projects = Project.query.filter_by(user_id=current_user.id).order_by(Project.created_date.desc()).all()
        category_expenses = ProjectCategoryExpense.query.filter_by(user_id=current_user.id).order_by(ProjectCategoryExpense.date.desc()).all()
        wallets = Wallet.query.filter_by(user_id=current_user.id).all()

        # Prepare category performance and profit data
        categories_data = []
        for cat in categories:
            cat_projects = [p for p in projects if p.category_id == cat.id]
            paid_income = sum(p.paid_income for p in cat_projects)
            paid_expense = sum(p.paid_expense for p in cat_projects)
            op_expenses = [e for e in category_expenses if e.category_id == cat.id]
            total_op_expense = sum(e.amount for e in op_expenses)
            current_profit = paid_income - (paid_expense + total_op_expense)
            projected_income = sum(p.total_income for p in cat_projects)
            projected_cost = sum(p.total_cost for p in cat_projects)
            projected_profit = projected_income - (projected_cost + total_op_expense)

            categories_data.append({
                'category': cat,
                'projects': cat_projects,
                'projects_count': len(cat_projects),
                'active_count': sum(1 for p in cat_projects if p.total_cost > p.paid_expense or p.total_income > p.paid_income),
                'paid_income': paid_income,
                'paid_expense': paid_expense,
                'operational_expense': total_op_expense,
                'current_profit': current_profit,
                'projected_income': projected_income,
                'projected_cost': projected_cost,
                'projected_profit': projected_profit,
                'expenses_list': op_expenses
            })

        # Uncategorized projects
        uncategorized_projects = [p for p in projects if not p.category_id]

        return render_template('projects.html',
                               projects=projects,
                               categories=categories,
                               categories_data=categories_data,
                               uncategorized_projects=uncategorized_projects,
                               category_expenses=category_expenses,
                               wallets=wallets)

    @main.route('/projects/add', methods=['GET', 'POST'])
    @login_required
    def add_project():
        categories = get_or_seed_project_categories(current_user.id)
        if request.method == 'POST':
            name = request.form.get('name')
            description = request.form.get('description')
            funding_source = request.form.get('funding_source')
            custom_funding_source = request.form.get('custom_funding_source')
            wallet_id = request.form.get('wallet_id')
            category_id = request.form.get('category_id')

            final_category_id = int(category_id) if category_id and category_id.isdigit() else None

            if funding_source == 'wallet' and wallet_id:
                final_funding_source = 'wallet'
                final_wallet_id = int(wallet_id)
                final_custom_source = None
            elif funding_source == 'other' and custom_funding_source:
                final_funding_source = 'other'
                final_wallet_id = None
                final_custom_source = custom_funding_source
            else:
                final_funding_source = funding_source
                final_wallet_id = None
                final_custom_source = None

            project = Project(
                user_id=current_user.id,
                category_id=final_category_id,
                name=name,
                description=description,
                funding_source=final_funding_source,
                wallet_id=final_wallet_id,
                custom_funding_source=final_custom_source
            )
            db.session.add(project)
            db.session.commit()
            flash('Project created successfully!', 'success')
            return redirect(url_for('main.project_details', id=project.id))

        wallets = Wallet.query.filter_by(user_id=current_user.id).all()
        return render_template('add_project.html', wallets=wallets, categories=categories)

    @main.route('/projects/<int:id>')
    @login_required
    def project_details(id):
        project = Project.query.filter_by(id=id, user_id=current_user.id).first_or_404()

        completed_cost = project.paid_expense
        not_completed_cost = project.total_cost - project.paid_expense
        total_income = project.paid_income

        return render_template('project_details.html',
                             project=project,
                             completed_cost=completed_cost,
                             not_completed_cost=not_completed_cost,
                             total_income=total_income,
                             current_profit=project.current_profit,
                             projected_profit=project.projected_profit)

    @main.route('/projects/edit/<int:id>', methods=['GET', 'POST'])
    @login_required
    def edit_project(id):
        project = Project.query.filter_by(id=id, user_id=current_user.id).first_or_404()
        categories = get_or_seed_project_categories(current_user.id)

        if request.method == 'POST':
            project.name = request.form.get('name')
            project.description = request.form.get('description')
            funding_source = request.form.get('funding_source')
            custom_funding_source = request.form.get('custom_funding_source')
            wallet_id = request.form.get('wallet_id')
            category_id = request.form.get('category_id')

            project.category_id = int(category_id) if category_id and category_id.isdigit() else None

            if funding_source == 'wallet' and wallet_id:
                project.funding_source = 'wallet'
                project.wallet_id = int(wallet_id)
                project.custom_funding_source = None
            elif funding_source == 'other' and custom_funding_source:
                project.funding_source = 'other'
                project.wallet_id = None
                project.custom_funding_source = custom_funding_source
            else:
                project.funding_source = funding_source
                project.wallet_id = None
                project.custom_funding_source = None

            db.session.commit()
            flash('Project updated successfully!', 'success')
            return redirect(url_for('main.project_details', id=project.id))

        wallets = Wallet.query.filter_by(user_id=current_user.id).all()
        return render_template('edit_project.html', project=project, wallets=wallets, categories=categories)

    @main.route('/projects/delete/<int:id>', methods=['POST'])
    @login_required
    def delete_project(id):
        project = Project.query.filter_by(id=id, user_id=current_user.id).first_or_404()
        db.session.delete(project)
        db.session.commit()
        flash('Project deleted successfully!', 'success')
        return redirect(url_for('main.projects'))

    @main.route('/projects/categories/create', methods=['POST'])
    @login_required
    def create_project_category():
        name = request.form.get('name') or (request.json.get('name') if request.is_json else None)
        description = request.form.get('description') or (request.json.get('description') if request.is_json else None)

        if not name or not name.strip():
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': 'Category name is required'}), 400
            flash('Category name is required', 'error')
            return redirect(request.referrer or url_for('main.projects'))

        name = name.strip()
        existing = ProjectCategory.query.filter_by(user_id=current_user.id, name=name).first()
        if existing:
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': True, 'category': {'id': existing.id, 'name': existing.name}, 'message': 'Category already exists'})
            flash(f'Category "{name}" already exists!', 'info')
            return redirect(request.referrer or url_for('main.projects'))

        category = ProjectCategory(
            user_id=current_user.id,
            name=name,
            description=description.strip() if description else None
        )
        db.session.add(category)
        db.session.commit()

        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': True,
                'category': {'id': category.id, 'name': category.name},
                'message': 'Category created successfully!'
            })

        flash(f'Category "{name}" created successfully!', 'success')
        return redirect(request.referrer or url_for('main.projects'))

    @main.route('/projects/category/<int:category_id>')
    @login_required
    def category_projects(category_id):
        category = ProjectCategory.query.filter_by(id=category_id, user_id=current_user.id).first_or_404()
        projects = Project.query.filter_by(category_id=category.id, user_id=current_user.id).order_by(Project.created_date.desc()).all()
        category_expenses = ProjectCategoryExpense.query.filter_by(category_id=category.id, user_id=current_user.id).order_by(ProjectCategoryExpense.date.desc()).all()
        wallets = Wallet.query.filter_by(user_id=current_user.id).all()
        all_categories = get_or_seed_project_categories(current_user.id)

        total_paid_income = sum(p.paid_income for p in projects)
        total_paid_expense = sum(p.paid_expense for p in projects)
        total_operational_expense = sum(e.amount for e in category_expenses)
        current_profit = total_paid_income - (total_paid_expense + total_operational_expense)
        total_projected_income = sum(p.total_income for p in projects)
        total_projected_cost = sum(p.total_cost for p in projects)
        projected_profit = total_projected_income - (total_projected_cost + total_operational_expense)

        # Monthly realized profit is based on paid project-item payments and
        # operational expenses recorded in the same calendar month.
        monthly_profit_by_period = {}

        def month_bucket(date):
            period = date.strftime('%Y-%m')
            if period not in monthly_profit_by_period:
                monthly_profit_by_period[period] = {
                    'month': datetime(date.year, date.month, 1),
                    'income': 0.0,
                    'project_expenses': 0.0,
                    'operational_expenses': 0.0,
                }
            return monthly_profit_by_period[period]

        for project in projects:
            for item in project.items:
                for payment in item.payments:
                    if not payment.is_paid or not payment.payment_date:
                        continue
                    bucket = month_bucket(payment.payment_date)
                    if item.item_type == 'income':
                        bucket['income'] += payment.amount
                    else:
                        bucket['project_expenses'] += payment.amount

        for expense in category_expenses:
            if expense.date:
                month_bucket(expense.date)['operational_expenses'] += expense.amount

        monthly_profits = []
        for period in sorted(monthly_profit_by_period, reverse=True):
            entry = monthly_profit_by_period[period]
            entry['profit'] = entry['income'] - entry['project_expenses'] - entry['operational_expenses']
            monthly_profits.append(entry)

        return render_template('category_projects.html',
                               category=category,
                               projects=projects,
                               category_expenses=category_expenses,
                               wallets=wallets,
                               all_categories=all_categories,
                               total_paid_income=total_paid_income,
                               total_paid_expense=total_paid_expense,
                               total_operational_expense=total_operational_expense,
                               current_profit=current_profit,
                               total_projected_income=total_projected_income,
                               total_projected_cost=total_projected_cost,
                               projected_profit=projected_profit,
                               monthly_profits=monthly_profits)

    @main.route('/projects/categories/expenses/add', methods=['POST'])
    @login_required
    def add_category_expense():
        category_id = request.form.get('category_id')
        if not category_id:
            flash('Please select a valid project category.', 'error')
            return redirect(request.referrer or url_for('main.projects'))

        category = ProjectCategory.query.filter_by(id=int(category_id), user_id=current_user.id).first_or_404()
        amount = float(request.form.get('amount', 0))
        expense_name = request.form.get('expense_name', '').strip()
        notes = request.form.get('notes', '').strip()
        date_str = request.form.get('date')
        wallet_id = request.form.get('wallet_id')

        exp_date = datetime.utcnow()
        if date_str:
            try:
                exp_date = datetime.strptime(date_str, '%Y-%m-%d')
            except ValueError:
                pass

        final_wallet_id = int(wallet_id) if wallet_id and wallet_id.isdigit() else None

        expense = ProjectCategoryExpense(
            user_id=current_user.id,
            category_id=category.id,
            amount=amount,
            expense_name=expense_name or f'Operational expense for {category.name}',
            notes=notes,
            date=exp_date,
            wallet_id=final_wallet_id
        )
        db.session.add(expense)
        db.session.commit()
        flash(f'Operational expense "{expense.expense_name}" recorded for "{category.name}"!', 'success')
        return redirect(request.referrer or (url_for('main.projects') + '#category-breakdown'))

    @main.route('/projects/categories/expenses/<int:id>/edit', methods=['POST'])
    @login_required
    def edit_category_expense(id):
        expense = ProjectCategoryExpense.query.filter_by(id=id, user_id=current_user.id).first_or_404()
        expense.expense_name = request.form.get('expense_name', expense.expense_name).strip()
        expense.amount = float(request.form.get('amount', expense.amount))
        expense.notes = request.form.get('notes', '').strip()
        
        category_id = request.form.get('category_id')
        if category_id and category_id.isdigit():
            cat = ProjectCategory.query.filter_by(id=int(category_id), user_id=current_user.id).first()
            if cat:
                expense.category_id = cat.id

        date_str = request.form.get('date')
        if date_str:
            try:
                expense.date = datetime.strptime(date_str, '%Y-%m-%d')
            except ValueError:
                pass

        wallet_id = request.form.get('wallet_id')
        expense.wallet_id = int(wallet_id) if wallet_id and wallet_id.isdigit() else None

        db.session.commit()
        flash('Category operational expense updated successfully!', 'success')
        return redirect(request.referrer or (url_for('main.projects') + '#category-breakdown'))

    @main.route('/projects/categories/expenses/<int:id>/delete', methods=['POST'])
    @login_required
    def delete_category_expense(id):
        expense = ProjectCategoryExpense.query.filter_by(id=id, user_id=current_user.id).first_or_404()
        db.session.delete(expense)
        db.session.commit()
        flash('Category operational expense deleted successfully!', 'success')
        return redirect(request.referrer or (url_for('main.projects') + '#category-breakdown'))

    @main.route('/projects/<int:project_id>/items/add', methods=['POST'])
    @login_required
    def add_project_item(project_id):
        project = Project.query.filter_by(id=project_id, user_id=current_user.id).first_or_404()
        item_name = request.form.get('item_name')
        cost = float(request.form.get('cost', 0))
        description = request.form.get('description', '')
        item_type = request.form.get('item_type', 'expense')

        item = ProjectItem(
            user_id=current_user.id,
            project_id=project_id,
            item_name=item_name,
            cost=cost,
            description=description,
            item_type=item_type
        )
        db.session.add(item)
        db.session.commit()
        db.session.refresh(item)
        flash('Item added successfully!', 'success')
        return redirect(url_for('main.project_details', id=project_id, _anchor=f'item-{item.id}'))

    @main.route('/projects/<int:project_id>/items/<int:item_id>/delete', methods=['POST'])
    @login_required
    def delete_project_item(project_id, item_id):
        project = Project.query.filter_by(id=project_id, user_id=current_user.id).first_or_404()
        item = ProjectItem.query.filter_by(id=item_id, project_id=project_id).first_or_404()
        db.session.delete(item)
        db.session.commit()
        flash('Item deleted successfully!', 'success')
        return redirect(url_for('main.project_details', id=project_id))

    @main.route('/projects/<int:project_id>/items/<int:item_id>/edit', methods=['GET', 'POST'])
    @login_required
    def edit_project_item(project_id, item_id):
        project = Project.query.filter_by(id=project_id, user_id=current_user.id).first_or_404()
        item = ProjectItem.query.filter_by(id=item_id, project_id=project_id).first_or_404()

        if request.method == 'POST':
            item.item_name = request.form.get('item_name')
            item.cost = float(request.form.get('cost', 0))
            item.description = request.form.get('description', '')
            item.item_type = request.form.get('item_type', 'expense')
            db.session.commit()
            flash('Item updated successfully!', 'success')
            return redirect(url_for('main.project_details', id=project_id) + f'#item-{item_id}')

        return render_template('edit_project_item.html', item=item, project=project)

    @main.route('/projects/<int:project_id>/items/<int:item_id>/toggle', methods=['POST'])
    @login_required
    def toggle_project_item(project_id, item_id):
        project = Project.query.filter_by(id=project_id, user_id=current_user.id).first_or_404()
        item = ProjectItem.query.filter_by(id=item_id, project_id=project_id).first_or_404()
        item.is_completed = not item.is_completed
        db.session.commit()
        return jsonify({'success': True, 'is_completed': item.is_completed})

    # ===== PROJECT ITEM PAYMENTS =====
    @main.route('/projects/<int:project_id>/items/<int:item_id>/payments/add', methods=['POST'])
    @login_required
    def add_project_item_payment(project_id, item_id):
        project = Project.query.filter_by(id=project_id, user_id=current_user.id).first_or_404()
        item = ProjectItem.query.filter_by(id=item_id, project_id=project_id).first_or_404()

        amount = float(request.form.get('payment_amount'))
        description = request.form.get('payment_description', '')
        date_str = request.form.get('payment_date')

        payment_date = datetime.utcnow()
        if date_str:
            try:
                payment_date = datetime.strptime(date_str, '%Y-%m-%d')
            except ValueError:
                pass

        payment = ProjectItemPayment(
            user_id=current_user.id,
            project_item_id=item_id,
            amount=amount,
            description=description,
            payment_date=payment_date
        )
        db.session.add(payment)
        db.session.commit()
        flash('Payment added successfully!', 'success')
        return redirect(url_for('main.project_details', id=project_id) + f'#item-{item_id}')

    @main.route('/projects/<int:project_id>/items/<int:item_id>/payments/<int:payment_id>/toggle', methods=['POST'])
    @login_required
    def toggle_project_item_payment(project_id, item_id, payment_id):
        project = Project.query.filter_by(id=project_id, user_id=current_user.id).first_or_404()
        payment = ProjectItemPayment.query.join(ProjectItem).filter(
            ProjectItem.id == item_id,
            ProjectItem.project_id == project_id,
            ProjectItemPayment.id == payment_id
        ).first_or_404()
        payment.is_paid = not payment.is_paid
        if payment.is_paid:
            payment.payment_date = datetime.utcnow()
        else:
            payment.payment_date = None
        db.session.commit()
        return jsonify({'success': True, 'is_paid': payment.is_paid})

    @main.route('/projects/<int:project_id>/items/<int:item_id>/payments/<int:payment_id>/edit', methods=['POST'])
    @login_required
    def edit_project_item_payment(project_id, item_id, payment_id):
        project = Project.query.filter_by(id=project_id, user_id=current_user.id).first_or_404()
        payment = ProjectItemPayment.query.join(ProjectItem).filter(
            ProjectItem.id == item_id,
            ProjectItem.project_id == project_id,
            ProjectItemPayment.id == payment_id
        ).first_or_404()

        amount = float(request.form.get('payment_amount', 0))
        description = request.form.get('payment_description', '')
        date_str = request.form.get('payment_date')

        if date_str:
            try:
                payment.payment_date = datetime.strptime(date_str, '%Y-%m-%d')
            except ValueError:
                pass
        
        payment.amount = amount
        payment.description = description
        
        db.session.commit()
        flash('Payment updated successfully!', 'success')
        return redirect(url_for('main.project_details', id=project_id) + f'#item-{item_id}')

    @main.route('/projects/<int:project_id>/items/<int:item_id>/payments/<int:payment_id>/delete', methods=['POST'])
    @login_required
    def delete_project_item_payment(project_id, item_id, payment_id):
        project = Project.query.filter_by(id=project_id, user_id=current_user.id).first_or_404()
        payment = ProjectItemPayment.query.join(ProjectItem).filter(
            ProjectItem.id == item_id,
            ProjectItem.project_id == project_id,
            ProjectItemPayment.id == payment_id
        ).first_or_404()
        db.session.delete(payment)
        db.session.commit()
        flash('Payment deleted successfully!', 'success')
        return redirect(url_for('main.project_details', id=project_id) + f'#item-{item_id}')
