"""Execution Layer - Order execution and position management.

This module provides order execution functionality for backtesting,
paper trading, and live trading modes.
"""

from src.execution.backtest_executor import BacktestExecutor
from src.execution.alpaca_executor import AlpacaExecutor
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
from src.execution.vectorbt_backtest import (
    VectorBTBacktest,
    VectorBTError,
    VectorBTResult,
)

__all__ = [
    # Abstract interface
    "OrderExecutor",
    # Concrete implementations
    "BacktestExecutor",
    "AlpacaExecutor",
    "VectorBTBacktest",
    # Data classes
    "ExecutionOrder",
    "Fill",
    "Position",
    "AccountInfo",
    "VectorBTResult",
    # Enums
    "OrderStatus",
    "OrderType",
    "TimeInForce",
    # Exceptions
    "VectorBTError",
]
