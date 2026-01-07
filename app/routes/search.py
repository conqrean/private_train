# -*- coding: utf-8 -*-
"""Search routes."""
from datetime import datetime
from flask import Blueprint, request, session, redirect, url_for, render_template

from app.routes.auth import get_service

bp = Blueprint('search', __name__)


def login_required(f):
    """Decorator to require login."""
    from functools import wraps

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


@bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    """Main search page."""
    provider = session.get('provider', 'srt')
    service = get_service(provider)
    stations = service.get_stations()

    # Default values
    default_date = datetime.now().strftime('%Y-%m-%d')
    default_time = '00:00'

    # Form data
    form_data = {
        'dep': request.form.get('dep', '수서' if provider == 'srt' else '용산'),
        'arr': request.form.get('arr', '순천'),
        'date': request.form.get('date', default_date),
        'time': request.form.get('time', default_time)
    }

    trains = []
    error_message = None

    if request.method == 'POST' and 'search' in request.form:
        try:
            # Convert date and time format
            date_str = form_data['date'].replace('-', '')
            time_str = form_data['time'].replace(':', '') + '00'

            trains = service.search(
                dep=form_data['dep'],
                arr=form_data['arr'],
                date=date_str,
                time=time_str,
                include_no_seats=True
            )

            # Store trains in session for reservation
            session['trains'] = [
                {
                    'index': i,
                    'train_name': t.train_name,
                    'train_number': t.train_number,
                    'dep_date': t.dep_date,
                    'dep_time': t.dep_time,
                    'arr_date': t.arr_date,
                    'arr_time': t.arr_time,
                    'dep_station': t.dep_station,
                    'arr_station': t.arr_station,
                    'general_seat_available': t.general_seat_available,
                    'special_seat_available': t.special_seat_available,
                }
                for i, t in enumerate(trains)
            ]

        except Exception as e:
            error_message = str(e)

    return render_template('search.html',
                           provider=provider,
                           stations=stations,
                           form_data=form_data,
                           default_date=default_date,
                           trains=trains,
                           error_message=error_message)
