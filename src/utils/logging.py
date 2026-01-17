"""Logging configuration for AI Trader.

This module provides structured logging setup with configurable output format.
"""

import logging
import sys
from typing import Any


def setup_logging(
    level: str = "INFO",
    log_format: str | None = None,
) -> None:
    """Configure logging for the application.

    Sets up the root logger with specified level and format.
    Logs are written to stdout for easy redirection and debugging.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Custom format string. If None, uses default format.

    Example:
        >>> from src.utils.logging import setup_logging
        >>> setup_logging(level="DEBUG")
        >>> import logging
        >>> logging.info("Application started")
    """
    if log_format is None:
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Convert string level to logging level constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Configure root logger
    logging.basicConfig(
        level=numeric_level,
        format=log_format,
        stream=sys.stdout,
        force=True,  # Override any existing configuration
    )


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for a module.

    Args:
        name: Logger name (typically __name__ of the module)

    Returns:
        Logger instance

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Data processing started")
    """
    return logging.getLogger(name)


def log_with_context(
    logger: logging.Logger,
    level: str,
    message: str,
    **context: Any,
) -> None:
    """Log a message with structured context.

    Logs message with additional context fields for debugging and monitoring.
    Context is appended to the message in key=value format.

    Args:
        logger: Logger instance
        level: Log level (debug, info, warning, error, critical)
        message: Log message
        **context: Additional context fields

    Example:
        >>> logger = get_logger(__name__)
        >>> log_with_context(
        ...     logger, "info", "Signal generated",
        ...     symbol="AAPL", signal=0.75, timestamp="2026-01-20"
        ... )
        # Logs: "Signal generated | symbol=AAPL signal=0.75 timestamp=2026-01-20"
    """
    log_func = getattr(logger, level.lower())

    if context:
        context_str = " ".join(f"{k}={v}" for k, v in context.items())
        full_message = f"{message} | {context_str}"
    else:
        full_message = message

    log_func(full_message)
