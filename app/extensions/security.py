from flask_security import (
    Security,
    SQLAlchemyUserDatastore,
)

from app.models import User, Role
from app.extensions import db

user_datastore = SQLAlchemyUserDatastore(db, User, Role)
security = Security()
