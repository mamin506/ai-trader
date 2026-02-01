"""Orchestration Layer - Coordinates all layers for trading workflows.

This module provides orchestrators that coordinate Data, Strategy, Portfolio,
Risk, and Execution layers for backtesting and live/paper trading.
"""

from src.orchestration.backtest_orchestrator import (
    BacktestConfig,
    BacktestOrchestrator,
    BacktestResult,
)
from src.orchestration.scheduler import TradingScheduler, is_market_open, is_trading_day
from src.orchestration.workflows import DailyWorkflow, WorkflowConfig

__all__ = [
    # Backtesting
    "BacktestOrchestrator",
    "BacktestConfig",
    "BacktestResult",
    # Paper Trading
    "TradingScheduler",
    "DailyWorkflow",
    "WorkflowConfig",
    # Utilities
    "is_market_open",
    "is_trading_day",
]
