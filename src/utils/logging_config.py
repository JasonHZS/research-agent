"""
Structured Logging Configuration

Provides a unified logging system using structlog that supports:
- Development mode: Colored, human-readable console output
- Production mode: JSON output for log aggregation (ELK/Splunk)

Usage:
    from src.utils.logging_config import configure_logging, get_logger

    # Initialize once at application startup
    configure_logging()

    # Get a logger in any module
    logger = get_logger(__name__)
    logger.info("User logged in", user_id="123", action="login")
"""

import logging
import logging.handlers
import os
import sys
from typing import Optional

import structlog
from structlog.types import Processor


def _is_production() -> bool:
    """Check if running in production environment."""
    env = os.getenv("ENV", os.getenv("ENVIRONMENT", "development")).lower()
    return env in ("production", "prod")


def _get_log_level() -> int:
    """Get log level from environment variable."""
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    return getattr(logging, level_name, logging.INFO)


def configure_logging(
    json_format: Optional[bool] = None,
    log_level: Optional[int] = None,
    log_file: Optional[str] = None,
) -> None:
    """
    Configure structlog for the application.

    Args:
        json_format: If True, output JSON logs. If None, auto-detect based on ENV.
        log_level: Logging level. If None, read from LOG_LEVEL env var (default: INFO).
        log_file: Log file path for production (defaults to LOG_FILE or logs/app.log).
    """
    # Determine output format
    if json_format is None:
        json_format = _is_production()

    # Determine log level
    if log_level is None:
        log_level = _get_log_level()

    # Shared processors for both dev and prod
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,  # Merge context from contextvars
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
        structlog.processors.format_exc_info,
    ]

    if json_format:
        # Production: JSON output to file
        if log_file is None:
            log_file = os.getenv("LOG_FILE", "logs/app.log")
        os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
        handler: logging.Handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
        )
        # ensure_ascii=False allows Chinese and other non-ASCII chars to render properly
        renderer = structlog.processors.JSONRenderer(ensure_ascii=False)
    else:
        # Development: Colored console output
        handler = logging.StreamHandler(sys.stdout)
        renderer = structlog.dev.ConsoleRenderer(
            colors=True,
            exception_formatter=structlog.dev.plain_traceback,
        )

    # Configure structlog
    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processor=renderer,
        foreign_pre_chain=shared_processors,
    )
    handler.setFormatter(formatter)

    # Configure standard library logging to use structlog formatting
    logging.basicConfig(
        format="%(message)s",
        handlers=[handler],
        level=log_level,
    )

    # Suppress noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: Optional[str] = None) -> structlog.stdlib.BoundLogger:
    """
    Get a structlog logger instance.

    Args:
        name: Logger name (typically __name__). If None, returns root logger.

    Returns:
        A bound structlog logger.

    Example:
        logger = get_logger(__name__)
        logger.info("Processing request", request_id="abc123")
        logger.error("Failed to process", error="timeout", exc_info=True)
    """
    return structlog.get_logger(name)


def bind_context(**kwargs) -> None:
    """
    Bind context variables that will be included in all subsequent logs.

    This is useful for adding request-scoped context like request_id.

    Args:
        **kwargs: Key-value pairs to bind to the context.

    Example:
        bind_context(request_id="abc123", user_id="user456")
        logger.info("Processing")  # Will include request_id and user_id
    """
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_context() -> None:
    """
    Clear all bound context variables.

    Call this at the end of request processing to prevent context leakage.
    """
    structlog.contextvars.clear_contextvars()
