from flask import Blueprint
from flask_login import login_required

bp = Blueprint("first", __name__)

from app.main.first import routes


@bp.before_request
@login_required
def before_request():
    pass
