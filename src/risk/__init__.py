"""Risk Management Layer.

This layer is the safety guardian of the trading system, responsible for
preventing catastrophic losses by validating allocations and monitoring positions.

Components:
- RiskManager: Abstract interface for risk validation
- BasicRiskManager: Phase 1 static validation with auto-adjustment
- RiskCheckResult: Validation result with action and adjusted weights
- PositionRisk: Position-level risk metrics
- ExitSignal: Signal to exit a position due to risk trigger
"""

from src.risk.base import (
    ExitSignal,
    PositionRisk,
    RiskAction,
    RiskCheckResult,
    RiskManager,
)
from src.risk.basic_risk_manager import BasicRiskManager

__all__ = [
    "RiskManager",
    "BasicRiskManager",
    "RiskAction",
    "RiskCheckResult",
    "PositionRisk",
    "ExitSignal",
]
