from functools import wraps

from flask import abort, request
from loguru import logger

from app import cache, htmx


def disable_route():
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            abort(404)

        return decorated_function

    return decorator


def make_cache_key_with_htmx(*args, **kwargs):
    """Create cache key that includes HTMX boosted state and request path."""
    cache_key = request.path + ("_htmx" if htmx.boosted else "")
    logger.debug(f"Cache key: {cache_key}")

    return cache_key


def delete_htmx_cache(path: str):
    """Delete the cache for the key `path` and `path_htmx`.

    Args:
        path (str): The part before the _htmx in the cache key, should be `request.path`
    """
    cache.delete(path)
    cache.delete(path + "_htmx")


if __name__ == "__main__":
    pass
