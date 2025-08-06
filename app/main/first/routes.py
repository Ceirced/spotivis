from flask import current_app, render_template

from app import cache, htmx
from app.helpers.app_helpers import make_cache_key_with_htmx
from app.main.first import bp


def add_cache_headers(response, max_age=300, private=True):
    """Add client-side cache headers to response."""
    if private:
        response.headers["Cache-Control"] = f"private, max-age={max_age}"
    else:
        response.headers["Cache-Control"] = f"public, max-age={max_age}"
    return response


@bp.route("/", methods=["GET"])
@cache.cached(
    timeout=60,
    make_cache_key=make_cache_key_with_htmx,
    unless=lambda: current_app.config.get("DEBUG", False),
)
def index():
    title = "First"
    return render_template("./first/index.html", title=title)
