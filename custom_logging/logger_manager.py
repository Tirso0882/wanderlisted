import logging
from pathlib import Path
from typing import Any, Dict, Optional

from .formatters import ColoredFormatter
from .handlers import ConditionalStreamHandler


class LoggerManager:
    """
    LoggerManager class to manage and configure logger instances.

    This class provides methods to set up and manage loggers with specified configurations,
    including console and file handlers with optional colored output.

    Attributes:
    -----------
    DEFAULT_FORMAT : str
        Default log message format.
    loggers : dict
        Dictionary to store logger instances.

    Notes:
    ------
    - Ensure the logger name is unique to avoid conflicts.
    - The log file path is generated based on the current timestamp if not provided.
    """

    DEFAULT_FORMAT = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"

    def __init__(self):
        """Initialize logger manager."""
        self.loggers = {}

    def setup_logger(
        self, name: str, config: Dict[str, Any], log_file: Optional[str] = None
    ) -> None:
        """
        Set up a logger with the given configuration.

        This method configures a logger with specified settings, including console and file handlers.

        Args:
            name (str): The name of the logger.
            config (Dict[str, Any]): Configuration dictionary for the logger.
            log_file (Optional[str]): Optional path to a specific log file. Overrides config file path if provided.

        Returns:
            None
        """
        if name in self.loggers:
            return

        logger = logging.getLogger(name)

        logger.handlers.clear()

        level = config.get("level", logging.INFO)
        logger.setLevel(level)

        log_format = config.get("log_format", self.DEFAULT_FORMAT)
        use_colors = config.get("use_colors", True)

        # Console Handler
        if config.get("console", {}).get("enabled", True):
            console_handler = ConditionalStreamHandler()
            console_formatter = ColoredFormatter(fmt=log_format, use_colors=use_colors)
            console_handler.setFormatter(console_formatter)
            console_handler.setLevel(level)
            logger.addHandler(console_handler)

        # File Handler
        file_config = config.get("file", {})
        if file_config.get("enabled", False):
            file_path = log_file or file_config.get("path")
            if file_path:
                path = Path(file_path)
                path.parent.mkdir(parents=True, exist_ok=True)
                file_handler = logging.FileHandler(str(path))
                file_formatter = logging.Formatter(fmt=log_format)
                file_handler.setFormatter(file_formatter)
                file_handler.setLevel(level)
                logger.addHandler(file_handler)

        # Prevent propagation to root logger
        logger.propagate = False

        # Store logger
        self.loggers[name] = logger

    def get_logger(self, name: str) -> logging.Logger:
        """Get logger by name."""
        return self.loggers.get(name, logging.getLogger(name))

    def set_console_log_level(self, service_name: str, level: int) -> None:
        """
        Adjust the console log level dynamically for a specific service.

        Args:
            service_name (str): The name of the service whose logger needs to be adjusted
            level (int): The logging level to set for the console handler
        """
        logger = self.get_logger(service_name)
        console_handler = next(
            (
                handler
                for handler in logger.handlers
                if isinstance(handler, logging.StreamHandler)
            ),
            None,
        )

        if console_handler:
            console_handler.setLevel(level)
            logger.info(f"Console log level set to: {logging.getLevelName(level)}")
        else:
            logger.warning("No console handler found to adjust the level.")
