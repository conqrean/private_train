# -*- coding: utf-8 -*-
"""Flask Application Factory"""
import os
from flask import Flask


def create_app(config_name: str = 'default') -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__,
                template_folder='templates',
                static_folder='static')

    app.secret_key = os.environ.get("FLASK_SECRET_KEY", "train_reservation_secret_key_2024")

    # Register blueprints
    from app.routes import auth, search, reservation
    app.register_blueprint(auth.bp)
    app.register_blueprint(search.bp)
    app.register_blueprint(reservation.bp)

    return app
