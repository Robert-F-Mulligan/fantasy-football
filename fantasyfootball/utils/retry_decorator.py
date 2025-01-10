from functools import wraps
import time 
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def retry_decorator(retries: int = 3, delay: int = 1, backoff_factor: int = 2):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempts = 0
            while attempts <= retries:
                try: 
                    if attempts > 0:
                        logger.debug(f"Trying to execute {func.__name__} on attempt {attempts + 1}")
                    result =  func(*args, **kwargs)
                    if attempts == 0:
                        logger.debug(f"Successfully executed {func.__name__} on first attempt")
                    else:
                        logger.info(f"Successfully executed {func.__name__} on attempt {attempts + 1}")
                    return result
                except Exception as e:
                    attempts += 1
                    logger.exception(f"Failed to execute {func.__name__} on attempt {attempts} due to {e}")
                    time.sleep(delay * (backoff_factor ** attempts))
                
            logger.info(f"Retrying {func.__name__} after {delay * (backoff_factor ** attempts)} seconds") 
        return wrapper
    return decorator