"""Unit tests for enhanced logging utilities.

Tests trading event logging, log rotation, and structured output.
"""

import json
import logging
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from src.utils.logging_enhanced import (
    TradingEventType,
    TradingLogger,
    get_trading_logger,
)


class TestTradingEventType:
    """Tests for TradingEventType enum."""

    def test_order_events(self):
        """Test order event types."""
        assert TradingEventType.ORDER_SUBMITTED.value == "order_submitted"
        assert TradingEventType.ORDER_FILLED.value == "order_filled"
        assert TradingEventType.ORDER_REJECTED.value == "order_rejected"
        assert TradingEventType.ORDER_CANCELLED.value == "order_cancelled"

    def test_risk_events(self):
        """Test risk event types."""
        assert TradingEventType.STOP_LOSS_TRIGGERED.value == "stop_loss_triggered"
        assert TradingEventType.TAKE_PROFIT_TRIGGERED.value == "take_profit_triggered"
        assert TradingEventType.CIRCUIT_BREAKER_TRIGGERED.value == "circuit_breaker_triggered"

    def test_signal_events(self):
        """Test signal event types."""
        assert TradingEventType.SIGNAL_GENERATED.value == "signal_generated"
        assert TradingEventType.ALLOCATION_CALCULATED.value == "allocation_calculated"


class TestTradingLogger:
    """Tests for TradingLogger."""

    def test_initialization(self):
        """Test TradingLogger initialization."""
        with TemporaryDirectory() as tmpdir:
            logger = TradingLogger(log_dir=tmpdir)

            assert logger.log_dir == Path(tmpdir)
            assert logger.max_bytes == 10 * 1024 * 1024
            assert logger.backup_count == 30

            # Check log files are created
            assert (Path(tmpdir) / "orders.log").exists()
            assert (Path(tmpdir) / "risk.log").exists()
            assert (Path(tmpdir) / "signals.log").exists()
            assert (Path(tmpdir) / "system.log").exists()
            assert (Path(tmpdir) / "errors.log").exists()

    def test_log_order_event(self):
        """Test logging order events."""
        with TemporaryDirectory() as tmpdir:
            logger = TradingLogger(log_dir=tmpdir, enable_console=False)

            logger.log_order_event(
                event_type=TradingEventType.ORDER_FILLED,
                symbol="AAPL",
                shares=100,
                price=150.25,
                order_id="order_123",
            )

            # Read log file
            log_file = Path(tmpdir) / "orders.log"
            with open(log_file) as f:
                log_line = f.read().strip()

            # Parse JSON (outer formatter adds wrapper)
            assert "order_filled" in log_line
            assert "AAPL" in log_line
            assert "100" in log_line

    def test_log_risk_event(self):
        """Test logging risk events."""
        with TemporaryDirectory() as tmpdir:
            logger = TradingLogger(log_dir=tmpdir, enable_console=False)

            logger.log_risk_event(
                event_type=TradingEventType.STOP_LOSS_TRIGGERED,
                reason="Price dropped below -3% threshold",
                symbol="MSFT",
                current_price=285.50,
            )

            # Read log file
            log_file = Path(tmpdir) / "risk.log"
            with open(log_file) as f:
                log_line = f.read().strip()

            assert "stop_loss_triggered" in log_line
            assert "MSFT" in log_line
            assert "Price dropped" in log_line

    def test_log_signal_event(self):
        """Test logging signal events."""
        with TemporaryDirectory() as tmpdir:
            logger = TradingLogger(log_dir=tmpdir, enable_console=False)

            logger.log_signal_event(
                event_type=TradingEventType.SIGNAL_GENERATED,
                symbol="GOOGL",
                signal_value=0.75,
                strategy="MA_Crossover",
            )

            # Read log file
            log_file = Path(tmpdir) / "signals.log"
            with open(log_file) as f:
                log_line = f.read().strip()

            assert "signal_generated" in log_line
            assert "GOOGL" in log_line
            assert "0.75" in log_line

    def test_log_system_event(self):
        """Test logging system events."""
        with TemporaryDirectory() as tmpdir:
            logger = TradingLogger(log_dir=tmpdir, enable_console=False)

            logger.log_system_event(
                event_type=TradingEventType.TRADING_SESSION_STARTED,
                message="Paper trading session started",
                mode="paper",
            )

            # Read log file
            log_file = Path(tmpdir) / "system.log"
            with open(log_file) as f:
                log_line = f.read().strip()

            assert "trading_session_started" in log_line
            assert "Paper trading" in log_line

    def test_log_error(self):
        """Test logging error events."""
        with TemporaryDirectory() as tmpdir:
            logger = TradingLogger(log_dir=tmpdir, enable_console=False)

            logger.log_error(
                event_type=TradingEventType.EXECUTION_ERROR,
                error="Failed to submit order: Connection timeout",
                symbol="AAPL",
            )

            # Read log file
            log_file = Path(tmpdir) / "errors.log"
            with open(log_file) as f:
                log_line = f.read().strip()

            assert "execution_error" in log_line
            assert "Connection timeout" in log_line

    def test_log_performance(self):
        """Test logging performance metrics."""
        with TemporaryDirectory() as tmpdir:
            logger = TradingLogger(log_dir=tmpdir, enable_console=False)

            logger.log_performance(
                portfolio_value=105000.0,
                daily_pnl=2000.0,
                daily_return=0.02,
                sharpe_ratio=1.5,
            )

            # Read log file
            log_file = Path(tmpdir) / "system.log"
            with open(log_file) as f:
                log_line = f.read().strip()

            assert "daily_performance_recorded" in log_line
            assert "105000" in log_line
            assert "2000" in log_line

    def test_json_structure(self):
        """Test that logged events have proper JSON structure."""
        with TemporaryDirectory() as tmpdir:
            logger = TradingLogger(log_dir=tmpdir, enable_console=False)

            logger.log_order_event(
                event_type=TradingEventType.ORDER_SUBMITTED,
                symbol="AAPL",
                shares=100,
                price=150.0,
            )

            # Read and parse log
            log_file = Path(tmpdir) / "orders.log"
            with open(log_file, encoding="utf-8") as f:
                log_line = f.read().strip()

            # The log line is a JSON object with timestamp, level, and message
            log_json = json.loads(log_line)

            assert "timestamp" in log_json
            assert "level" in log_json
            assert "message" in log_json

            # Message field contains another JSON string that needs parsing
            # The formatter inserts the JSON without quotes, making it an object
            if isinstance(log_json["message"], str):
                event_json = json.loads(log_json["message"])
            else:
                # Message is already parsed as an object
                event_json = log_json["message"]

            assert event_json["event_type"] == "order_submitted"
            assert event_json["symbol"] == "AAPL"
            assert event_json["shares"] == 100
            assert event_json["price"] == 150.0
            assert "timestamp" in event_json

    def test_disable_console_logging(self):
        """Test disabling console output."""
        with TemporaryDirectory() as tmpdir:
            logger = TradingLogger(log_dir=tmpdir, enable_console=False)

            # Check that loggers don't have StreamHandler
            for log in [logger.order_logger, logger.risk_logger]:
                stream_handlers = [
                    h for h in log.handlers
                    if isinstance(h, logging.StreamHandler)
                       and not isinstance(h, logging.handlers.RotatingFileHandler)
                ]
                assert len(stream_handlers) == 0


class TestGlobalLogger:
    """Tests for global logger instance."""

    def test_get_trading_logger(self):
        """Test getting global trading logger."""
        with TemporaryDirectory() as tmpdir:
            logger = get_trading_logger(log_dir=tmpdir)

            assert isinstance(logger, TradingLogger)

    def test_get_trading_logger_singleton(self):
        """Test that get_trading_logger returns same instance."""
        # Note: This test assumes the global logger persists between calls
        # In a real test suite, you'd want to reset global state between tests
        with TemporaryDirectory() as tmpdir:
            logger1 = get_trading_logger(log_dir=tmpdir)
            logger2 = get_trading_logger(log_dir=tmpdir)

            # Should be the same instance (singleton pattern)
            assert logger1 is logger2
