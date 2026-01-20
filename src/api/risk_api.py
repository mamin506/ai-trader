"""User-friendly Risk API for risk validation and monitoring.

This module provides a simple, high-level interface for validating
portfolio allocations and monitoring position risks.
"""

from typing import Dict, List, Optional

import pandas as pd

from src.portfolio.base import AllocationResult, PortfolioState
from src.risk.base import ExitSignal, PositionRisk, RiskAction, RiskCheckResult, RiskManager
from src.risk.basic_risk_manager import BasicRiskManager
from src.utils.logging import get_logger

logger = get_logger(__name__)


class RiskAPI:
    """High-level API for risk management.

    Provides simple methods for validating allocations and checking
    position risks.

    Example:
        >>> from src.api.risk_api import RiskAPI
        >>>
        >>> # Initialize API
        >>> api = RiskAPI()
        >>>
        >>> # Validate proposed weights
        >>> weights = {'AAPL': 0.30, 'MSFT': 0.20, 'Cash': 0.50}
        >>> result = api.validate_allocation(weights)
        >>> if result['adjusted']:
        ...     print(f"Weights adjusted: {result['adjustments']}")
    """

    def __init__(self, risk_manager: Optional[RiskManager] = None):
        """Initialize RiskAPI.

        Args:
            risk_manager: RiskManager instance (defaults to BasicRiskManager)
        """
        self.risk_manager = risk_manager or BasicRiskManager()
        logger.debug("RiskAPI initialized with %s", type(self.risk_manager).__name__)

    def validate_allocation(
        self,
        target_weights: Dict[str, float],
    ) -> Dict:
        """Validate proposed portfolio weights against risk rules.

        Args:
            target_weights: Proposed allocation {symbol: weight}

        Returns:
            Dictionary with:
                - valid: Whether allocation passes all checks
                - adjusted: Whether weights were modified
                - original_weights: Input weights
                - final_weights: Weights after any adjustments
                - violations: List of rule violations found
                - adjustments: List of adjustments made
                - message: Human-readable summary

        Example:
            >>> api = RiskAPI()
            >>> result = api.validate_allocation({'AAPL': 0.30, 'Cash': 0.70})
            >>> # AAPL exceeds 20% limit
            >>> print(result['final_weights'])  # {'AAPL': 0.20, 'Cash': 0.80}
        """
        logger.info("Validating allocation: %d positions", len(target_weights))

        result = self.risk_manager.validate_weights(target_weights)

        return {
            "valid": result.is_compliant,
            "adjusted": result.action == RiskAction.ADJUST,
            "original_weights": result.original_weights,
            "final_weights": result.adjusted_weights,
            "violations": result.violations,
            "adjustments": result.adjustments,
            "message": result.message,
        }

    def validate_and_get_weights(
        self,
        target_weights: Dict[str, float],
    ) -> Dict[str, float]:
        """Validate and return compliant weights.

        Convenience method that just returns the adjusted weights.

        Args:
            target_weights: Proposed allocation

        Returns:
            Adjusted weights (compliant with risk rules)

        Example:
            >>> api = RiskAPI()
            >>> weights = api.validate_and_get_weights({'AAPL': 0.30, 'Cash': 0.70})
            >>> # Returns {'AAPL': 0.20, 'Cash': 0.80}
        """
        return self.risk_manager.validate_and_adjust(target_weights)

    def check_position_risks(
        self,
        positions: List[Dict],
    ) -> List[Dict]:
        """Check multiple positions for risk triggers.

        Args:
            positions: List of position dictionaries with keys:
                - symbol: Ticker symbol
                - entry_price: Price at entry
                - current_price: Current price
                - shares: Number of shares
                - peak_price: (optional) Highest price since entry

        Returns:
            List of exit signals (empty if no exits triggered)

        Example:
            >>> api = RiskAPI()
            >>> positions = [
            ...     {'symbol': 'AAPL', 'entry_price': 150, 'current_price': 135, 'shares': 100},
            ...     {'symbol': 'MSFT', 'entry_price': 350, 'current_price': 360, 'shares': 50},
            ... ]
            >>> exits = api.check_position_risks(positions)
            >>> # AAPL is down 10%, may trigger stop-loss
        """
        logger.info("Checking risks for %d positions", len(positions))

        # Convert to PositionRisk objects
        position_risks = []
        for pos in positions:
            entry = pos["entry_price"]
            current = pos["current_price"]
            peak = pos.get("peak_price", max(entry, current))

            pnl_pct = (current - entry) / entry if entry > 0 else 0.0
            drawdown = (current - peak) / peak if peak > 0 else 0.0

            position_risks.append(
                PositionRisk(
                    symbol=pos["symbol"],
                    entry_price=entry,
                    current_price=current,
                    shares=pos["shares"],
                    pnl_pct=pnl_pct,
                    peak_price=peak,
                    drawdown_from_peak=drawdown,
                    days_held=pos.get("days_held", 0),
                )
            )

        # Check for exits
        exit_signals = self.risk_manager.check_positions(position_risks)

        # Convert to dictionaries
        return [
            {
                "symbol": sig.symbol,
                "shares": sig.shares,
                "reason": sig.reason,
                "trigger_type": sig.trigger_type,
                "current_price": sig.current_price,
            }
            for sig in exit_signals
        ]

    def get_risk_metrics(
        self,
        weights: Dict[str, float],
    ) -> Dict:
        """Get risk metrics for a portfolio allocation.

        Args:
            weights: Portfolio weights {symbol: weight}

        Returns:
            Dictionary with risk metrics

        Example:
            >>> api = RiskAPI()
            >>> metrics = api.get_risk_metrics({'AAPL': 0.20, 'MSFT': 0.15, 'Cash': 0.65})
            >>> print(f"Exposure: {metrics['total_exposure']:.1%}")
        """
        if isinstance(self.risk_manager, BasicRiskManager):
            return self.risk_manager.get_risk_metrics(weights)

        # Fallback for other risk managers
        equity_weights = {s: w for s, w in weights.items() if s != "Cash"}
        return {
            "total_exposure": sum(equity_weights.values()),
            "cash_weight": weights.get("Cash", 0.0),
            "position_count": float(len(equity_weights)),
        }

    def validate_allocation_result(
        self,
        allocation: AllocationResult,
    ) -> Dict:
        """Validate an AllocationResult from PortfolioManager.

        Convenience method for integrating with Portfolio layer.

        Args:
            allocation: AllocationResult from portfolio allocation

        Returns:
            Dictionary with validation results and adjusted weights

        Example:
            >>> portfolio_api = PortfolioAPI()
            >>> result = portfolio_api.get_allocation(...)
            >>> risk_api = RiskAPI()
            >>> validated = risk_api.validate_allocation_result(result)
        """
        return self.validate_allocation(allocation.target_weights)

    def format_validation_result(
        self,
        result: Dict,
    ) -> pd.DataFrame:
        """Format validation result for display.

        Args:
            result: Validation result dictionary

        Returns:
            DataFrame with validation details
        """
        data = []

        # Add weights comparison
        original = result["original_weights"]
        final = result["final_weights"]
        all_symbols = set(original.keys()) | set(final.keys())

        for symbol in sorted(all_symbols):
            orig = original.get(symbol, 0.0)
            fin = final.get(symbol, 0.0)
            changed = abs(orig - fin) > 0.001

            data.append(
                {
                    "symbol": symbol,
                    "original": f"{orig:.1%}",
                    "final": f"{fin:.1%}",
                    "changed": "Yes" if changed else "",
                }
            )

        return pd.DataFrame(data)

    def format_exit_signals(
        self,
        exits: List[Dict],
    ) -> pd.DataFrame:
        """Format exit signals for display.

        Args:
            exits: List of exit signal dictionaries

        Returns:
            DataFrame with exit details
        """
        if not exits:
            return pd.DataFrame(columns=["symbol", "shares", "trigger", "reason"])

        return pd.DataFrame(
            [
                {
                    "symbol": e["symbol"],
                    "shares": e["shares"],
                    "trigger": e["trigger_type"],
                    "reason": e["reason"],
                }
                for e in exits
            ]
        )

    def is_compliant(
        self,
        weights: Dict[str, float],
    ) -> bool:
        """Quick check if weights are compliant.

        Args:
            weights: Portfolio weights

        Returns:
            True if no adjustments needed
        """
        result = self.risk_manager.validate_weights(weights)
        return result.action == RiskAction.APPROVE
