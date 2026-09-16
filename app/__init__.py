# -*- coding: utf-8 -*-
"""Flask Application Factory"""
import os
from datetime import timedelta

from flask import Flask, session

from app.utils.server_session import (
    EncryptedFileSessionInterface,
    get_state_dir,
    load_or_create_secret_key,
)

# How long a login (and the registered card) survives without use.
SESSION_LIFETIME = timedelta(days=30)


def create_app(config_name: str = 'default') -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__,
                template_folder='templates',
                static_folder='static')

    state_dir = get_state_dir()
    app.secret_key = (
        os.environ.get("FLASK_SECRET_KEY") or load_or_create_secret_key(state_dir)
    )

    # Sessions are stored server-side and encrypted; the cookie carries only a
    # signed id. Without this the cookie expired the moment the browser closed,
    # taking the login and the card settings with it.
    app.permanent_session_lifetime = SESSION_LIFETIME
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    app.session_interface = EncryptedFileSessionInterface(state_dir, SESSION_LIFETIME)

    @app.before_request
    def _make_session_persistent():
        session.permanent = True

    # Register blueprints
    from app.routes import auth, search, reservation, telegram
    app.register_blueprint(auth.bp)
    app.register_blueprint(search.bp)
    app.register_blueprint(reservation.bp)
    app.register_blueprint(telegram.bp)

    return app
