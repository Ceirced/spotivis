from flask import Blueprint
from flask_login import login_required

bp = Blueprint("second_page", __name__)

from app.main.second_page import routes


@bp.before_request
@login_required
def before_request():
    pass
