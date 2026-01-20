"""Execution Layer - Order execution and position management.

This module provides order execution functionality for backtesting,
paper trading, and live trading modes.
"""

from src.execution.backtest_executor import BacktestExecutor
from src.execution.base import (
    AccountInfo,
    ExecutionOrder,
    Fill,
    OrderExecutor,
    OrderStatus,
    OrderType,
    Position,
    TimeInForce,
)

__all__ = [
    # Abstract interface
    "OrderExecutor",
    # Concrete implementations
    "BacktestExecutor",
    # Data classes
    "ExecutionOrder",
    "Fill",
    "Position",
    "AccountInfo",
    # Enums
    "OrderStatus",
    "OrderType",
    "TimeInForce",
]
