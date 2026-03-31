import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

import yaml

from .logger_manager import LoggerManager

# Default config used when no config.yaml is found
_DEFAULT_CONFIG = {
    "logging": {
        "level": "INFO",
        "log_format": "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        "datefmt": "%H:%M:%S",
        "use_colors": True,
        "console": {"enabled": True},
        "file": {"enabled": False, "base_path": "logs"},
    }
}


def _find_config() -> dict:
    """Search upward from this file for config/config.yaml."""
    search = Path(__file__).resolve().parent.parent
    for _ in range(5):
        candidate = search / "config" / "config.yaml"
        if candidate.exists():
            with open(candidate, "r") as f:
                return yaml.safe_load(f)
        search = search.parent
    return _DEFAULT_CONFIG


class AppLogger:
    """Flexible coloured logger with optional file output.

    Loads ``config/config.yaml`` when found, falls back to sensible defaults.
    """

    def __init__(
        self,
        logger_name: str = "root",
        use_colors: bool = True,
        level: Union[str, int] = "INFO",
        log_file: Optional[str] = None,
    ):
        self.logger_manager = LoggerManager()
        self.config = _find_config()

        logger_config = dict(self.config.get("logging", _DEFAULT_CONFIG["logging"]))
        logger_config["use_colors"] = use_colors

        if isinstance(level, str):
            level = getattr(logging, level.upper())

        logger_config["level"] = level
        if "console" in logger_config:
            logger_config["console"]["level"] = level
        if "file" in logger_config:
            logger_config["file"]["level"] = level

        if not log_file and logger_config.get("file", {}).get("enabled", False):
            log_file = self._generate_log_file_path(logger_name, logger_config)

        self.logger_manager.setup_logger(logger_name, logger_config, log_file)
        self._logger = self.logger_manager.get_logger(logger_name)
        self._logger_name = logger_name
        self._log_file = log_file

    def _generate_log_file_path(self, logger_name: str, config: dict) -> str:
        """
        This method creates a log file path based on the current timestamp,
        ensuring that each log file has a unique name. The base path for the
        log files is determined from the configuration.

        Args:
            logger_name (str): The name of the logger.
            config (dict): The logger configuration dictionary.

        Returns:
            str: The generated log file path.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_path = config.get("file", {}).get("base_path", "logs")
        filename = f"{logger_name}_{timestamp}.log"

        log_path = Path(base_path) / filename
        log_path.parent.mkdir(parents=True, exist_ok=True)

        return str(log_path)

    @property
    def log_file(self) -> Optional[str]:
        """Return the log file path."""
        return self._log_file

    def _format_message(self, msg: str) -> str:
        """Format log message with logger name."""
        return msg

    def debug(self, msg: str, *args, **kwargs) -> None:
        """Log debug message."""
        self._logger.debug(self._format_message(msg), *args, **kwargs)

    def info(self, msg: str, *args, **kwargs) -> None:
        """Log info message."""
        self._logger.info(self._format_message(msg), *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs) -> None:
        """Log warning message."""
        self._logger.warning(self._format_message(msg), *args, **kwargs)

    def error(self, msg: str, *args, **kwargs) -> None:
        """Log error message."""
        self._logger.error(self._format_message(msg), *args, **kwargs)

    def exception(self, msg: str, *args, **kwargs) -> None:
        """Log exception with traceback."""
        kwargs["exc_info"] = True
        self._logger.error(self._format_message(msg), *args, **kwargs)

    def critical(self, msg: str, *args, **kwargs) -> None:
        """Log critical message."""
        self._logger.critical(self._format_message(msg), *args, **kwargs)
