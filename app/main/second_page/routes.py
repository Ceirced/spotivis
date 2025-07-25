from flask import render_template

from app import htmx
from app.main.second_page import bp


@bp.route("/")
def index():
    title = "Second"
    if htmx.boosted:
        return render_template("./second_page/partials/_content.html", title=title)
    return render_template("./second_page/index.html", title=title)
