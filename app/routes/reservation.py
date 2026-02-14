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
    get_search_state, set_selected_indices,
    get_credentials, set_auth_state
)

bp = Blueprint('reservation', __name__)

# Global stop flag for macro
STOP_MACRO = False

# Maximum recovery attempts
MAX_RECOVERY_ATTEMPTS = 3


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


def attempt_recovery(provider: str, service) -> tuple[bool, str]:
    """Attempt to recover from connection/login errors.
    
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        # Get stored credentials
        credentials = get_credentials(provider)
        if not credentials:
            return False, "저장된 로그인 정보가 없습니다."
        
        # Logout first to clear any stale state
        try:
            service.logout()
        except:
            pass
        
        # Attempt re-login
        success = service.login(credentials['user_id'], credentials['password'])
        if success:
            set_auth_state(provider, credentials['user_id'])
            return True, "재로그인 성공"
        else:
            return False, "재로그인 실패"
            
    except Exception as e:
        return False, f"리커버리 중 오류: {str(e)}"


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
        consecutive_errors = 0
        recovery_attempts = 0

        # Collect selected trains info
        selected_trains = []
        for idx in selected_indices:
            if idx < len(trains_data):
                selected_trains.append(trains_data[idx])
        
        if not selected_trains:
            yield f"data: {json.dumps({'type': 'error', 'message': '선택된 열차가 없습니다.'})}\n\n"
            return

        # Get earliest train for search
        earliest_train = min(selected_trains, key=lambda t: t['dep_time'])

        while not STOP_MACRO:
            attempt += 1
            timestamp = datetime.now().strftime('%H:%M:%S')

            try:
                # Single search to get all fresh train data
                yield f"data: {json.dumps({'type': 'log', 'message': f'[{timestamp}] 시도 #{attempt}: 열차 정보 조회 중...'})}\n\n"
                
                fresh_trains = service.search(
                    dep=earliest_train['dep_station'],
                    arr=earliest_train['arr_station'],
                    date=earliest_train['dep_date'],
                    time=earliest_train['dep_time'],
                    include_no_seats=True
                )

                # Reset error counter on successful query
                consecutive_errors = 0

                # Match selected trains with fresh data
                for train_info in selected_trains:
                    if STOP_MACRO:
                        yield f"data: {json.dumps({'type': 'stopped', 'message': '예약이 중단되었습니다.'})}\n\n"
                        return

                    train_name = train_info['train_name']
                    dep_time = f"{train_info['dep_time'][:2]}:{train_info['dep_time'][2:4]}"

                    # Find matching train in fresh data
                    matching_train = None
                    for t in fresh_trains:
                        if (t.train_number == train_info['train_number'] and
                            t.dep_time == train_info['dep_time']):
                            matching_train = t
                            break

                    if not matching_train:
                        yield f"data: {json.dumps({'type': 'log', 'message': f'[{timestamp}] {train_name} ({dep_time}): 열차를 찾을 수 없음'})}\n\n"
                        continue

                    if not matching_train.has_seat():
                        yield f"data: {json.dumps({'type': 'log', 'message': f'[{timestamp}] {train_name} ({dep_time}): 좌석 없음'})}\n\n"
                        continue

                    # Found a train with available seats - attempt reservation
                    yield f"data: {json.dumps({'type': 'log', 'message': f'[{timestamp}] {train_name} ({dep_time}): 좌석 있음! 예약 시도 중...'})}\n\n"
                    
                    try:
                        result = service.reserve(matching_train, seat_option)

                        if result.success:
                            yield f"data: {json.dumps({'type': 'success', 'message': f'예약 성공! {train_name} ({dep_time})', 'reservation_id': result.reservation_id})}\n\n"
                            STOP_MACRO = True
                            return
                        else:
                            yield f"data: {json.dumps({'type': 'log', 'message': f'[{timestamp}] {train_name} ({dep_time}): {result.message}'})}\n\n"
                    
                    except Exception as reserve_error:
                        error_msg = str(reserve_error)
                        yield f"data: {json.dumps({'type': 'log', 'message': f'[{timestamp}] {train_name} ({dep_time}): 예약 오류 - {error_msg}'})}\n\n"
                        
                        # Check if it's a login-related error
                        if 'login' in error_msg.lower() or 'auth' in error_msg.lower():
                            consecutive_errors += 1

            except Exception as e:
                consecutive_errors += 1
                error_msg = str(e)
                error_type = type(e).__name__
                
                yield f"data: {json.dumps({'type': 'error', 'message': f'[{timestamp}] 오류 ({error_type}): {error_msg}'})}\n\n"
                
                # Attempt auto-recovery if we have consecutive errors
                if consecutive_errors >= 2 and recovery_attempts < MAX_RECOVERY_ATTEMPTS:
                    recovery_attempts += 1
                    yield f"data: {json.dumps({'type': 'warning', 'message': f'[{timestamp}] 자동 복구 시도 중... ({recovery_attempts}/{MAX_RECOVERY_ATTEMPTS})'})}\n\n"
                    
                    success, recovery_msg = attempt_recovery(provider, service)
                    
                    if success:
                        yield f"data: {json.dumps({'type': 'success', 'message': f'[{timestamp}] {recovery_msg} - 예약 재시작'})}\n\n"
                        consecutive_errors = 0
                        time.sleep(1)  # Brief pause before resuming
                        continue
                    else:
                        yield f"data: {json.dumps({'type': 'error', 'message': f'[{timestamp}] {recovery_msg}'})}\n\n"
                        
                        # If max recovery attempts reached, stop
                        if recovery_attempts >= MAX_RECOVERY_ATTEMPTS:
                            yield f"data: {json.dumps({'type': 'error', 'message': f'[{timestamp}] 최대 복구 시도 횟수 초과. 예약을 중단합니다.'})}\n\n"
                            STOP_MACRO = True
                            return

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
