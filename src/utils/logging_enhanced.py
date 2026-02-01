"""Enhanced logging for trading events with rotation and structured output.

This module extends the basic logging with trading-specific event logging,
log rotation, and structured JSON formatting for analysis.
"""

import json
import logging
import logging.handlers
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

from src.utils.logging import get_logger


class TradingEventType(Enum):
    """Types of trading events to log."""

    # Order events
    ORDER_SUBMITTED = "order_submitted"
    ORDER_FILLED = "order_filled"
    ORDER_REJECTED = "order_rejected"
    ORDER_CANCELLED = "order_cancelled"

    # Risk events
    STOP_LOSS_TRIGGERED = "stop_loss_triggered"
    TAKE_PROFIT_TRIGGERED = "take_profit_triggered"
    CIRCUIT_BREAKER_TRIGGERED = "circuit_breaker_triggered"

    # Signal events
    SIGNAL_GENERATED = "signal_generated"
    ALLOCATION_CALCULATED = "allocation_calculated"
    RISK_CHECK_PASSED = "risk_check_passed"
    RISK_CHECK_FAILED = "risk_check_failed"

    # System events
    TRADING_SESSION_STARTED = "trading_session_started"
    TRADING_SESSION_ENDED = "trading_session_ended"
    MARKET_OPEN = "market_open"
    MARKET_CLOSE = "market_close"

    # Performance events
    DAILY_PERFORMANCE_RECORDED = "daily_performance_recorded"

    # Error events
    EXECUTION_ERROR = "execution_error"
    DATA_ERROR = "data_error"
    API_ERROR = "api_error"


class TradingLogger:
    """Enhanced logger for trading events with rotation and structured output.

    Features:
    - Automatic log rotation (daily, with size limits)
    - Structured JSON logging for analysis
    - Trading-specific event types
    - Separate log files for different event types

    Example:
        >>> logger = TradingLogger(log_dir="logs")
        >>> logger.log_order_event(
        ...     event_type=TradingEventType.ORDER_FILLED,
        ...     symbol="AAPL",
        ...     shares=100,
        ...     price=150.25,
        ...     order_id="order_123",
        ... )
    """

    def __init__(
        self,
        log_dir: str | Path = "logs",
        max_bytes: int = 10 * 1024 * 1024,  # 10 MB
        backup_count: int = 30,  # Keep 30 days of logs
        enable_console: bool = True,
    ):
        """Initialize enhanced trading logger.

        Args:
            log_dir: Directory for log files
            max_bytes: Maximum size per log file (default 10 MB)
            backup_count: Number of backup files to keep (default 30)
            enable_console: Also log to console (default True)
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.enable_console = enable_console

        # Create specialized loggers
        self.order_logger = self._create_rotating_logger("orders")
        self.risk_logger = self._create_rotating_logger("risk")
        self.signal_logger = self._create_rotating_logger("signals")
        self.system_logger = self._create_rotating_logger("system")
        self.error_logger = self._create_rotating_logger("errors", level=logging.ERROR)

    def _create_rotating_logger(
        self,
        name: str,
        level: int = logging.INFO,
    ) -> logging.Logger:
        """Create a rotating file logger.

        Args:
            name: Logger name and file prefix
            level: Logging level

        Returns:
            Configured logger
        """
        logger = logging.getLogger(f"trading.{name}")
        logger.setLevel(level)

        # Remove existing handlers
        logger.handlers = []

        # File handler with rotation
        log_file = self.log_dir / f"{name}.log"
        file_handler = logging.handlers.RotatingFileHandler(
            filename=log_file,
            maxBytes=self.max_bytes,
            backupCount=self.backup_count,
        )
        file_handler.setLevel(level)

        # JSON formatter for structured logging
        formatter = logging.Formatter(
            '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": %(message)s}'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # Console handler (optional)
        if self.enable_console:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(level)
            console_formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            console_handler.setFormatter(console_formatter)
            logger.addHandler(console_handler)

        return logger

    def _log_structured_event(
        self,
        logger: logging.Logger,
        event_type: TradingEventType,
        level: str = "info",
        **data: Any,
    ) -> None:
        """Log a structured event as JSON.

        Args:
            logger: Logger instance to use
            event_type: Type of trading event
            level: Log level (default: info)
            **data: Event data fields
        """
        event = {
            "event_type": event_type.value,
            "timestamp": datetime.now().isoformat(),
            **data,
        }

        # Get the appropriate log function
        log_func = getattr(logger, level)
        # Log as JSON string (formatter will wrap it)
        log_func(json.dumps(event))

    def log_order_event(
        self,
        event_type: TradingEventType,
        symbol: str,
        shares: int,
        price: Optional[float] = None,
        order_id: Optional[str] = None,
        **extra: Any,
    ) -> None:
        """Log an order-related event.

        Args:
            event_type: Type of order event
            symbol: Ticker symbol
            shares: Number of shares
            price: Order price (optional)
            order_id: Order ID (optional)
            **extra: Additional event data
        """
        data = {
            "symbol": symbol,
            "shares": shares,
        }

        if price is not None:
            data["price"] = price
        if order_id is not None:
            data["order_id"] = order_id

        data.update(extra)

        self._log_structured_event(self.order_logger, event_type, **data)

    def log_risk_event(
        self,
        event_type: TradingEventType,
        reason: str,
        symbol: Optional[str] = None,
        **extra: Any,
    ) -> None:
        """Log a risk-related event.

        Args:
            event_type: Type of risk event
            reason: Reason for risk trigger
            symbol: Affected symbol (optional)
            **extra: Additional event data
        """
        data = {
            "reason": reason,
        }

        if symbol is not None:
            data["symbol"] = symbol

        data.update(extra)

        self._log_structured_event(self.risk_logger, event_type, **data)

    def log_signal_event(
        self,
        event_type: TradingEventType,
        symbol: str,
        signal_value: Optional[float] = None,
        **extra: Any,
    ) -> None:
        """Log a signal-related event.

        Args:
            event_type: Type of signal event
            symbol: Ticker symbol
            signal_value: Signal value (optional)
            **extra: Additional event data
        """
        data = {
            "symbol": symbol,
        }

        if signal_value is not None:
            data["signal_value"] = signal_value

        data.update(extra)

        self._log_structured_event(self.signal_logger, event_type, **data)

    def log_system_event(
        self,
        event_type: TradingEventType,
        message: str,
        **extra: Any,
    ) -> None:
        """Log a system-related event.

        Args:
            event_type: Type of system event
            message: Event message
            **extra: Additional event data
        """
        data = {
            "message": message,
        }

        data.update(extra)

        self._log_structured_event(self.system_logger, event_type, **data)

    def log_error(
        self,
        event_type: TradingEventType,
        error: str,
        **extra: Any,
    ) -> None:
        """Log an error event.

        Args:
            event_type: Type of error event
            error: Error message or description
            **extra: Additional event data
        """
        data = {
            "error": error,
        }

        data.update(extra)

        self._log_structured_event(self.error_logger, event_type, level="error", **data)

    def log_performance(
        self,
        portfolio_value: float,
        daily_pnl: float,
        daily_return: float,
        **extra: Any,
    ) -> None:
        """Log daily performance metrics.

        Args:
            portfolio_value: End-of-day portfolio value
            daily_pnl: Daily profit/loss
            daily_return: Daily return percentage
            **extra: Additional performance data
        """
        data = {
            "portfolio_value": portfolio_value,
            "daily_pnl": daily_pnl,
            "daily_return": daily_return,
        }

        data.update(extra)

        self._log_structured_event(
            self.system_logger,
            TradingEventType.DAILY_PERFORMANCE_RECORDED,
            **data,
        )


# Global logger instance
_trading_logger: Optional[TradingLogger] = None


def get_trading_logger(log_dir: str | Path = "logs") -> TradingLogger:
    """Get or create the global trading logger instance.

    Args:
        log_dir: Directory for log files

    Returns:
        TradingLogger instance
    """
    global _trading_logger

    if _trading_logger is None:
        _trading_logger = TradingLogger(log_dir=log_dir)

    return _trading_logger
