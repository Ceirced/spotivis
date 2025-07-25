from flask import Blueprint
from flask_login import login_required

bp = Blueprint("api", __name__)

from app.api import api


@bp.before_request
@login_required
def before_request():
    pass
