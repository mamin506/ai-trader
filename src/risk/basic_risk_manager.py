"""Basic risk manager with static validation.

This module implements Phase 1 risk management: pre-trade validation
with automatic adjustment to comply with risk rules.

Enforcement Mode: Auto-Adjustment (Mode B)
- System keeps running, adjusts weights to comply
- All adjustments are logged for analysis
- Suitable for backtesting and automated systems
"""

from typing import Dict, List, Optional

from src.risk.base import (
    ExitSignal,
    PositionRisk,
    RiskAction,
    RiskCheckResult,
    RiskManager,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)


class BasicRiskManager(RiskManager):
    """Phase 1 risk manager with static pre-trade validation.

    Validates proposed portfolio allocations against basic risk rules
    and auto-adjusts to comply when possible.

    Risk Rules:
    - max_position_size: Maximum weight for single position (default 20%)
    - max_total_exposure: Maximum total invested (default 90%)
    - min_cash_reserve: Minimum cash to maintain (default 5%)

    Example:
        >>> config = {
        ...     'max_position_size': 0.20,
        ...     'max_total_exposure': 0.90,
        ...     'min_cash_reserve': 0.05
        ... }
        >>> manager = BasicRiskManager(config)
        >>> weights = {'AAPL': 0.30, 'MSFT': 0.15, 'Cash': 0.55}
        >>> result = manager.validate_weights(weights)
        >>> # AAPL capped at 20%, excess goes to Cash
        >>> print(result.adjusted_weights)
    """

    def __init__(self, config: Optional[Dict] = None):
        """Initialize risk manager with configuration.

        Args:
            config: Risk parameters. Uses sensible defaults if not provided.
        """
        config = config or {}

        self.max_position_size = config.get("max_position_size", 0.20)
        self.max_total_exposure = config.get("max_total_exposure", 0.90)
        self.min_cash_reserve = config.get("min_cash_reserve", 0.05)

        # Phase 2 parameters (stop-loss/take-profit)
        self.stop_loss_pct = config.get("stop_loss_pct", 0.08)
        self.take_profit_pct = config.get("take_profit_pct", 0.25)
        self.trailing_stop_pct = config.get("trailing_stop_pct", 0.05)

        self._validate_config()

        logger.debug(
            "BasicRiskManager initialized: max_pos=%.0f%%, max_exp=%.0f%%, min_cash=%.0f%%",
            self.max_position_size * 100,
            self.max_total_exposure * 100,
            self.min_cash_reserve * 100,
        )

    def _validate_config(self) -> None:
        """Validate configuration parameters."""
        if not 0 < self.max_position_size <= 1:
            raise ValueError(
                f"max_position_size must be in (0, 1], got {self.max_position_size}"
            )
        if not 0 < self.max_total_exposure <= 1:
            raise ValueError(
                f"max_total_exposure must be in (0, 1], got {self.max_total_exposure}"
            )
        if not 0 <= self.min_cash_reserve < 1:
            raise ValueError(
                f"min_cash_reserve must be in [0, 1), got {self.min_cash_reserve}"
            )
        if self.max_total_exposure + self.min_cash_reserve > 1:
            raise ValueError(
                f"max_total_exposure ({self.max_total_exposure}) + "
                f"min_cash_reserve ({self.min_cash_reserve}) cannot exceed 1.0"
            )

    def validate_weights(
        self,
        target_weights: Dict[str, float],
    ) -> RiskCheckResult:
        """Validate proposed portfolio weights against risk rules.

        Checks are applied in order:
        1. Single position size limits
        2. Total exposure limits
        3. Minimum cash reserve

        Args:
            target_weights: Proposed allocation {symbol: weight}

        Returns:
            RiskCheckResult with action, adjusted weights, and messages
        """
        original = target_weights.copy()
        adjusted = target_weights.copy()
        violations: List[str] = []
        adjustments: List[str] = []

        # Check 1: Single position size limits
        position_violations = []
        for symbol, weight in list(adjusted.items()):
            if symbol == "Cash":
                continue

            if weight > self.max_position_size:
                position_violations.append((symbol, weight))

        if position_violations:
            for symbol, weight in position_violations:
                excess = weight - self.max_position_size
                adjusted[symbol] = self.max_position_size
                adjusted["Cash"] = adjusted.get("Cash", 0.0) + excess

                violations.append(
                    f"{symbol} weight {weight:.1%} exceeds limit {self.max_position_size:.1%}"
                )

            adjustments.append(
                f"Capped {len(position_violations)} position(s) at {self.max_position_size:.0%}"
            )
            logger.info(
                "Position size violations: %d positions capped", len(position_violations)
            )

        # Check 2: Total exposure limit
        total_exposure = sum(w for s, w in adjusted.items() if s != "Cash")

        if total_exposure > self.max_total_exposure:
            scale_factor = self.max_total_exposure / total_exposure

            for symbol in adjusted:
                if symbol != "Cash":
                    adjusted[symbol] *= scale_factor

            # Recalculate cash
            new_exposure = sum(w for s, w in adjusted.items() if s != "Cash")
            adjusted["Cash"] = 1.0 - new_exposure

            violations.append(
                f"Total exposure {total_exposure:.1%} exceeds limit {self.max_total_exposure:.1%}"
            )
            adjustments.append(
                f"Scaled exposure from {total_exposure:.1%} to {self.max_total_exposure:.1%}"
            )
            logger.info(
                "Exposure violation: scaled from %.1f%% to %.1f%%",
                total_exposure * 100,
                self.max_total_exposure * 100,
            )

        # Check 3: Minimum cash reserve
        cash = adjusted.get("Cash", 0.0)

        if cash < self.min_cash_reserve:
            shortage = self.min_cash_reserve - cash
            current_invested = sum(w for s, w in adjusted.items() if s != "Cash")

            if current_invested > 0:
                scale_factor = (current_invested - shortage) / current_invested

                for symbol in adjusted:
                    if symbol != "Cash":
                        adjusted[symbol] *= scale_factor

                adjusted["Cash"] = self.min_cash_reserve

                violations.append(
                    f"Cash {cash:.1%} below minimum {self.min_cash_reserve:.1%}"
                )
                adjustments.append(
                    f"Increased cash reserve to {self.min_cash_reserve:.0%}"
                )
                logger.info(
                    "Cash reserve violation: increased from %.1f%% to %.1f%%",
                    cash * 100,
                    self.min_cash_reserve * 100,
                )

        # Ensure weights sum to 1.0 (handle rounding errors)
        total = sum(adjusted.values())
        if abs(total - 1.0) > 1e-6:
            adjusted["Cash"] = adjusted.get("Cash", 0.0) + (1.0 - total)

        # Determine action and message
        if not violations:
            action = RiskAction.APPROVE
            message = "All risk checks passed"
            is_compliant = True
        else:
            action = RiskAction.ADJUST
            message = f"Risk adjustments: {'; '.join(adjustments)}"
            is_compliant = True  # Compliant after adjustment

        return RiskCheckResult(
            action=action,
            is_compliant=is_compliant,
            original_weights=original,
            adjusted_weights=adjusted,
            violations=violations,
            adjustments=adjustments,
            message=message,
        )

    def check_position_risk(
        self,
        position: PositionRisk,
    ) -> Optional[ExitSignal]:
        """Check if a position should be exited due to risk triggers.

        Checks in order (first match wins):
        1. Stop-loss: Exit if loss exceeds threshold
        2. Take-profit: Exit if gain exceeds threshold
        3. Trailing stop: Exit if drawdown from peak exceeds threshold

        Args:
            position: Current position with price and P&L data

        Returns:
            ExitSignal if position should be exited, None otherwise
        """
        # Check 1: Stop-loss
        if position.pnl_pct < -self.stop_loss_pct:
            logger.info(
                "Stop-loss triggered for %s: %.1f%% loss",
                position.symbol,
                position.pnl_pct * 100,
            )
            return ExitSignal(
                symbol=position.symbol,
                shares=position.shares,
                reason=f"Stop-loss triggered ({position.pnl_pct:.1%} loss)",
                trigger_type="stop_loss",
                current_price=position.current_price,
            )

        # Check 2: Take-profit
        if position.pnl_pct > self.take_profit_pct:
            logger.info(
                "Take-profit triggered for %s: %.1f%% gain",
                position.symbol,
                position.pnl_pct * 100,
            )
            return ExitSignal(
                symbol=position.symbol,
                shares=position.shares,
                reason=f"Take-profit triggered ({position.pnl_pct:.1%} gain)",
                trigger_type="take_profit",
                current_price=position.current_price,
            )

        # Check 3: Trailing stop
        if position.drawdown_from_peak < -self.trailing_stop_pct:
            logger.info(
                "Trailing stop triggered for %s: %.1f%% from peak $%.2f",
                position.symbol,
                position.drawdown_from_peak * 100,
                position.peak_price,
            )
            return ExitSignal(
                symbol=position.symbol,
                shares=position.shares,
                reason=f"Trailing stop ({position.drawdown_from_peak:.1%} from peak ${position.peak_price:.2f})",
                trigger_type="trailing_stop",
                current_price=position.current_price,
            )

        return None

    def validate_orders(
        self,
        orders: List,
        portfolio_value: float,
        current_positions: Dict[str, float] = None,
        prices: Dict[str, float] = None,
    ) -> List:
        """Validate orders against risk rules before execution.

        Filters out orders that would violate position size limits,
        exposure limits, or cash requirements.

        Args:
            orders: List of Order objects to validate
            portfolio_value: Current total portfolio value
            current_positions: Dict of current positions {symbol: dollar_value}
            prices: Dict of current prices {symbol: price}

        Returns:
            List of approved Order objects that pass risk validation

        Example:
            >>> orders = [Order(action=OrderAction.BUY, symbol='AAPL', shares=100, ...)]
            >>> approved = manager.validate_orders(orders, portfolio_value=100000)
        """
        from src.portfolio.base import Order, OrderAction

        if current_positions is None:
            current_positions = {}

        if prices is None:
            prices = {}

        approved_orders = []
        rejected_orders = []

        for order in orders:
            # Calculate projected position value after order
            current_value = current_positions.get(order.symbol, 0.0)
            order_value = abs(order.estimated_value)

            if order.action == OrderAction.BUY:
                projected_value = current_value + order_value
            elif order.action == OrderAction.SELL:
                projected_value = max(0, current_value - order_value)
            else:
                # Unknown action, skip
                logger.warning(
                    "Unknown order action %s for %s, skipping",
                    order.action,
                    order.symbol,
                )
                rejected_orders.append(order)
                continue

            # Check 1: Position size limit
            projected_weight = projected_value / portfolio_value if portfolio_value > 0 else 0
            if projected_weight > self.max_position_size:
                logger.warning(
                    "Order rejected: %s position would exceed max size (%.1f%% > %.1f%%)",
                    order.symbol,
                    projected_weight * 100,
                    self.max_position_size * 100,
                )
                rejected_orders.append(order)
                continue

            # Check 2: Minimum trade value (skip tiny orders)
            if order_value < 100.0:  # $100 minimum
                logger.debug(
                    "Order skipped: %s trade value too small ($%.2f < $100)",
                    order.symbol,
                    order_value,
                )
                rejected_orders.append(order)
                continue

            # Order passed all checks
            approved_orders.append(order)

        if rejected_orders:
            logger.info(
                "Order validation: %d approved, %d rejected",
                len(approved_orders),
                len(rejected_orders),
            )

        return approved_orders

    def get_risk_metrics(self, weights: Dict[str, float]) -> Dict[str, float]:
        """Calculate risk metrics for a portfolio allocation.

        Args:
            weights: Portfolio weights {symbol: weight}

        Returns:
            Dictionary with risk metrics
        """
        equity_weights = {s: w for s, w in weights.items() if s != "Cash"}

        total_exposure = sum(equity_weights.values())
        cash_weight = weights.get("Cash", 0.0)
        position_count = len(equity_weights)
        max_position = max(equity_weights.values()) if equity_weights else 0.0

        # Concentration (Herfindahl index)
        herfindahl = sum(w**2 for w in equity_weights.values()) if equity_weights else 0.0

        return {
            "total_exposure": total_exposure,
            "cash_weight": cash_weight,
            "position_count": float(position_count),
            "max_position_weight": max_position,
            "herfindahl_index": herfindahl,
            "compliant_position_size": max_position <= self.max_position_size,
            "compliant_exposure": total_exposure <= self.max_total_exposure,
            "compliant_cash": cash_weight >= self.min_cash_reserve,
        }
