import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

import stripe
from flask import Flask, render_template, request
from flask_caching import Cache
from flask_htmx import HTMX
from flask_migrate import Migrate
from posthog import Posthog
from werkzeug.middleware.proxy_fix import ProxyFix

from app.extensions import db, mail
from app.extensions.admin import init_admin
from app.extensions.celery import init_celery
from app.extensions.security import init_app as init_security

# to set the app Settings in the docker compose
migrate = Migrate()
htmx = HTMX()
cache = Cache(config={"CACHE_TYPE": "SimpleCache"})

posthog = Posthog(os.getenv("POSTHOG_API_KEY", ""), host="https://eu.i.posthog.com")


def create_app():
    app = Flask(__name__)

    app.config["APP_NAME"] = os.getenv("APP_NAME")
    app_settings = os.getenv("APP_SETTINGS")
    app.config.from_object(app_settings)
    app.config["MAINTENANCE_MODE"] = os.getenv("MAINTENANCE_MODE", "False") == "True"
    stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

    app.config["MAIL_SERVER"] = os.getenv("MAIL_SERVER", "smtp.ionos.com")
    app.config["MAIL_PORT"] = os.getenv("MAIL_PORT", 587)
    app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME")
    app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD")
    app.config["MAIL_USE_TLS"] = True

    app.config.from_mapping(
        CELERY={
            "broker_url": app.config["REDIS_URL"],
            "result_backend": app.config["REDIS_URL"],
            "task_ignore_result": True,
        }
    )

    init_security(app)
    init_celery(app)
    init_admin(app)
    db.init_app(app)
    htmx.init_app(app)
    cache.init_app(app)
    mail.init_app(app)
    migrate.init_app(app, db)

    # Enable foreign key support for SQLite
    if "sqlite" in app.config.get("SQLALCHEMY_DATABASE_URI", ""):
        from sqlalchemy import event
        from sqlalchemy.engine import Engine

        @event.listens_for(Engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            # the sqlite3 driver will not set PRAGMA foreign_keys
            # if autocommit=False; set to True temporarily
            ac = dbapi_connection.autocommit
            dbapi_connection.autocommit = True

            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

            # restore previous autocommit setting
            dbapi_connection.autocommit = ac

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
        if app.config.get("LOG_TO_STDOUT", False):
            stream_handler = logging.StreamHandler()
            stream_handler.setLevel(logging.INFO)
            app.logger.addHandler(stream_handler)
        else:
            logs_path = Path("logs")
            if not logs_path.exists():
                logs_path.mkdir()
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
