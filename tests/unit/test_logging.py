"""Unit tests for logging configuration."""

import logging

import pytest

from src.utils.logging import get_logger, log_with_context, setup_logging


class TestLoggingSetup:
    """Test cases for logging setup."""

    def test_setup_logging_default_level(self) -> None:
        """Test setup_logging with default INFO level."""
        setup_logging()
        logger = logging.getLogger("test")

        # Verify logger level is set correctly
        assert logger.getEffectiveLevel() == logging.INFO

    def test_setup_logging_sets_root_logger_level(self) -> None:
        """Test that setup_logging configures the root logger."""
        setup_logging(level="DEBUG")
        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG

    def test_setup_logging_debug_level(self) -> None:
        """Test setup_logging with DEBUG level."""
        setup_logging(level="DEBUG")
        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG

    def test_setup_logging_warning_level(self) -> None:
        """Test setup_logging with WARNING level."""
        setup_logging(level="WARNING")
        root_logger = logging.getLogger()
        assert root_logger.level == logging.WARNING

    def test_setup_logging_custom_format(self) -> None:
        """Test setup_logging accepts custom format without error."""
        custom_format = "%(levelname)s - %(message)s"
        # Should not raise any exception
        setup_logging(level="INFO", log_format=custom_format)
        assert logging.getLogger().level == logging.INFO

    def test_setup_logging_invalid_level_fallback(self) -> None:
        """Test setup_logging with invalid level falls back to INFO."""
        setup_logging(level="INVALID")
        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO


class TestGetLogger:
    """Test cases for get_logger function."""

    def test_get_logger_returns_logger(self) -> None:
        """Test get_logger returns a Logger instance."""
        logger = get_logger("test_module")
        assert isinstance(logger, logging.Logger)

    def test_get_logger_name(self) -> None:
        """Test get_logger creates logger with correct name."""
        logger = get_logger("test_module_name")
        assert logger.name == "test_module_name"

    def test_get_logger_different_instances(self) -> None:
        """Test get_logger returns same instance for same name."""
        logger1 = get_logger("test_same")
        logger2 = get_logger("test_same")
        assert logger1 is logger2


class TestLogWithContext:
    """Test cases for log_with_context function."""

    def test_log_with_context_info(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test logging info message with context."""
        logger = get_logger("test_context")

        # caplog automatically captures logs at the propagate level
        with caplog.at_level(logging.INFO, logger="test_context"):
            log_with_context(
                logger,
                "info",
                "Event occurred",
                symbol="AAPL",
                price=150.0,
            )

        # Check the captured records
        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert "Event occurred" in record.message
        assert "symbol=AAPL" in record.message
        assert "price=150.0" in record.message

    def test_log_with_context_no_context(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test logging message without context fields."""
        logger = get_logger("test_no_context")

        with caplog.at_level(logging.INFO, logger="test_no_context"):
            log_with_context(logger, "info", "Simple message")

        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert record.message == "Simple message"
        # Should not have the pipe separator when no context
        assert " | " not in record.message

    def test_log_with_context_debug(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test logging debug message with context."""
        logger = get_logger("test_debug_context")

        with caplog.at_level(logging.DEBUG, logger="test_debug_context"):
            log_with_context(
                logger,
                "debug",
                "Debug event",
                operation="fetch_data",
                duration_ms=123,
            )

        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert "Debug event" in record.message
        assert "operation=fetch_data" in record.message
        assert "duration_ms=123" in record.message

    def test_log_with_context_error(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test logging error message with context."""
        logger = get_logger("test_error_context")

        with caplog.at_level(logging.ERROR, logger="test_error_context"):
            log_with_context(
                logger,
                "error",
                "Operation failed",
                error_code=500,
                retry_count=3,
            )

        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert "Operation failed" in record.message
        assert "error_code=500" in record.message
        assert "retry_count=3" in record.message

    def test_log_with_context_multiple_fields(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test logging with multiple context fields."""
        logger = get_logger("test_multiple")

        with caplog.at_level(logging.INFO, logger="test_multiple"):
            log_with_context(
                logger,
                "info",
                "Trade executed",
                symbol="TSLA",
                quantity=100,
                price=250.5,
                order_type="market",
            )

        assert len(caplog.records) == 1
        record = caplog.records[0]
        message = record.message
        assert "Trade executed" in message
        assert "symbol=TSLA" in message
        assert "quantity=100" in message
        assert "price=250.5" in message
        assert "order_type=market" in message
