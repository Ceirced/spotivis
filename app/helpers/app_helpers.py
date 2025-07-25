from flask import abort
from functools import wraps


def disable_route():
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            abort(404)

        return decorated_function

    return decorator


if __name__ == "__main__":
    pass
