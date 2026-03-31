import logging

global_logging_enabled = True


class ConditionalStreamHandler(logging.StreamHandler):
    """
    A custom logging stream handler that respects the global logging flag.
    """

    def emit(self, record):
        """
        Emit a record if global logging is enabled.

        Args:
            record (logging.LogRecord): The log record to emit.
        """
        if global_logging_enabled:
            super().emit(record)
