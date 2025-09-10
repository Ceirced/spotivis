from functools import wraps

from flask import abort, request

from app import htmx


def disable_route():
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            abort(404)

        return decorated_function

    return decorator


def make_cache_key_with_htmx(*args, **kwargs):
    """Create cache key that includes HTMX boosted state and request path."""
    return f"{request.endpoint}_{htmx.boosted}_{request.view_args}"


if __name__ == "__main__":
    pass
