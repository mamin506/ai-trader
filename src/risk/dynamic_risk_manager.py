"""Dynamic risk manager with real-time position monitoring.

This module implements dynamic risk management for paper trading, combining:
- Static pre-trade validation (from BasicRiskManager)
- Real-time position monitoring (stop-loss, take-profit)
- Portfolio-level circuit breakers

Core Philosophy: "Validate before trade, monitor during trade, protect always."
"""

from typing import Dict, List, Optional

from src.execution.base import Position
from src.risk.base import (
    ExitSignal,
    PositionRisk,
    RiskAction,
    RiskCheckResult,
    RiskManager,
)
from src.risk.basic_risk_manager import BasicRiskManager
from src.risk.monitors import PortfolioMonitor, PositionMonitor


class DynamicRiskManager(RiskManager):
    """Risk manager with real-time monitoring capabilities.

    Extends BasicRiskManager with dynamic position tracking and
    intraday risk monitoring. Suitable for paper trading and live trading.

    Features:
    - Pre-trade validation (position limits, exposure limits)
    - Stop-loss monitoring (position-level)
    - Take-profit monitoring (position-level)
    - Trailing stop-loss (optional)
    - Portfolio drawdown circuit breaker
    - Daily loss limit circuit breaker

    Example:
        >>> manager = DynamicRiskManager.from_config(config)
        >>> # Pre-trade validation
        >>> weights = {'AAPL': 0.30, 'MSFT': 0.20, 'Cash': 0.50}
        >>> result = manager.validate_weights(weights)
        >>>
        >>> # Start tracking positions
        >>> manager.start_position('AAPL', entry_price=150.0, shares=100)
        >>>
        >>> # Monitor during trading day
        >>> manager.update_prices({'AAPL': 145.0})  # Price drops
        >>> exit_signals = manager.check_all_positions()
        >>> for signal in exit_signals:
        ...     print(f"Exit {signal.symbol}: {signal.reason}")
    """

    def __init__(
        self,
        max_position_size: float = 0.20,
        min_position_size: float = 0.02,
        max_total_exposure: float = 0.95,
        cash_buffer: float = 0.05,
        stop_loss_pct: float = 0.03,
        take_profit_pct: float = 0.10,
        trailing_stop_pct: Optional[float] = None,
        daily_loss_limit: float = 0.02,
        max_drawdown: float = 0.05,
        initial_portfolio_value: float = 100000.0,
    ):
        """Initialize dynamic risk manager.

        Args:
            max_position_size: Maximum weight per position (default 20%)
            min_position_size: Minimum weight per position (default 2%)
            max_total_exposure: Maximum total exposure (default 95%)
            cash_buffer: Minimum cash reserve (default 5%)
            stop_loss_pct: Stop-loss threshold per position (default 3%)
            take_profit_pct: Take-profit threshold per position (default 10%)
            trailing_stop_pct: Trailing stop threshold (optional)
            daily_loss_limit: Maximum daily loss (default 2%)
            max_drawdown: Maximum drawdown from peak (default 5%)
            initial_portfolio_value: Starting portfolio value (default $100k)
        """
        # Initialize basic risk manager for pre-trade validation
        basic_config = {
            "max_position_size": max_position_size,
            "max_total_exposure": max_total_exposure,
            "min_cash_reserve": cash_buffer,
            "stop_loss_pct": stop_loss_pct,
            "take_profit_pct": take_profit_pct,
            "trailing_stop_pct": trailing_stop_pct,
        }
        self._basic_manager = BasicRiskManager(basic_config)

        # Initialize position monitor
        self._position_monitor = PositionMonitor(
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            trailing_stop_pct=trailing_stop_pct,
        )

        # Initialize portfolio monitor
        self._portfolio_monitor = PortfolioMonitor(
            initial_value=initial_portfolio_value,
            daily_loss_limit=daily_loss_limit,
            max_drawdown=max_drawdown,
        )

        # Store thresholds for reference
        self.max_position_size = max_position_size
        self.min_position_size = min_position_size
        self.max_total_exposure = max_total_exposure
        self.cash_buffer = cash_buffer
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.trailing_stop_pct = trailing_stop_pct
        self.daily_loss_limit = daily_loss_limit
        self.max_drawdown = max_drawdown

    @classmethod
    def from_config(cls, config: Dict) -> "DynamicRiskManager":
        """Create DynamicRiskManager from configuration dict.

        Args:
            config: Configuration dictionary with keys:
                - portfolio.max_position_size
                - portfolio.min_position_size
                - portfolio.cash_buffer
                - alpaca.risk_monitoring.*
                - portfolio.initial_capital

        Returns:
            Configured DynamicRiskManager instance

        Example:
            >>> from src.utils.config import load_alpaca_config
            >>> config, _ = load_alpaca_config()
            >>> manager = DynamicRiskManager.from_config(config.to_dict())
        """
        return cls(
            max_position_size=config.get("portfolio", {}).get("max_position_size", 0.20),
            min_position_size=config.get("portfolio", {}).get("min_position_size", 0.02),
            max_total_exposure=config.get("alpaca", {})
            .get("risk_monitoring", {})
            .get("max_total_exposure", 0.95),
            cash_buffer=config.get("portfolio", {}).get("cash_buffer", 0.05),
            stop_loss_pct=config.get("alpaca", {})
            .get("risk_monitoring", {})
            .get("stop_loss_pct", 0.03),
            take_profit_pct=config.get("alpaca", {})
            .get("risk_monitoring", {})
            .get("take_profit_pct", 0.10),
            trailing_stop_pct=config.get("alpaca", {})
            .get("risk_monitoring", {})
            .get("trailing_stop_pct"),
            daily_loss_limit=config.get("alpaca", {})
            .get("risk_monitoring", {})
            .get("daily_loss_limit", 0.02),
            max_drawdown=config.get("alpaca", {})
            .get("risk_monitoring", {})
            .get("max_drawdown", 0.05),
            initial_portfolio_value=config.get("portfolio", {}).get(
                "initial_capital", 100000.0
            ),
        )

    # ========================================================================
    # Pre-Trade Validation (delegated to BasicRiskManager)
    # ========================================================================

    def validate_weights(self, target_weights: Dict[str, float]) -> RiskCheckResult:
        """Validate proposed portfolio weights against risk rules.

        Delegates to BasicRiskManager for static validation.

        Args:
            target_weights: Proposed allocation {symbol: weight}

        Returns:
            RiskCheckResult with validation outcome
        """
        return self._basic_manager.validate_weights(target_weights)

    def check_position_risk(self, position: PositionRisk) -> Optional[ExitSignal]:
        """Check if a position should be exited due to risk triggers.

        This is called by the base class check_positions() method but is
        not used directly by DynamicRiskManager. Use check_all_positions()
        instead for dynamic monitoring.

        Args:
            position: Position risk metrics

        Returns:
            ExitSignal if position should be exited
        """
        # Delegate to basic manager (which checks basic thresholds)
        return self._basic_manager.check_position_risk(position)

    # ========================================================================
    # Dynamic Position Monitoring
    # ========================================================================

    def start_position(
        self, symbol: str, entry_price: float, shares: int
    ) -> None:
        """Start tracking a new position.

        Call this when a position is opened to enable monitoring.

        Args:
            symbol: Ticker symbol
            entry_price: Price at which position was opened
            shares: Number of shares
        """
        self._position_monitor.add_position(symbol, entry_price, shares)

    def close_position(self, symbol: str) -> None:
        """Stop tracking a position (after it's closed).

        Args:
            symbol: Ticker symbol
        """
        self._position_monitor.remove_position(symbol)

    def update_prices(self, prices: Dict[str, float]) -> None:
        """Update current prices for all tracked positions.

        Call this periodically (e.g., every 5 minutes) to monitor positions.

        Args:
            prices: Dict mapping symbol -> current price
        """
        self._position_monitor.update_prices(prices)

    def check_all_positions(self) -> List[ExitSignal]:
        """Check all tracked positions for risk triggers.

        Returns:
            List of ExitSignal for positions that breached thresholds
        """
        return self._position_monitor.check_all_positions()

    def get_position_risks(self) -> List[PositionRisk]:
        """Get current risk metrics for all tracked positions.

        Returns:
            List of PositionRisk objects with current metrics
        """
        return self._position_monitor.get_position_risks()

    # ========================================================================
    # Portfolio-Level Monitoring
    # ========================================================================

    def update_portfolio_value(self, new_value: float) -> None:
        """Update total portfolio value.

        Args:
            new_value: Current portfolio value
        """
        self._portfolio_monitor.update_value(new_value)

    def reset_daily_tracking(self) -> None:
        """Reset daily tracking metrics.

        Call this at market open each day.
        """
        self._portfolio_monitor.reset_daily_start()

    def check_circuit_breaker(self) -> bool:
        """Check if portfolio-level circuit breaker should trigger.

        Evaluates both daily loss limit and maximum drawdown.

        Returns:
            True if circuit breaker triggered (halt trading)
        """
        return self._portfolio_monitor.check_circuit_breaker()

    def get_circuit_breaker_reason(self) -> Optional[str]:
        """Get reason for circuit breaker trigger.

        Returns:
            Human-readable reason if triggered, None otherwise
        """
        return self._portfolio_monitor.circuit_breaker_reason

    def is_circuit_breaker_active(self) -> bool:
        """Check if circuit breaker is currently active.

        Returns:
            True if circuit breaker triggered and trading should stop
        """
        return self._portfolio_monitor.circuit_breaker_triggered

    def get_portfolio_metrics(self) -> Dict[str, float]:
        """Get current portfolio risk metrics.

        Returns:
            Dict with portfolio value, P&L, drawdown, etc.
        """
        return self._portfolio_monitor.get_metrics()

    # ========================================================================
    # Batch Position Sync (for integration with Alpaca)
    # ========================================================================

    def sync_positions(self, positions: List[Position]) -> None:
        """Sync tracked positions with actual positions from broker.

        This reconciles the monitor's state with the actual account positions.
        Useful for initialization or recovery.

        Args:
            positions: Current positions from executor
        """
        # Get current tracked symbols
        tracked_symbols = set(self._position_monitor.positions.keys())
        actual_symbols = {pos.symbol for pos in positions}

        # Remove positions that are no longer held
        for symbol in tracked_symbols - actual_symbols:
            self.close_position(symbol)

        # Add new positions (if not already tracked)
        for position in positions:
            if position.symbol not in tracked_symbols:
                # Use avg_cost as entry price
                self.start_position(
                    symbol=position.symbol,
                    entry_price=position.avg_cost,
                    shares=position.shares,
                )

    def validate_orders(
        self,
        orders: List,
        portfolio_value: float,
        current_positions: Dict[str, float] = None,
        prices: Dict[str, float] = None,
    ) -> List:
        """Validate orders against risk rules before execution.

        Delegates to BasicRiskManager for validation logic.

        Args:
            orders: List of Order objects to validate
            portfolio_value: Current total portfolio value
            current_positions: Dict of current positions {symbol: dollar_value}
            prices: Dict of current prices {symbol: price}

        Returns:
            List of approved Order objects that pass risk validation
        """
        return self._basic_manager.validate_orders(
            orders=orders,
            portfolio_value=portfolio_value,
            current_positions=current_positions,
            prices=prices,
        )

    def get_summary(self) -> Dict:
        """Get comprehensive risk summary.

        Returns:
            Dict with position count, portfolio metrics, and circuit breaker status
        """
        position_risks = self.get_position_risks()
        portfolio_metrics = self.get_portfolio_metrics()

        return {
            "positions_tracked": len(position_risks),
            "portfolio_value": portfolio_metrics["portfolio_value"],
            "daily_pnl_pct": portfolio_metrics["daily_pnl_pct"],
            "drawdown_from_peak": portfolio_metrics["drawdown_from_peak"],
            "circuit_breaker_active": self.is_circuit_breaker_active(),
            "circuit_breaker_reason": self.get_circuit_breaker_reason(),
            "thresholds": {
                "stop_loss_pct": self.stop_loss_pct,
                "take_profit_pct": self.take_profit_pct,
                "daily_loss_limit": self.daily_loss_limit,
                "max_drawdown": self.max_drawdown,
            },
        }
