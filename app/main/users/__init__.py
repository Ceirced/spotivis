from flask import Blueprint
from flask_login import login_required

bp = Blueprint('users', __name__)

from app.main.users import routes

@bp.before_request
@login_required
def before_request():
    pass