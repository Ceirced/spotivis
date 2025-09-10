from flask import render_template

from app import cache, htmx
from app.helpers.app_helpers import make_cache_key_with_htmx
from app.main.second_page import bp


@bp.route("/")
@cache.cached(timeout=600, make_cache_key=make_cache_key_with_htmx)
def index():
    title = "Second"
    if htmx.boosted:
        return render_template("./second_page/partials/_content.html", title=title)
    return render_template("./second_page/index.html", title=title)
