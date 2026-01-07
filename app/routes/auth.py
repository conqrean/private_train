# -*- coding: utf-8 -*-
"""Authentication routes."""
from flask import Blueprint, request, session, redirect, url_for, render_template, flash

from app.services import SRTService, KorailService, TrainProvider

bp = Blueprint('auth', __name__)

# Service instances (per-session in production, use proper session management)
_services = {}


def get_service(provider: str):
    """Get or create service instance for provider."""
    if provider not in _services:
        if provider == TrainProvider.SRT.value:
            _services[provider] = SRTService()
        else:
            _services[provider] = KorailService()
    return _services[provider]


@bp.route('/login', methods=['GET', 'POST'])
def login():
    """Handle login."""
    if request.method == 'POST':
        provider = request.form.get('provider', 'srt')
        user_id = request.form.get('user_id', '').strip()
        password = request.form.get('password', '').strip()

        if not user_id or not password:
            return render_template('login.html',
                                   error="아이디와 비밀번호를 입력해주세요.",
                                   provider=provider)

        service = get_service(provider)
        if service.login(user_id, password):
            session['logged_in'] = True
            session['provider'] = provider
            session['user_id'] = user_id
            return redirect(url_for('search.index'))
        else:
            return render_template('login.html',
                                   error="로그인에 실패했습니다. 아이디와 비밀번호를 확인해주세요.",
                                   provider=provider)

    return render_template('login.html', provider=request.args.get('provider', 'srt'))


@bp.route('/logout', methods=['POST'])
def logout():
    """Handle logout."""
    provider = session.get('provider')
    if provider and provider in _services:
        _services[provider].logout()
        del _services[provider]

    session.clear()
    return redirect(url_for('auth.login'))


@bp.route('/switch/<provider>')
def switch_provider(provider: str):
    """Switch between SRT and Korail."""
    if provider not in ['srt', 'korail']:
        return redirect(url_for('auth.login'))

    # Logout from current provider if logged in
    current_provider = session.get('provider')
    if current_provider and current_provider in _services:
        _services[current_provider].logout()
        del _services[current_provider]

    session.clear()
    return redirect(url_for('auth.login', provider=provider))
