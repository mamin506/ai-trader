"""Risk Management Layer.

This layer is the safety guardian of the trading system, responsible for
preventing catastrophic losses by validating allocations and monitoring positions.

Components:
- RiskManager: Abstract interface for risk validation
- BasicRiskManager: Phase 1 static validation with auto-adjustment
- DynamicRiskManager: Phase 2 real-time monitoring with position tracking
- RiskCheckResult: Validation result with action and adjusted weights
- PositionRisk: Position-level risk metrics
- ExitSignal: Signal to exit a position due to risk trigger
- PositionMonitor: Real-time position tracking
- PortfolioMonitor: Portfolio-level risk tracking
"""

from src.risk.base import (
    ExitSignal,
    PositionRisk,
    RiskAction,
    RiskCheckResult,
    RiskManager,
)
from src.risk.basic_risk_manager import BasicRiskManager
from src.risk.dynamic_risk_manager import DynamicRiskManager
from src.risk.monitors import PortfolioMonitor, PositionMonitor

__all__ = [
    "RiskManager",
    "BasicRiskManager",
    "DynamicRiskManager",
    "RiskAction",
    "RiskCheckResult",
    "PositionRisk",
    "ExitSignal",
    "PositionMonitor",
    "PortfolioMonitor",
]
