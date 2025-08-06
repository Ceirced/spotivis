from flask import render_template

from app import htmx, cache
from app.main.first import bp


@bp.route("/", methods=["GET"])
def index():
    title = "First"
    if htmx.boosted:
        return render_template("./first/partials/_content.html", title=title)
    return render_template("./first/index.html", title=title)
