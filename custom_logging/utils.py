"""Utilities — temporarily disable or suppress console logging."""

import logging
from contextlib import contextmanager
from typing import Generator, Optional


class DisableLogger:
    """
    Context manager to temporarily disable logging.

    This class provides a way to temporarily disable all logging messages.
    It can be useful in scenarios where it is needed to suppress log output
    for a specific block of code.

    Attributes:
    -----------
    level : int, optional
        The logging level to set for disabling logs. Defaults to a level higher than CRITICAL.

    Methods:
    --------
    __enter__():
        Disables logging by setting the logging level to the specified level.
    __exit__(exc_type, exc_val, exc_tb):
        Restores the original logging level.
    """

    def __init__(self, level: Optional[int] = None):
        self.level = level or logging.CRITICAL + 1
        self._old_level = None

    def __enter__(self):
        self._old_level = logging.root.manager.disable
        logging.disable(self.level)

    def __exit__(self, exc_type, exc_val, exc_tb):
        logging.disable(self._old_level)


@contextmanager
def suppress_console_logging() -> Generator[None, None, None]:
    """
    Context manager to temporarily suppress console logging while keeping file logging active.

    Example:
        with suppress_console_logging():
            logger.info("This won't appear in console")
    """
    # Get all loggers
    loggers = [logging.getLogger(name) for name in logging.root.manager.loggerDict]
    loggers.append(logging.getLogger())  # Add root logger

    # Store original handlers and remove console handlers
    original_handlers = {}
    for logger in loggers:
        if not hasattr(logger, "handlers"):
            continue
        original_handlers[logger] = []
        for handler in logger.handlers[:]:
            if isinstance(handler, logging.StreamHandler) and not isinstance(
                handler, logging.FileHandler
            ):
                original_handlers[logger].append(handler)
                logger.removeHandler(handler)

    try:
        yield
    finally:
        # Restore original handlers
        for logger, handlers in original_handlers.items():
            for handler in handlers:
                logger.addHandler(handler)
