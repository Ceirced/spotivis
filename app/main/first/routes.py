from flask import render_template
from app.main.first import bp


@bp.route("/", methods=["GET"])
def index():
    return render_template("./first/index.html")
