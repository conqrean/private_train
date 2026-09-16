# -*- coding: utf-8 -*-
"""Session management utilities for multi-provider support."""
from flask import session
from typing import Optional, Dict, Any, List


def _init_session_structure() -> None:
    """Initialize session structure if not exists."""
    if 'auth' not in session:
        session['auth'] = {}
    if 'credentials' not in session:
        session['credentials'] = {}
    if 'search_state' not in session:
        session['search_state'] = {}
    if 'cards' not in session:
        session['cards'] = {}


def get_current_provider() -> str:
    """Get the currently active provider.

    SRT 가 코레일로 통합되면서 웹 UI 에서 SRT 화면을 내렸다. 기본값이 'srt' 로
    남아 있으면 새 세션이 노출되지 않는 화면으로 떨어지므로 'korail' 로 둔다.
    (provider 분기 자체는 되돌릴 수 있게 백엔드에 그대로 남겨둔 상태)
    """
    return session.get('current_provider', 'korail')


def set_current_provider(provider: str) -> None:
    """Set the currently active provider."""
    if provider not in ['srt', 'korail']:
        raise ValueError(f"Invalid provider: {provider}")
    session['current_provider'] = provider
    session.modified = True


def get_auth_state(provider: str) -> Dict[str, Any]:
    """Get authentication state for a provider."""
    _init_session_structure()
    return session['auth'].get(provider, {'logged_in': False})


def set_auth_state(provider: str, user_id: str) -> None:
    """Set authentication state for a provider."""
    _init_session_structure()
    session['auth'][provider] = {
        'logged_in': True,
        'user_id': user_id
    }
    session.modified = True


def clear_auth_state(provider: str, keep_card: bool = False) -> None:
    """Clear authentication state for a provider.

    Pass keep_card=True for the automatic re-login that runs on every request:
    a transient failure there (network down, provider hiccup) must not throw
    away the card the user registered. Only an explicit logout clears it.
    """
    _init_session_structure()
    if provider in session['auth']:
        session['auth'][provider] = {'logged_in': False}
    if provider in session['credentials']:
        del session['credentials'][provider]
    if provider in session['search_state']:
        del session['search_state'][provider]
    if not keep_card and provider in session['cards']:
        del session['cards'][provider]
    session.modified = True


def is_logged_in(provider: str = None) -> bool:
    """Check if logged in to a specific provider or current provider."""
    if provider is None:
        provider = get_current_provider()
    return get_auth_state(provider).get('logged_in', False)


def get_logged_in_providers() -> List[str]:
    """Get list of all logged-in providers."""
    return [p for p in ['korail', 'srt'] if is_logged_in(p)]


def get_any_logged_in_provider() -> Optional[str]:
    """Return any provider that is logged in, or None."""
    for p in ['korail', 'srt']:
        if is_logged_in(p):
            return p
    return None


def get_search_state(provider: str = None) -> Dict[str, Any]:
    """Get search state for a provider."""
    if provider is None:
        provider = get_current_provider()
    _init_session_structure()
    if provider not in session['search_state']:
        session['search_state'][provider] = {
            'trains': [],
            'selected_indices': [],
            'seat_option': 'GENERAL_FIRST',
            'form_data': {}
        }
        session.modified = True
    return session['search_state'][provider]


def set_search_trains(provider: str, trains: List[Dict]) -> None:
    """Store search results for a provider."""
    state = get_search_state(provider)
    state['trains'] = trains
    session.modified = True


def set_selected_indices(
    provider: str, indices: List[int], seat_option: str,
    passenger_count: int = 1, sequential: bool = False,
    pace_mode: str = 'safe'
) -> None:
    """Store selected train indices and reservation options for a provider."""
    state = get_search_state(provider)
    state['selected_indices'] = indices
    state['seat_option'] = seat_option
    state['passenger_count'] = passenger_count
    state['sequential'] = sequential
    state['pace_mode'] = pace_mode
    session.modified = True


def get_credentials(provider: str) -> Optional[Dict[str, str]]:
    """Get stored credentials for a provider (for session restoration)."""
    _init_session_structure()
    return session['credentials'].get(provider)


def set_credentials(provider: str, user_id: str, password: str) -> None:
    """Store credentials for a provider (for session restoration)."""
    _init_session_structure()
    session['credentials'][provider] = {
        'user_id': user_id,
        'password': password
    }
    session.modified = True


def get_card_settings(provider: str) -> Optional[Dict[str, Any]]:
    """Get stored card auto-payment settings for a provider."""
    _init_session_structure()
    return session['cards'].get(provider)


def set_card_settings(
    provider: str,
    card_number: str,
    card_password: str,
    validation_number: str,
    card_expire: str,
    installment: int = 0,
    card_type: str = 'J',
    auto_pay: bool = True,
) -> None:
    """Store card auto-payment settings for a provider."""
    _init_session_structure()
    session['cards'][provider] = {
        'card_number': card_number,
        'card_password': card_password,
        'validation_number': validation_number,
        'card_expire': card_expire,
        'installment': installment,
        'card_type': card_type,
        'auto_pay': auto_pay,
    }
    session.modified = True


def clear_card_settings(provider: str) -> None:
    """Remove stored card settings for a provider."""
    _init_session_structure()
    if provider in session['cards']:
        del session['cards'][provider]
        session.modified = True


def clear_all_session() -> None:
    """Clear all session data."""
    session.clear()
