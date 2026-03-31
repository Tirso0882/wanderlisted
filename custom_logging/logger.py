import logging
from typing import Any, Dict, Optional, Union


class UnicodeLogger(logging.Logger):
    """
    Custom logger to handle Unicode characters in log messages.
    This logger ensures that all messages and arguments are converted to strings,
    preventing encoding issues.
    """

    def __init__(self, name: str, level: int = logging.NOTSET):
        """Initialize the UnicodeLogger instance."""
        super().__init__(name, level)
        logging.setLoggerClass(UnicodeLogger)  # Set as default logger class

    def _log(
        self,
        level: int,
        msg: Any,
        args: tuple = (),
        exc_info: Optional[Union[BaseException, tuple[Any, Any, Any]]] = None,
        extra: Optional[Dict[str, Any]] = None,
        stack_info: bool = False,
        stacklevel: int = 1,
    ) -> None:
        """
        Low-level logging routine which creates LogRecord and calls handlers.

        Args:
            level (int): Logging level.
            msg (Any): Log message.
            args (Any): Arguments to be formatted into the message.
            exc_info (Optional[Exception or Tuple]): Exception information.
            extra (Optional[Dict[str, Any]]): Additional information for the LogRecord.
            stack_info (bool): Include stack information.
            stacklevel (int): The stack level at which the logging call was made.
        """
          # structlog passes a dict as msg for its ProcessorFormatter to handle later.
        # Converting it to str here breaks structlog's record.msg.copy() call.
        if not isinstance(msg, dict):
            msg = str(msg)
        # Only convert non-numeric args to strings to avoid uvicorn formatting issues
        converted_args = []
        for arg in args:
            if isinstance(arg, (int, float)):
                converted_args.append(arg)
            else:
                converted_args.append(str(arg))
        args = tuple(converted_args)
        
        super()._log(
            level,
            msg,
            args,
            exc_info,
            extra,
            stack_info=stack_info,
            stacklevel=stacklevel,
        )


# Set UnicodeLogger as the default logger class - Inherited by all logger instances
logging.setLoggerClass(UnicodeLogger)
