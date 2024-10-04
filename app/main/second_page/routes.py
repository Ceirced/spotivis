from flask import render_template

from app.main.second_page import bp


@bp.route("/")
def index():
    return render_template("./second_page/index.html")
