"""Bounded retry policy which preserves the final exception."""
from functools import wraps
import time


def retry_decorator(retries=3, delay=1, backoff_factor=2, exceptions=(Exception,)):
    if not isinstance(retries, int) or retries < 0 or delay < 0 or backoff_factor < 1:
        raise ValueError('Invalid retry policy')
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions:
                    if attempt == retries:
                        raise
                    time.sleep(delay * backoff_factor ** attempt)
        return wrapper
    return decorator
