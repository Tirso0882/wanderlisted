import logging
from typing import Optional


class LogColors:
    """
    The `LogColors` class provides ANSI escape sequences for text formatting in the terminal.

    Attributes:
        Provides ANSI codes for basic and bold text in various colors
        (e.g., RED, GREEN, BLUE, etc.).
    """

    RESET = "\033[0m"
    BLACK = "\033[30m"
    RED = "\033[38;5;196m"
    GREEN = "\033[38;2;57;255;20m"
    YELLOW = "\033[38;2;255;255;0m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[38;2;0;255;255m"
    WHITE = "\033[37m"
    BOLD_RED = "\033[1;38;2;255;0;85m"
    BOLD_GREEN = "\033[1;32m"
    BOLD_YELLOW = "\033[1;33m"
    BOLD_BLUE = "\033[1;34m"
    BOLD_MAGENTA = "\033[1;35m"
    BOLD_CYAN = "\033[1;36m"
    BOLD_WHITE = "\033[1;37m"
    GREY = "\033[38;20m"


class ColoredFormatter(logging.Formatter):
    """
    Custom formatter to add colors to log messages based on their severity level.

    Attributes:
    ----------
    LEVEL_COLORS : dict
        Mapping of logging levels to corresponding color codes, used to format log messages in different colors.

    Methods:
    -------
    format(record):
        Formats a log record by adding a corresponding color based on the severity level.
    """

    COLORS = {
        logging.DEBUG: LogColors.CYAN,
        logging.INFO: LogColors.GREEN,
        logging.WARNING: LogColors.YELLOW,
        logging.ERROR: LogColors.RED,
        logging.CRITICAL: LogColors.BOLD_RED,
    }

    def __init__(self, fmt: Optional[str] = None, use_colors: bool = True):
        """
        Initialize the formatter.

        Args:
            fmt: Log format string
            use_colors: Whether to use colored output
        """
        if fmt is None:
            fmt = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
        super().__init__(fmt=fmt)
        self.use_colors = use_colors

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record with optional colors."""
        if not self.use_colors:
            return super().format(record)

        # Save original values
        orig_levelname = record.levelname
        orig_msg = record.msg

        # Add color
        color = self.COLORS.get(record.levelno, LogColors.GREY)
        record.levelname = f"{color}{record.levelname}{LogColors.RESET}"
        record.msg = f"{color}{record.msg}{LogColors.RESET}"

        # Format record
        result = super().format(record)

        # Restore original values
        record.levelname = orig_levelname
        record.msg = orig_msg

        return result
