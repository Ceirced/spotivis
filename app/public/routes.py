from flask import redirect, render_template, url_for
from flask_security import current_user

from app.public import bp


@bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    return render_template("public/index.html", title="Home")
