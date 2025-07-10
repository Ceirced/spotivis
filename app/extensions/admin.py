from flask import abort, redirect, request, url_for  # type: ignore
from flask_security import current_user  # type: ignore
from flask_admin import Admin, AdminIndexView  # type: ignore
from flask_admin.contrib.sqla import ModelView  # type: ignore
from flask_admin.theme import Bootstrap4Theme  # type: ignore

from app import db
from app.models import User, Role


class MyAdminIndexView(AdminIndexView):
    def is_accessible(self):
        return (
            current_user.is_active
            and current_user.is_authenticated
            and current_user.has_role("admin")
        )

    def _handle_view(self, name, **kwargs):
        """
        Override builtin _handle_view in order to redirect users when a view is not
        accessible.
        """
        if not self.is_accessible():
            if current_user.is_authenticated:
                # permission denied
                abort(403)
            else:
                # login
                return redirect(url_for("security.login", next=request.url))


class MyModelView(ModelView):
    def is_accessible(self):
        return (
            current_user.is_active
            and current_user.is_authenticated
            and current_user.has_role("admin")
        )

    def _handle_view(self, name, **kwargs):
        """
        Override builtin _handle_view in order to redirect users when a view is not
        accessible.
        """
        if not self.is_accessible():
            if current_user.is_authenticated:
                # permission denied
                abort(403)
            else:
                # login
                return redirect(url_for("security.login", next=request.url))


def init_admin(app):
    """
    Initialize Flask-Admin with the given Flask app.

    :param app: The Flask application instance.
    :return: An instance of Flask-Admin.
    """
    app.config["FLASK_ADMIN_SWATCH"] = "slate"

    admin = Admin(
        name=app.config["APP_NAME"],
        theme=Bootstrap4Theme(swatch="slate"),
        index_view=MyAdminIndexView(
            name="Dashboard",
            url="/admin",
        ),
    )
    admin.add_view(MyModelView(User, db.session))
    admin.add_view(MyModelView(Role, db.session))

    admin.init_app(app)
