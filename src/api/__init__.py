"""User-friendly APIs for AI Trader.

This package provides high-level interfaces for interacting with the trading system.

Components:
- DataAPI: Market data access
- StrategyAPI: Strategy testing and backtesting
- PortfolioAPI: Portfolio allocation and management
- RiskAPI: Risk validation and monitoring
- ExecutionAPI: Trade execution and position management
- BacktestAPI: End-to-end backtesting
"""

from src.api.backtest_api import BacktestAPI
from src.api.data_api import DataAPI
from src.api.execution_api import ExecutionAPI
from src.api.portfolio_api import PortfolioAPI
from src.api.risk_api import RiskAPI
from src.api.strategy_api import StrategyAPI

__all__ = [
    "DataAPI",
    "StrategyAPI",
    "PortfolioAPI",
    "RiskAPI",
    "ExecutionAPI",
    "BacktestAPI",
]
