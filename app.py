import logging

import sqlalchemy as sa
import sqlalchemy.orm as so

from app import create_app, db
from app.models import User

app = create_app()


@app.shell_context_processor
def make_shell_context():
    return {"sa": sa, "so": so, "db": db, "User": User}


# We check if we are running directly or not
if __name__ != "__main__":
    # if we are not running directly, we set the loggers
    gunicorn_logger = logging.getLogger("gunicorn.error")
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(gunicorn_logger.level)

if __name__ == "__main__":
    with app.app_context():
        if not User.get_user_by_name("dev"):
            User.new_user("dev", "dev@dev.at", "password")
    app.run(host="0.0.0.0", port=5000)
