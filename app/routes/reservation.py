# -*- coding: utf-8 -*-
"""Reservation routes with SSE support and multi-provider session."""
import json
import time
from datetime import datetime
from functools import wraps
from flask import Blueprint, request, session, redirect, url_for, Response, jsonify

from app.services import ServiceManager, SeatOption
from app.utils.session_helper import (
    get_current_provider, is_logged_in,
    get_search_state, set_selected_indices
)

bp = Blueprint('reservation', __name__)

# Global stop flag for macro
STOP_MACRO = False


def login_required(f):
    """Decorator to require login."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_logged_in():
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


@bp.route('/reserve_select', methods=['POST'])
@login_required
def reserve_select():
    """Store selected trains for reservation."""
    provider = get_current_provider()
    selected_indices = request.form.getlist('train_indices[]')
    seat_option = request.form.get('seat_option', 'GENERAL_FIRST')

    # Store for this provider
    set_selected_indices(
        provider,
        [int(i) for i in selected_indices],
        seat_option
    )

    return jsonify({'success': True, 'count': len(selected_indices)})


@bp.route('/start_reservation')
@login_required
def start_reservation():
    """SSE endpoint for reservation attempts."""
    global STOP_MACRO
    STOP_MACRO = False

    provider = get_current_provider()
    service = ServiceManager.get_service(provider)

    # Get provider-specific search state
    search_state = get_search_state(provider)
    selected_indices = search_state.get('selected_indices', [])
    seat_option_str = search_state.get('seat_option', 'GENERAL_FIRST')
    trains_data = search_state.get('trains', [])

    # Convert seat option
    seat_option_map = {
        'GENERAL_FIRST': SeatOption.GENERAL_FIRST,
        'GENERAL_ONLY': SeatOption.GENERAL_ONLY,
        'SPECIAL_FIRST': SeatOption.SPECIAL_FIRST,
        'SPECIAL_ONLY': SeatOption.SPECIAL_ONLY,
    }
    seat_option = seat_option_map.get(seat_option_str, SeatOption.GENERAL_FIRST)

    def generate():
        global STOP_MACRO
        attempt = 0

        while not STOP_MACRO:
            attempt += 1
            timestamp = datetime.now().strftime('%H:%M:%S')

            for idx in selected_indices:
                if STOP_MACRO:
                    yield f"data: {json.dumps({'type': 'stopped', 'message': '예약이 중단되었습니다.'})}\n\n"
                    return

                if idx >= len(trains_data):
                    continue

                train_info = trains_data[idx]
                train_name = train_info['train_name']
                dep_time = f"{train_info['dep_time'][:2]}:{train_info['dep_time'][2:4]}"

                yield f"data: {json.dumps({'type': 'log', 'message': f'[{timestamp}] 시도 #{attempt}: {train_name} ({dep_time}) 예약 시도 중...'})}\n\n"

                try:
                    # Re-search to get fresh train data
                    fresh_trains = service.search(
                        dep=train_info['dep_station'],
                        arr=train_info['arr_station'],
                        date=train_info['dep_date'],
                        time=train_info['dep_time'],
                        include_no_seats=True
                    )

                    # Find matching train
                    matching_train = None
                    for t in fresh_trains:
                        if (t.train_number == train_info['train_number'] and
                            t.dep_time == train_info['dep_time']):
                            matching_train = t
                            break

                    if not matching_train:
                        yield f"data: {json.dumps({'type': 'log', 'message': f'[{timestamp}] {train_name}: 열차를 찾을 수 없습니다.'})}\n\n"
                        continue

                    if not matching_train.has_seat():
                        yield f"data: {json.dumps({'type': 'log', 'message': f'[{timestamp}] {train_name}: 좌석 없음'})}\n\n"
                        continue

                    # Attempt reservation
                    result = service.reserve(matching_train, seat_option)

                    if result.success:
                        yield f"data: {json.dumps({'type': 'success', 'message': f'예약 성공! {train_name} ({dep_time})', 'reservation_id': result.reservation_id})}\n\n"
                        STOP_MACRO = True
                        return
                    else:
                        yield f"data: {json.dumps({'type': 'log', 'message': f'[{timestamp}] {train_name}: {result.message}'})}\n\n"

                except Exception as e:
                    yield f"data: {json.dumps({'type': 'error', 'message': f'[{timestamp}] 오류: {str(e)}'})}\n\n"

            # Wait before next attempt
            time.sleep(0.5)

        yield f"data: {json.dumps({'type': 'stopped', 'message': '예약이 중단되었습니다.'})}\n\n"

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        }
    )


@bp.route('/stop_macro', methods=['POST'])
@login_required
def stop_macro():
    """Stop the reservation macro."""
    global STOP_MACRO
    STOP_MACRO = True
    return jsonify({'success': True})
