from functools import wraps

from .base_logger import default_logger


def log_function_call(func):
    """Decorator to log synchronous function calls with entry/exit/error."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        default_logger.debug(f"Calling function: {func.__name__}")
        try:
            result = func(*args, **kwargs)
            default_logger.debug(f"Function {func.__name__} completed successfully")
            return result
        except Exception as e:
            default_logger.error(
                f"Error in function {func.__name__}: {str(e)}", exc_info=True
            )
            raise

    return wrapper


def log_async_function_call(func):
    """Decorator to log async function calls with entry/exit/error."""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        default_logger.debug(f"Calling async function: {func.__name__}")
        try:
            result = await func(*args, **kwargs)
            default_logger.debug(f"Async function {func.__name__} completed successfully")
            return result
        except Exception as e:
            default_logger.error(
                f"Error in async function {func.__name__}: {str(e)}", exc_info=True
            )
            raise

    return wrapper
