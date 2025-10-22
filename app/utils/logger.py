"""
Logging Utilities
구조화된 로깅 설정
"""
import sys
import logging
from pathlib import Path
from typing import Any
import structlog
from structlog.types import Processor

from app.config import settings


def setup_logging() -> None:
    """
    Setup structured logging with structlog

    Configures JSON or text logging based on settings
    """
    # Determine log processors based on format
    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.logging.format == "json":
        # JSON formatting for production
        processors.extend([
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer()
        ])
    else:
        # Console-friendly formatting for development
        processors.extend([
            structlog.processors.ExceptionPrettyPrinter(),
            structlog.dev.ConsoleRenderer(colors=True)
        ])

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=settings.logging.log_level,
    )

    # Set log file if specified
    if settings.logging.file:
        log_path = Path(settings.logging.file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(
            settings.logging.file,
            encoding='utf-8'
        )
        file_handler.setLevel(settings.logging.log_level)

        root_logger = logging.getLogger()
        root_logger.addHandler(file_handler)


def get_logger(name: str = __name__) -> Any:
    """
    Get a structured logger instance

    Args:
        name: Logger name (typically __name__)

    Returns:
        Structured logger instance
    """
    return structlog.get_logger(name)


class LoggerMixin:
    """
    Mixin class to add logging capability to any class

    Usage:
        class MyService(LoggerMixin):
            def my_method(self):
                self.logger.info("my_event", key="value")
    """

    @property
    def logger(self) -> Any:
        """Get logger instance for this class"""
        if not hasattr(self, '_logger'):
            self._logger = get_logger(self.__class__.__name__)
        return self._logger
