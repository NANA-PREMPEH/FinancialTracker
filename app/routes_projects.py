from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from . import db
from .models import Wallet, Project, ProjectItem, ProjectItemPayment
from datetime import datetime


def register_routes(main):

    @main.route('/projects')
    @login_required
    def projects():
        projects = Project.query.order_by(Project.created_date.desc()).all()
        return render_template('projects.html', projects=projects)

    @main.route('/projects/add', methods=['GET', 'POST'])
    @login_required
    def add_project():
        if request.method == 'POST':
            name = request.form.get('name')
            description = request.form.get('description')
            funding_source = request.form.get('funding_source')
            custom_funding_source = request.form.get('custom_funding_source')
            wallet_id = request.form.get('wallet_id')

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

        wallets = Wallet.query.all()
        return render_template('add_project.html', wallets=wallets)

    @main.route('/projects/<int:id>')
    @login_required
    def project_details(id):
        project = Project.query.get_or_404(id)

        completed_cost = project.paid_expense
        not_completed_cost = project.total_cost - project.paid_expense
        total_income = project.paid_income
        net_cost = project.total_cost - project.total_income

        return render_template('project_details.html',
                             project=project,
                             completed_cost=completed_cost,
                             not_completed_cost=not_completed_cost,
                             total_income=total_income,
                             net_cost=project.total_cost - project.total_income)

    @main.route('/projects/edit/<int:id>', methods=['GET', 'POST'])
    @login_required
    def edit_project(id):
        project = Project.query.get_or_404(id)

        if request.method == 'POST':
            project.name = request.form.get('name')
            project.description = request.form.get('description')
            funding_source = request.form.get('funding_source')
            custom_funding_source = request.form.get('custom_funding_source')
            wallet_id = request.form.get('wallet_id')

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

        wallets = Wallet.query.all()
        return render_template('edit_project.html', project=project, wallets=wallets)

    @main.route('/projects/delete/<int:id>', methods=['POST'])
    @login_required
    def delete_project(id):
        project = Project.query.get_or_404(id)
        db.session.delete(project)
        db.session.commit()
        flash('Project deleted successfully!', 'success')
        return redirect(url_for('main.projects'))

    @main.route('/projects/<int:project_id>/items/add', methods=['POST'])
    @login_required
    def add_project_item(project_id):
        project = Project.query.get_or_404(project_id)
        item_name = request.form.get('item_name')
        cost = float(request.form.get('cost', 0))
        description = request.form.get('description', '')
        item_type = request.form.get('item_type', 'expense')

        item = ProjectItem(
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
        item = ProjectItem.query.get_or_404(item_id)
        db.session.delete(item)
        db.session.commit()
        flash('Item deleted successfully!', 'success')
        return redirect(url_for('main.project_details', id=project_id))

    @main.route('/projects/<int:project_id>/items/<int:item_id>/edit', methods=['GET', 'POST'])
    @login_required
    def edit_project_item(project_id, item_id):
        item = ProjectItem.query.get_or_404(item_id)
        project = Project.query.get_or_404(project_id)

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
        item = ProjectItem.query.get_or_404(item_id)
        item.is_completed = not item.is_completed
        db.session.commit()
        return jsonify({'success': True, 'is_completed': item.is_completed})

    # ===== PROJECT ITEM PAYMENTS =====
    @main.route('/projects/<int:project_id>/items/<int:item_id>/payments/add', methods=['POST'])
    @login_required
    def add_project_item_payment(project_id, item_id):
        project = Project.query.get_or_404(project_id)
        item = ProjectItem.query.get_or_404(item_id)

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
        payment = ProjectItemPayment.query.get_or_404(payment_id)
        payment.is_paid = not payment.is_paid
        if payment.is_paid:
            payment.payment_date = datetime.utcnow()
        else:
            payment.payment_date = None
        db.session.commit()
        return jsonify({'success': True, 'is_paid': payment.is_paid})

    @main.route('/projects/<int:project_id>/items/<int:item_id>/payments/<int:payment_id>/delete', methods=['POST'])
    @login_required
    def delete_project_item_payment(project_id, item_id, payment_id):
        payment = ProjectItemPayment.query.get_or_404(payment_id)
        db.session.delete(payment)
        db.session.commit()
        flash('Payment deleted successfully!', 'success')
        return redirect(url_for('main.project_details', id=project_id) + f'#item-{item_id}')
