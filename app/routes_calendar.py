from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from . import db
from .models import CalendarEvent, RecurringTransaction
from datetime import datetime, timedelta
import calendar as cal_module

calendar_bp = Blueprint('calendar', __name__)


@calendar_bp.route('/calendar')
@login_required
def calendar_view():
    year = request.args.get('year', datetime.now().year, type=int)
    month = request.args.get('month', datetime.now().month, type=int)

    first_day = datetime(year, month, 1)
    last_day = datetime(year, month, cal_module.monthrange(year, month)[1], 23, 59, 59)

    events = CalendarEvent.query.filter(
        CalendarEvent.user_id == current_user.id,
        CalendarEvent.event_date >= first_day,
        CalendarEvent.event_date <= last_day
    ).order_by(CalendarEvent.event_date).all()

    # Build calendar grid
    cal = cal_module.Calendar(firstweekday=0)
    weeks = cal.monthdayscalendar(year, month)

    # Events by day
    events_by_day = {}
    for event in events:
        day = event.event_date.day
        events_by_day.setdefault(day, []).append(event)

    # Upcoming events (next 30 days)
    upcoming = CalendarEvent.query.filter(
        CalendarEvent.user_id == current_user.id,
        CalendarEvent.event_date >= datetime.now(),
        CalendarEvent.event_date <= datetime.now() + timedelta(days=30)
    ).order_by(CalendarEvent.event_date).limit(10).all()

    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1

    return render_template('calendar.html',
        events=events, weeks=weeks, events_by_day=events_by_day,
        upcoming=upcoming, year=year, month=month,
        month_name=cal_module.month_name[month],
        prev_month=prev_month, prev_year=prev_year,
        next_month=next_month, next_year=next_year)


@calendar_bp.route('/calendar/add', methods=['POST'])
@login_required
def add_event():
    event = CalendarEvent(
        user_id=current_user.id,
        title=request.form.get('title', '').strip(),
        description=request.form.get('description', '').strip() or None,
        event_type=request.form.get('event_type', 'Custom'),
        event_date=datetime.strptime(request.form['event_date'], '%Y-%m-%d'),
        amount=float(request.form.get('amount', 0)) or None,
        color=request.form.get('color', '#6366f1'),
        reminder_enabled=bool(request.form.get('reminder_enabled')),
    )
    reminder = request.form.get('reminder_date')
    if reminder:
        event.reminder_date = datetime.strptime(reminder, '%Y-%m-%d')
    db.session.add(event)
    db.session.commit()
    flash('Event added to calendar.', 'success')
    return redirect(url_for('calendar.calendar_view', year=event.event_date.year, month=event.event_date.month))


@calendar_bp.route('/calendar/edit/<int:id>', methods=['POST'])
@login_required
def edit_event(id):
    event = CalendarEvent.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    event.title = request.form.get('title', event.title).strip()
    event.description = request.form.get('description', '').strip() or None
    event.event_type = request.form.get('event_type', event.event_type)
    event.event_date = datetime.strptime(request.form['event_date'], '%Y-%m-%d')
    event.amount = float(request.form.get('amount', 0)) or None
    event.color = request.form.get('color', event.color)
    event.reminder_enabled = bool(request.form.get('reminder_enabled'))
    reminder = request.form.get('reminder_date')
    event.reminder_date = datetime.strptime(reminder, '%Y-%m-%d') if reminder else None
    db.session.commit()
    flash('Event updated.', 'success')
    return redirect(url_for('calendar.calendar_view', year=event.event_date.year, month=event.event_date.month))


@calendar_bp.route('/calendar/delete/<int:id>', methods=['POST'])
@login_required
def delete_event(id):
    event = CalendarEvent.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    db.session.delete(event)
    db.session.commit()
    flash('Event deleted.', 'success')
    return redirect(url_for('calendar.calendar_view'))
