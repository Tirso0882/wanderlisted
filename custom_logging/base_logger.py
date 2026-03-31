"""
Base logger configuration.

This file defines a `default_logger` to avoid circular dependencies within the logging module.
"""

from .app_logger import AppLogger

default_logger = AppLogger(logger_name="custom_logging", use_colors=True, level="DEBUG")
