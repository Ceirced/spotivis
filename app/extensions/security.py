import os

from flask_security import Security, SQLAlchemyUserDatastore

from app.models import Role, User

from . import db
from .celery import CeleryMailUtil

user_datastore = SQLAlchemyUserDatastore(db, User, Role)
security = Security(mail_util_cls=CeleryMailUtil)


def init_app(app):
    app.config.update(
        SECURITY_TRACKABLE=True,
        SECURITY_PASSWORD_SALT=os.environ["SECURITY_PASSWORD_SALT"],
        SECURITY_REGISTERABLE=True,
        SECURITY_PASSWORD_CONFIRM_REQUIRED=False,
        SECURITY_USE_REGISTER_V2=True,
        SECURITY_USERNAME_ENABLE=True,
        SECURITY_SEND_REGISTER_EMAIL=True,
        SECURITY_POST_REGISTER_VIEW="security.login",
        SECURITY_CONFIRMABLE=True,
        SECURITY_USERNAME_REQUIRED=True,
        SECURITY_EMAIL_SENDER=f'"{app.config["APP_NAME"]}" <hi@aufsichtsr.at>',
        SECURITY_RECOVERABLE=True,
        SECURITY_DEFAULT_REMEMBER_ME=True,
        SECURITY_CHANGEABLE=True,
        # Set to True when the app has enough users for security
        SECURITY_RETURN_GENERIC_RESPONSES=False,
        SECURITY_CHANGE_EMAIL=True,
        SECURITY_REQUIRES_CONFIRMATION_ERROR_VIEW="confirm",
    )

    security.init_app(app, user_datastore)
