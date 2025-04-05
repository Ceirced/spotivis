import os

import logging
from logging.handlers import RotatingFileHandler

from flask import Flask, render_template, request
from flask_migrate import Migrate  # type: ignore
from werkzeug.middleware.proxy_fix import ProxyFix
from posthog import Posthog
import stripe

from app.extensions import db
from app.extensions.security import init_app as init_security


# to set the app Settings in the docker compose
migrate = Migrate()

posthog = Posthog(os.getenv("POSTHOG_API_KEY"), host="https://eu.i.posthog.com")


def create_app():
    app = Flask(__name__)

    app_settings = os.getenv("APP_SETTINGS")
    app.config.from_object(app_settings)
    app.config["MAINTENANCE_MODE"] = os.getenv("MAINTENANCE_MODE", "False") == "True"
    stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

    init_security(app)
    db.init_app(app)
    migrate.init_app(app, db)

    from app.public import bp as public_bp

    app.register_blueprint(public_bp)

    from app.main import bp as main_bp

    app.register_blueprint(main_bp, url_prefix="/app")

    from app.api import bp as api_bp

    app.register_blueprint(api_bp, url_prefix="/api")

    from app.main.second_page import bp as second_page_bp

    app.register_blueprint(second_page_bp, url_prefix="/second_page")

    from app.main.first import bp as first_bp

    app.register_blueprint(first_bp, url_prefix="/first")

    from app.main.users import bp as users_bp

    app.register_blueprint(users_bp, url_prefix="/users")

    from app.auth import bp as auth_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")

    from app.errors import bp as errors_bp

    app.register_blueprint(errors_bp)

    @app.before_request
    def check_for_maintenance():
        if (
            app.config["MAINTENANCE_MODE"]
            and request.blueprint != "public_bp"
            and not request.path.startswith("/static/")
        ):
            return (
                render_template("errors/maintenance.html"),
                503,
            )  # HTTP 503 Service Unavailable

    if app.debug:
        posthog.disabled = True
        app.logger.setLevel(logging.DEBUG)

    if not app.debug and not app.testing:
        root = logging.getLogger()
        root.setLevel(logging.INFO)
        if app.config["LOG_TO_STDOUT"]:
            stream_handler = logging.StreamHandler()
            stream_handler.setLevel(logging.INFO)
            app.logger.addHandler(stream_handler)
        else:
            if not os.path.exists("logs"):
                os.mkdir("logs")
            file_handler = RotatingFileHandler(
                "logs/flask.log", maxBytes=10240, backupCount=10
            )
            file_handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s %(levelname)s: %(message)s "
                    "[in %(pathname)s:%(lineno)d]"
                )
            )
            file_handler.setLevel(logging.INFO)
            root.addHandler(file_handler)

        app.logger.setLevel(logging.INFO)

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=2, x_proto=1, x_host=1, x_prefix=1)
    return app


# from app import models
