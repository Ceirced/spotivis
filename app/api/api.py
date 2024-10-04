from flask import jsonify

from app.api import bp


@bp.route("/", methods=["GET"])
def index():
    return jsonify({"message": "success"})
