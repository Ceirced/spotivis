from flask_security import (
    Security,
    SQLAlchemyUserDatastore,
)

from app.models import User, Role
from app.extensions import db

user_datastore = SQLAlchemyUserDatastore(db, User, Role)
security = Security()


def init_app(app):

    app.config.update(
        SECURITY_TRACKABLE=True,
        SECURITY_PASSWORD_SALT="IschlerSalz",
        SECURITY_REGISTERABLE=True,
        SECURITY_PASSWORD_CONFIRM_REQUIRED=False,
        SECURITY_USE_REGISTER_V2=True,
        SECURITY_SEND_REGISTER_EMAIL=False,
    )

    security.init_app(app, user_datastore)
