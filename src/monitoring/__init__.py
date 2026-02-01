"""Monitoring and performance tracking for paper trading.

This module provides real-time monitoring, performance tracking, and
alerting capabilities for the trading system.

Components:
- PerformanceTracker: Track P&L, returns, and performance metrics
"""

from src.monitoring.performance_tracker import PerformanceTracker

__all__ = [
    "PerformanceTracker",
]
