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
    )

    security.init_app(app, user_datastore)
