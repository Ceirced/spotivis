from flask_admin import Admin  # type: ignore
from flask_admin.contrib.sqla import ModelView  # type: ignore

from app import db
from app.models import User, Payment


def init_admin(app):
    """
    Initialize Flask-Admin with the given Flask app.

    :param app: The Flask application instance.
    :return: An instance of Flask-Admin.
    """
    app.config["FLASK_ADMIN_SWATCH"] = "slate"

    admin = Admin(
        name=app.config["APP_NAME"],
    )
    admin.add_view(ModelView(User, db.session))
    admin.add_view(ModelView(Payment, db.session))

    admin.init_app(app)
