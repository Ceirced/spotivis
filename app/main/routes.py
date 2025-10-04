from flask import redirect, render_template, url_for
from flask_security import login_required

from app.main import bp


@bp.before_request
@login_required
def before_request():
    pass


@bp.route("/flash-message", methods=["GET"])
def flash_messages():
    return render_template("partials/_flash-messages.html")


@bp.route("/")
def index():
    # redirect to first index
    return redirect(url_for("first.index"))
