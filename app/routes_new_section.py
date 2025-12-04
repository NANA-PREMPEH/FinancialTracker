@main.route('/projects/<int:project_id>/items/<int:item_id>/toggle', methods=['POST'])
def toggle_project_item(project_id, item_id):
    item = ProjectItem.query.get_or_404(item_id)
    item.is_completed = not item.is_completed
    db.session.commit()
    return jsonify({'success': True, 'is_completed': item.is_completed})

# ===== PROJECT ITEM PAYMENTS =====
@main.route('/projects/<int:project_id>/items/<int:item_id>/payments/add', methods=['POST'])
def add_project_item_payment(project_id, item_id):
    project = Project.query.get_or_404(project_id)
    item = ProjectItem.query.get_or_404(item_id)
    
    amount = float(request.form.get('payment_amount'))
    description = request.form.get('payment_description', '')
    
    payment = ProjectItemPayment(
        project_item_id=item_id,
        amount=amount,
        description=description
    )
    db.session.add(payment)
    db.session.commit()
    flash('Payment added successfully!', 'success')
    return redirect(url_for('main.project_details', id=project_id))

@main.route('/projects/<int:project_id>/items/<int:item_id>/payments/<int:payment_id>/toggle', methods=['POST'])
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
def delete_project_item_payment(project_id, item_id, payment_id):
    payment = ProjectItemPayment.query.get_or_404(payment_id)
    db.session.delete(payment)
    db.session.commit()
    flash('Payment deleted successfully!', 'success')
    return redirect(url_for('main.project_details', id=project_id))
