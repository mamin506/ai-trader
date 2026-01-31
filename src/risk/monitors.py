"""Position and portfolio monitors for real-time risk tracking.

This module provides monitoring classes for tracking position and portfolio-level
risk metrics during paper trading. These monitors track P&L, peak values, and
detect risk threshold breaches.

Core Philosophy: "Monitor continuously, act on thresholds."
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from src.execution.base import Position
from src.risk.base import ExitSignal, PositionRisk


@dataclass
class PositionState:
    """Tracks the state of a position for monitoring purposes.

    This extends the basic Position with additional tracking data needed
    for dynamic risk monitoring (peaks, entry times, etc.).

    Attributes:
        symbol: Ticker symbol
        entry_price: Price at which position was opened
        entry_time: When position was opened
        current_price: Current market price
        shares: Number of shares held
        peak_price: Highest price since entry (for trailing stop)
        peak_time: When peak price occurred
    """

    symbol: str
    entry_price: float
    entry_time: datetime
    current_price: float
    shares: int
    peak_price: float = 0.0
    peak_time: Optional[datetime] = None

    def __post_init__(self):
        """Initialize peak tracking."""
        if self.peak_price == 0.0:
            self.peak_price = self.entry_price
            self.peak_time = self.entry_time

    def update_price(self, new_price: float, timestamp: datetime) -> None:
        """Update current price and track peak.

        Args:
            new_price: New market price
            timestamp: Time of price update
        """
        self.current_price = new_price

        # Update peak if new high
        if new_price > self.peak_price:
            self.peak_price = new_price
            self.peak_time = timestamp

    def to_position_risk(self) -> PositionRisk:
        """Convert to PositionRisk for risk checking.

        Returns:
            PositionRisk object with current metrics
        """
        pnl_pct = 0.0
        if self.entry_price > 0:
            pnl_pct = (self.current_price - self.entry_price) / self.entry_price

        drawdown_from_peak = 0.0
        if self.peak_price > 0:
            drawdown_from_peak = (self.current_price - self.peak_price) / self.peak_price

        days_held = 0
        if self.entry_time:
            days_held = (datetime.now() - self.entry_time).days

        return PositionRisk(
            symbol=self.symbol,
            entry_price=self.entry_price,
            current_price=self.current_price,
            shares=self.shares,
            pnl_pct=pnl_pct,
            peak_price=self.peak_price,
            drawdown_from_peak=drawdown_from_peak,
            days_held=days_held,
        )


class PositionMonitor:
    """Monitors individual positions for risk triggers.

    Tracks position-level metrics and detects stop-loss and take-profit
    threshold breaches.

    Attributes:
        positions: Dict of symbol -> PositionState
        stop_loss_pct: Stop-loss threshold (e.g., 0.03 = 3%)
        take_profit_pct: Take-profit threshold (e.g., 0.10 = 10%)
        trailing_stop_pct: Trailing stop threshold (optional)
    """

    def __init__(
        self,
        stop_loss_pct: float = 0.03,
        take_profit_pct: float = 0.10,
        trailing_stop_pct: Optional[float] = None,
    ):
        """Initialize position monitor.

        Args:
            stop_loss_pct: Stop-loss threshold (default 3%)
            take_profit_pct: Take-profit threshold (default 10%)
            trailing_stop_pct: Trailing stop threshold (optional)
        """
        self.positions: Dict[str, PositionState] = {}
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.trailing_stop_pct = trailing_stop_pct

    def add_position(
        self,
        symbol: str,
        entry_price: float,
        shares: int,
        entry_time: Optional[datetime] = None,
    ) -> None:
        """Start tracking a new position.

        Args:
            symbol: Ticker symbol
            entry_price: Price at which position was opened
            shares: Number of shares
            entry_time: When position was opened (default: now)
        """
        if entry_time is None:
            entry_time = datetime.now()

        self.positions[symbol] = PositionState(
            symbol=symbol,
            entry_price=entry_price,
            entry_time=entry_time,
            current_price=entry_price,
            shares=shares,
        )

    def remove_position(self, symbol: str) -> None:
        """Stop tracking a position (after it's closed).

        Args:
            symbol: Ticker symbol to remove
        """
        if symbol in self.positions:
            del self.positions[symbol]

    def update_prices(self, prices: Dict[str, float]) -> None:
        """Update current prices for all tracked positions.

        Args:
            prices: Dict mapping symbol -> current price
        """
        timestamp = datetime.now()
        for symbol, price in prices.items():
            if symbol in self.positions:
                self.positions[symbol].update_price(price, timestamp)

    def check_position(self, symbol: str) -> Optional[ExitSignal]:
        """Check a specific position for risk triggers.

        Args:
            symbol: Ticker symbol to check

        Returns:
            ExitSignal if threshold breached, None otherwise
        """
        if symbol not in self.positions:
            return None

        state = self.positions[symbol]
        position_risk = state.to_position_risk()

        # Check stop-loss
        if position_risk.pnl_pct <= -self.stop_loss_pct:
            return ExitSignal(
                symbol=symbol,
                shares=state.shares,
                reason=f"Stop-loss triggered: {position_risk.pnl_pct:.2%} loss "
                f"(threshold: {-self.stop_loss_pct:.2%})",
                trigger_type="stop_loss",
                current_price=state.current_price,
            )

        # Check take-profit
        if position_risk.pnl_pct >= self.take_profit_pct:
            return ExitSignal(
                symbol=symbol,
                shares=state.shares,
                reason=f"Take-profit triggered: {position_risk.pnl_pct:.2%} gain "
                f"(threshold: {self.take_profit_pct:.2%})",
                trigger_type="take_profit",
                current_price=state.current_price,
            )

        # Check trailing stop (if enabled)
        if self.trailing_stop_pct is not None:
            if position_risk.drawdown_from_peak <= -self.trailing_stop_pct:
                return ExitSignal(
                    symbol=symbol,
                    shares=state.shares,
                    reason=f"Trailing stop triggered: {position_risk.drawdown_from_peak:.2%} "
                    f"from peak ${state.peak_price:.2f} "
                    f"(threshold: {-self.trailing_stop_pct:.2%})",
                    trigger_type="trailing_stop",
                    current_price=state.current_price,
                )

        return None

    def check_all_positions(self) -> List[ExitSignal]:
        """Check all tracked positions for risk triggers.

        Returns:
            List of ExitSignal for positions that breached thresholds
        """
        exit_signals = []
        for symbol in list(self.positions.keys()):
            signal = self.check_position(symbol)
            if signal:
                exit_signals.append(signal)
        return exit_signals

    def get_position_risks(self) -> List[PositionRisk]:
        """Get current risk metrics for all positions.

        Returns:
            List of PositionRisk objects
        """
        return [state.to_position_risk() for state in self.positions.values()]


@dataclass
class PortfolioState:
    """Tracks portfolio-level state for risk monitoring.

    Attributes:
        portfolio_value: Current total portfolio value
        peak_value: Peak portfolio value (for drawdown)
        daily_start_value: Portfolio value at market open
        peak_time: When peak value occurred
    """

    portfolio_value: float
    peak_value: float = 0.0
    daily_start_value: float = 0.0
    peak_time: Optional[datetime] = None

    def __post_init__(self):
        """Initialize peak tracking."""
        if self.peak_value == 0.0:
            self.peak_value = self.portfolio_value
            self.peak_time = datetime.now()
        if self.daily_start_value == 0.0:
            self.daily_start_value = self.portfolio_value

    def update_value(self, new_value: float) -> None:
        """Update portfolio value and track peak.

        Args:
            new_value: New portfolio value
        """
        self.portfolio_value = new_value

        # Update peak if new high
        if new_value > self.peak_value:
            self.peak_value = new_value
            self.peak_time = datetime.now()

    def reset_daily_start(self, start_value: float) -> None:
        """Reset daily start value (call at market open).

        Args:
            start_value: Portfolio value at market open
        """
        self.daily_start_value = start_value

    @property
    def drawdown_from_peak(self) -> float:
        """Calculate drawdown from peak value.

        Returns:
            Drawdown as negative percentage (e.g., -0.05 = -5%)
        """
        if self.peak_value == 0:
            return 0.0
        return (self.portfolio_value - self.peak_value) / self.peak_value

    @property
    def daily_pnl_pct(self) -> float:
        """Calculate daily P&L percentage.

        Returns:
            Daily P&L as percentage (e.g., -0.02 = -2%)
        """
        if self.daily_start_value == 0:
            return 0.0
        return (self.portfolio_value - self.daily_start_value) / self.daily_start_value


class PortfolioMonitor:
    """Monitors portfolio-level risk metrics.

    Tracks aggregate portfolio metrics and detects portfolio-level
    circuit breaker conditions.

    Attributes:
        state: Current portfolio state
        daily_loss_limit: Maximum daily loss (e.g., 0.02 = 2%)
        max_drawdown: Maximum drawdown from peak (e.g., 0.05 = 5%)
        circuit_breaker_triggered: Whether circuit breaker is active
    """

    def __init__(
        self,
        initial_value: float,
        daily_loss_limit: float = 0.02,
        max_drawdown: float = 0.05,
    ):
        """Initialize portfolio monitor.

        Args:
            initial_value: Starting portfolio value
            daily_loss_limit: Maximum daily loss (default 2%)
            max_drawdown: Maximum drawdown from peak (default 5%)
        """
        self.state = PortfolioState(portfolio_value=initial_value)
        self.daily_loss_limit = daily_loss_limit
        self.max_drawdown = max_drawdown
        self.circuit_breaker_triggered = False
        self.circuit_breaker_reason: Optional[str] = None

    def update_value(self, new_value: float) -> None:
        """Update portfolio value.

        Args:
            new_value: New portfolio value
        """
        self.state.update_value(new_value)

    def reset_daily_start(self) -> None:
        """Reset daily tracking (call at market open)."""
        self.state.reset_daily_start(self.state.portfolio_value)
        # Reset circuit breaker daily
        self.circuit_breaker_triggered = False
        self.circuit_breaker_reason = None

    def check_circuit_breaker(self) -> bool:
        """Check if circuit breaker should trigger.

        Evaluates both daily loss limit and maximum drawdown.

        Returns:
            True if circuit breaker triggered, False otherwise
        """
        # Check daily loss limit
        if self.state.daily_pnl_pct <= -self.daily_loss_limit:
            self.circuit_breaker_triggered = True
            self.circuit_breaker_reason = (
                f"Daily loss limit exceeded: {self.state.daily_pnl_pct:.2%} "
                f"(limit: {-self.daily_loss_limit:.2%})"
            )
            return True

        # Check maximum drawdown
        if self.state.drawdown_from_peak <= -self.max_drawdown:
            self.circuit_breaker_triggered = True
            self.circuit_breaker_reason = (
                f"Maximum drawdown exceeded: {self.state.drawdown_from_peak:.2%} "
                f"from peak ${self.state.peak_value:.2f} "
                f"(limit: {-self.max_drawdown:.2%})"
            )
            return True

        return False

    def get_metrics(self) -> Dict[str, float]:
        """Get current portfolio risk metrics.

        Returns:
            Dict with portfolio value, P&L, drawdown, etc.
        """
        return {
            "portfolio_value": self.state.portfolio_value,
            "peak_value": self.state.peak_value,
            "daily_start_value": self.state.daily_start_value,
            "daily_pnl_pct": self.state.daily_pnl_pct,
            "drawdown_from_peak": self.state.drawdown_from_peak,
            "circuit_breaker_triggered": self.circuit_breaker_triggered,
        }
