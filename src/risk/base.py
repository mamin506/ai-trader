"""Abstract base class for risk management.

This module defines the contract for risk validation and monitoring.
The Risk Management Layer sits between Portfolio Management and Execution Layer.

Core Philosophy: "First, do no harm. Preserve capital above all else."

Responsibilities:
- Pre-trade risk checks (static validation)
- Position-level monitoring (stop-loss, take-profit) - Phase 2
- Portfolio-level risk management (drawdown protection) - Phase 3
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple


class RiskAction(Enum):
    """Risk check result actions."""

    APPROVE = "approve"  # No changes needed
    ADJUST = "adjust"  # Weights were modified to comply
    REJECT = "reject"  # Cannot comply, reject entirely
    REDUCE_EXPOSURE = "reduce_exposure"  # Portfolio-level risk trigger
    HALT_TRADING = "halt_trading"  # Circuit breaker activated


@dataclass
class RiskCheckResult:
    """Result of a risk validation check.

    Attributes:
        action: What action was taken (approve, adjust, reject)
        is_compliant: Whether the final result passes all checks
        original_weights: Weights before any adjustments
        adjusted_weights: Weights after adjustments (same as original if no changes)
        violations: List of rule violations found
        adjustments: List of adjustments made
        message: Human-readable summary
    """

    action: RiskAction
    is_compliant: bool
    original_weights: Dict[str, float]
    adjusted_weights: Dict[str, float]
    violations: List[str] = field(default_factory=list)
    adjustments: List[str] = field(default_factory=list)
    message: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class PositionRisk:
    """Risk metrics for a single position.

    Attributes:
        symbol: Ticker symbol
        entry_price: Price at which position was opened
        current_price: Current market price
        shares: Number of shares held
        pnl_pct: Profit/loss percentage
        peak_price: Highest price since entry (for trailing stop)
        drawdown_from_peak: Percentage drop from peak
        days_held: Number of days position has been held
    """

    symbol: str
    entry_price: float
    current_price: float
    shares: int
    pnl_pct: float
    peak_price: float = 0.0
    drawdown_from_peak: float = 0.0
    days_held: int = 0

    def __post_init__(self):
        """Calculate derived fields."""
        if self.peak_price == 0.0:
            self.peak_price = max(self.entry_price, self.current_price)

        if self.entry_price > 0:
            self.pnl_pct = (self.current_price - self.entry_price) / self.entry_price

        if self.peak_price > 0:
            self.drawdown_from_peak = (
                self.current_price - self.peak_price
            ) / self.peak_price


@dataclass
class ExitSignal:
    """Signal to exit a position due to risk trigger.

    Attributes:
        symbol: Ticker symbol
        shares: Number of shares to sell
        reason: Why exit was triggered
        trigger_type: Type of risk trigger (stop_loss, take_profit, etc.)
        current_price: Price at time of trigger
    """

    symbol: str
    shares: int
    reason: str
    trigger_type: str
    current_price: float
    timestamp: datetime = field(default_factory=datetime.now)


class RiskManager(ABC):
    """Abstract interface for risk management.

    The Risk Manager validates portfolio allocations against risk rules
    and monitors positions for stop-loss/take-profit triggers.

    Design Principles:
    - Validate before execute (pre-trade checks)
    - Auto-adjust when possible (Mode B)
    - Log all violations and adjustments
    - Independent from Portfolio Management

    Example:
        >>> manager = BasicRiskManager(config)
        >>> weights = {'AAPL': 0.30, 'MSFT': 0.20, 'Cash': 0.50}
        >>> result = manager.validate_weights(weights)
        >>> if result.action == RiskAction.ADJUST:
        ...     print(f"Adjusted: {result.adjustments}")
        ...     weights = result.adjusted_weights
    """

    @abstractmethod
    def validate_weights(
        self,
        target_weights: Dict[str, float],
    ) -> RiskCheckResult:
        """Validate proposed portfolio weights against risk rules.

        This is the main pre-trade validation. Checks for:
        - Single position size limits
        - Total exposure limits
        - Minimum cash reserves

        Args:
            target_weights: Proposed allocation {symbol: weight}
                           Weights should sum to 1.0

        Returns:
            RiskCheckResult with action, adjusted weights, and messages

        Example:
            >>> weights = {'AAPL': 0.30, 'Cash': 0.70}
            >>> result = manager.validate_weights(weights)
            >>> # AAPL exceeds 20% limit, auto-adjusted to 20%
            >>> print(result.adjusted_weights)  # {'AAPL': 0.20, 'Cash': 0.80}
        """
        pass

    @abstractmethod
    def check_position_risk(
        self,
        position: PositionRisk,
    ) -> Optional[ExitSignal]:
        """Check if a position should be exited due to risk triggers.

        Evaluates stop-loss, take-profit, and trailing stop conditions.

        Args:
            position: Current position with price and P&L data

        Returns:
            ExitSignal if position should be exited, None otherwise

        Example:
            >>> position = PositionRisk(
            ...     symbol='AAPL',
            ...     entry_price=150.0,
            ...     current_price=135.0,  # -10% loss
            ...     shares=100,
            ...     pnl_pct=-0.10
            ... )
            >>> exit_signal = manager.check_position_risk(position)
            >>> if exit_signal:
            ...     print(f"Exit {exit_signal.symbol}: {exit_signal.reason}")
        """
        pass

    def validate_and_adjust(
        self,
        target_weights: Dict[str, float],
    ) -> Dict[str, float]:
        """Convenience method: validate and return adjusted weights.

        Args:
            target_weights: Proposed allocation

        Returns:
            Adjusted weights (compliant with risk rules)
        """
        result = self.validate_weights(target_weights)
        return result.adjusted_weights

    def check_positions(
        self,
        positions: List[PositionRisk],
    ) -> List[ExitSignal]:
        """Check multiple positions for risk triggers.

        Args:
            positions: List of current positions

        Returns:
            List of exit signals for positions that should be closed
        """
        exit_signals = []
        for position in positions:
            signal = self.check_position_risk(position)
            if signal:
                exit_signals.append(signal)
        return exit_signals
