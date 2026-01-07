# -*- coding: utf-8 -*-
"""Search routes with multi-provider session support."""
from datetime import datetime, timedelta
from functools import wraps
from flask import Blueprint, request, session, redirect, url_for, render_template, jsonify

from app.services import ServiceManager
from app.utils.session_helper import (
    get_current_provider, is_logged_in, get_logged_in_providers,
    get_search_state, set_search_trains
)

bp = Blueprint('search', __name__)


def get_service(provider: str):
    """Get service instance - wrapper for backward compatibility."""
    return ServiceManager.get_service(provider)


def login_required(f):
    """Decorator to require login for current provider."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        provider = get_current_provider()
        if not is_logged_in(provider):
            # Check if logged in to any other provider
            logged_in = get_logged_in_providers()
            if logged_in:
                return redirect(url_for('auth.switch_provider', provider=logged_in[0]))
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


@bp.route('/api/search_more', methods=['POST'])
@login_required
def search_more():
    """Fetch more trains starting from the last train's time."""
    provider = get_current_provider()
    service = ServiceManager.get_service(provider)
    
    # Get form data from request (or session)
    dep = request.form.get('dep')
    arr = request.form.get('arr')
    date = request.form.get('date', '').replace('-', '')
    last_time = request.form.get('last_time', '').replace(':', '')
    
    if not all([dep, arr, date, last_time]):
        return jsonify({'error': 'Missing parameters'}), 400

    try:
        # Increment time by 1 minute to avoid getting the same last train
        last_dt = datetime.strptime(f"{date}{last_time}", "%Y%m%d%H%M%S")
        next_dt = last_dt + timedelta(minutes=1)
        next_time = next_dt.strftime("%H%M%S")
        
        # Check if next_time crossed to next day
        if next_dt.strftime("%Y%m%d") != date:
            return jsonify({'trains': [], 'has_more': False})

        train_results = service.search(
            dep=dep,
            arr=arr,
            date=date,
            time=next_time,
            include_no_seats=True
        )

        # Format for JSON
        trains_data = [
            {
                'index': 0, # Will be set on client-side
                'train_name': t.train_name,
                'train_number': t.train_number,
                'dep_date': t.dep_date,
                'dep_time': t.dep_time,
                'dep_time_formatted': t.dep_time_formatted,
                'arr_date': t.arr_date,
                'arr_time': t.arr_time,
                'arr_time_formatted': t.arr_time_formatted,
                'duration_formatted': t.duration_formatted,
                'dep_station': t.dep_station,
                'arr_station': t.arr_station,
                'general_seat_available': t.general_seat_available,
                'special_seat_available': t.special_seat_available,
            }
            for t in train_results
        ]

        # Update session with new trains (optional, but good for macro)
        search_state = get_search_state(provider)
        existing_trains = search_state.get('trains', [])
        
        # Assign correct indices
        start_idx = len(existing_trains)
        for i, t in enumerate(trains_data):
            t['index'] = start_idx + i
            
        search_state['trains'] = existing_trains + trains_data
        session.modified = True

        return jsonify({
            'trains': trains_data,
            'has_more': len(trains_data) > 0
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    """Main search page."""
    provider = get_current_provider()
    service = ServiceManager.get_service(provider)
    stations = service.get_stations()

    # Get provider-specific search state
    search_state = get_search_state(provider)

    # Default values
    default_date = datetime.now().strftime('%Y-%m-%d')
    default_time = '00:00'

    # Use saved form_data if available, otherwise defaults
    saved_form = search_state.get('form_data', {})

    # Form data - POST data takes priority, then saved data, then defaults
    if request.method == 'POST':
        form_data = {
            'dep': request.form.get('dep', '수서' if provider == 'srt' else '용산'),
            'arr': request.form.get('arr', '순천'),
            'date': request.form.get('date', default_date),
            'time': request.form.get('time', default_time)
        }
    else:
        form_data = {
            'dep': saved_form.get('dep', '수서' if provider == 'srt' else '용산'),
            'arr': saved_form.get('arr', '순천'),
            'date': saved_form.get('date', default_date),
            'time': saved_form.get('time', default_time)
        }

    trains = []
    error_message = None

    # On GET, restore saved trains if available
    if request.method == 'GET' and search_state.get('trains'):
        trains = search_state['trains']

    if request.method == 'POST' and 'search' in request.form:
        try:
            # Convert date and time format
            date_str = form_data['date'].replace('-', '')
            time_str = form_data['time'].replace(':', '') + '00'

            train_results = service.search(
                dep=form_data['dep'],
                arr=form_data['arr'],
                date=date_str,
                time=time_str,
                include_no_seats=True
            )

            # Store trains in session for this provider
            trains_data = [
                {
                    'index': i,
                    'train_name': t.train_name,
                    'train_number': t.train_number,
                    'dep_date': t.dep_date,
                    'dep_time': t.dep_time,
                    'dep_time_formatted': t.dep_time_formatted,
                    'arr_date': t.arr_date,
                    'arr_time': t.arr_time,
                    'arr_time_formatted': t.arr_time_formatted,
                    'duration_formatted': t.duration_formatted,
                    'dep_station': t.dep_station,
                    'arr_station': t.arr_station,
                    'general_seat_available': t.general_seat_available,
                    'special_seat_available': t.special_seat_available,
                }
                for i, t in enumerate(train_results)
            ]

            set_search_trains(provider, trains_data)

            # Save form_data for this provider (restore on switch back)
            search_state['form_data'] = form_data
            session.modified = True

            trains = trains_data

        except Exception as e:
            error_message = str(e)

    return render_template('search.html',
                           provider=provider,
                           stations=stations,
                           form_data=form_data,
                           default_date=default_date,
                           trains=trains,
                           error_message=error_message,
                           logged_in_providers=get_logged_in_providers())
