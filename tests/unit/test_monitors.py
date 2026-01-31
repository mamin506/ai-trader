"""Unit tests for position and portfolio monitors.

Tests the PositionMonitor and PortfolioMonitor classes for tracking
risk metrics and detecting threshold breaches.
"""

from datetime import datetime, timedelta

import pytest

from src.risk.monitors import (
    PortfolioMonitor,
    PortfolioState,
    PositionMonitor,
    PositionState,
)


class TestPositionState:
    """Tests for PositionState data class."""

    def test_initialization(self):
        """Test PositionState initialization."""
        entry_time = datetime.now()
        state = PositionState(
            symbol="AAPL",
            entry_price=150.0,
            entry_time=entry_time,
            current_price=150.0,
            shares=100,
        )

        assert state.symbol == "AAPL"
        assert state.entry_price == 150.0
        assert state.current_price == 150.0
        assert state.shares == 100
        assert state.peak_price == 150.0  # Auto-initialized to entry price
        assert state.peak_time == entry_time

    def test_update_price_new_peak(self):
        """Test price update creates new peak."""
        state = PositionState(
            symbol="AAPL",
            entry_price=150.0,
            entry_time=datetime.now(),
            current_price=150.0,
            shares=100,
        )

        new_time = datetime.now()
        state.update_price(155.0, new_time)

        assert state.current_price == 155.0
        assert state.peak_price == 155.0
        assert state.peak_time == new_time

    def test_update_price_no_new_peak(self):
        """Test price update doesn't change peak when price drops."""
        state = PositionState(
            symbol="AAPL",
            entry_price=150.0,
            entry_time=datetime.now(),
            current_price=155.0,
            shares=100,
            peak_price=155.0,
        )

        old_peak_time = state.peak_time
        state.update_price(145.0, datetime.now())

        assert state.current_price == 145.0
        assert state.peak_price == 155.0  # Peak unchanged
        assert state.peak_time == old_peak_time

    def test_to_position_risk(self):
        """Test conversion to PositionRisk."""
        entry_time = datetime.now() - timedelta(days=5)
        state = PositionState(
            symbol="AAPL",
            entry_price=100.0,
            entry_time=entry_time,
            current_price=110.0,
            shares=100,
            peak_price=115.0,
        )

        position_risk = state.to_position_risk()

        assert position_risk.symbol == "AAPL"
        assert position_risk.entry_price == 100.0
        assert position_risk.current_price == 110.0
        assert position_risk.shares == 100
        assert position_risk.pnl_pct == pytest.approx(0.10)  # 10% gain
        assert position_risk.peak_price == 115.0
        # Drawdown from peak: (110 - 115) / 115 = -4.35%
        assert position_risk.drawdown_from_peak == pytest.approx(-0.0435, abs=0.001)
        assert position_risk.days_held == 5


class TestPositionMonitor:
    """Tests for PositionMonitor."""

    def test_initialization(self):
        """Test PositionMonitor initialization with default thresholds."""
        monitor = PositionMonitor()

        assert monitor.stop_loss_pct == 0.03
        assert monitor.take_profit_pct == 0.10
        assert monitor.trailing_stop_pct is None
        assert len(monitor.positions) == 0

    def test_initialization_custom_thresholds(self):
        """Test PositionMonitor with custom thresholds."""
        monitor = PositionMonitor(
            stop_loss_pct=0.05,
            take_profit_pct=0.15,
            trailing_stop_pct=0.08,
        )

        assert monitor.stop_loss_pct == 0.05
        assert monitor.take_profit_pct == 0.15
        assert monitor.trailing_stop_pct == 0.08

    def test_add_position(self):
        """Test adding a position to track."""
        monitor = PositionMonitor()
        monitor.add_position("AAPL", entry_price=150.0, shares=100)

        assert "AAPL" in monitor.positions
        assert monitor.positions["AAPL"].entry_price == 150.0
        assert monitor.positions["AAPL"].shares == 100

    def test_remove_position(self):
        """Test removing a position."""
        monitor = PositionMonitor()
        monitor.add_position("AAPL", entry_price=150.0, shares=100)
        monitor.remove_position("AAPL")

        assert "AAPL" not in monitor.positions

    def test_update_prices(self):
        """Test updating prices for tracked positions."""
        monitor = PositionMonitor()
        monitor.add_position("AAPL", entry_price=150.0, shares=100)
        monitor.add_position("MSFT", entry_price=300.0, shares=50)

        monitor.update_prices({"AAPL": 155.0, "MSFT": 290.0})

        assert monitor.positions["AAPL"].current_price == 155.0
        assert monitor.positions["MSFT"].current_price == 290.0

    def test_check_position_stop_loss(self):
        """Test stop-loss detection."""
        monitor = PositionMonitor(stop_loss_pct=0.05)  # 5% stop-loss
        monitor.add_position("AAPL", entry_price=100.0, shares=100)
        monitor.update_prices({"AAPL": 94.0})  # -6% loss

        exit_signal = monitor.check_position("AAPL")

        assert exit_signal is not None
        assert exit_signal.symbol == "AAPL"
        assert exit_signal.shares == 100
        assert exit_signal.trigger_type == "stop_loss"
        assert "stop-loss" in exit_signal.reason.lower()

    def test_check_position_no_stop_loss(self):
        """Test no stop-loss when within threshold."""
        monitor = PositionMonitor(stop_loss_pct=0.05)  # 5% stop-loss
        monitor.add_position("AAPL", entry_price=100.0, shares=100)
        monitor.update_prices({"AAPL": 96.0})  # -4% loss (within threshold)

        exit_signal = monitor.check_position("AAPL")

        assert exit_signal is None

    def test_check_position_take_profit(self):
        """Test take-profit detection."""
        monitor = PositionMonitor(take_profit_pct=0.10)  # 10% take-profit
        monitor.add_position("AAPL", entry_price=100.0, shares=100)
        monitor.update_prices({"AAPL": 112.0})  # +12% gain

        exit_signal = monitor.check_position("AAPL")

        assert exit_signal is not None
        assert exit_signal.symbol == "AAPL"
        assert exit_signal.trigger_type == "take_profit"
        assert "take-profit" in exit_signal.reason.lower()

    def test_check_position_trailing_stop(self):
        """Test trailing stop-loss detection."""
        # Use high take-profit so it doesn't trigger before trailing stop
        monitor = PositionMonitor(
            trailing_stop_pct=0.05,  # 5% trailing stop
            take_profit_pct=0.50,  # 50% take-profit (very high)
        )
        monitor.add_position("AAPL", entry_price=100.0, shares=100)

        # Price rises to 120, then drops to 113
        monitor.update_prices({"AAPL": 120.0})
        monitor.update_prices({"AAPL": 113.0})  # 5.83% drop from peak

        exit_signal = monitor.check_position("AAPL")

        assert exit_signal is not None
        assert exit_signal.trigger_type == "trailing_stop"
        assert "trailing stop" in exit_signal.reason.lower()

    def test_check_all_positions(self):
        """Test checking all positions for triggers."""
        monitor = PositionMonitor(stop_loss_pct=0.05, take_profit_pct=0.10)
        monitor.add_position("AAPL", entry_price=100.0, shares=100)
        monitor.add_position("MSFT", entry_price=200.0, shares=50)
        monitor.add_position("GOOGL", entry_price=150.0, shares=75)

        # AAPL hits stop-loss, MSFT hits take-profit, GOOGL is fine
        monitor.update_prices({"AAPL": 94.0, "MSFT": 222.0, "GOOGL": 155.0})

        exit_signals = monitor.check_all_positions()

        assert len(exit_signals) == 2
        symbols = {signal.symbol for signal in exit_signals}
        assert symbols == {"AAPL", "MSFT"}

    def test_get_position_risks(self):
        """Test getting position risk metrics."""
        monitor = PositionMonitor()
        monitor.add_position("AAPL", entry_price=100.0, shares=100)
        monitor.add_position("MSFT", entry_price=200.0, shares=50)
        monitor.update_prices({"AAPL": 110.0, "MSFT": 190.0})

        risks = monitor.get_position_risks()

        assert len(risks) == 2
        symbols = {risk.symbol for risk in risks}
        assert symbols == {"AAPL", "MSFT"}


class TestPortfolioState:
    """Tests for PortfolioState data class."""

    def test_initialization(self):
        """Test PortfolioState initialization."""
        state = PortfolioState(portfolio_value=100000.0)

        assert state.portfolio_value == 100000.0
        assert state.peak_value == 100000.0
        assert state.daily_start_value == 100000.0
        assert state.peak_time is not None

    def test_update_value_new_peak(self):
        """Test updating value creates new peak."""
        state = PortfolioState(portfolio_value=100000.0)
        state.update_value(105000.0)

        assert state.portfolio_value == 105000.0
        assert state.peak_value == 105000.0

    def test_update_value_no_new_peak(self):
        """Test updating value doesn't change peak when value drops."""
        state = PortfolioState(portfolio_value=100000.0)
        state.update_value(105000.0)
        old_peak_time = state.peak_time

        state.update_value(102000.0)

        assert state.portfolio_value == 102000.0
        assert state.peak_value == 105000.0
        assert state.peak_time == old_peak_time

    def test_reset_daily_start(self):
        """Test resetting daily start value."""
        state = PortfolioState(portfolio_value=100000.0)
        state.update_value(105000.0)
        state.reset_daily_start(105000.0)

        assert state.daily_start_value == 105000.0

    def test_drawdown_from_peak(self):
        """Test drawdown calculation."""
        state = PortfolioState(portfolio_value=100000.0)
        state.update_value(110000.0)  # New peak
        state.update_value(104500.0)  # -5% from peak

        assert state.drawdown_from_peak == pytest.approx(-0.05)

    def test_daily_pnl_pct(self):
        """Test daily P&L calculation."""
        state = PortfolioState(portfolio_value=100000.0)
        state.reset_daily_start(100000.0)
        state.update_value(102000.0)  # +2% for the day

        assert state.daily_pnl_pct == pytest.approx(0.02)


class TestPortfolioMonitor:
    """Tests for PortfolioMonitor."""

    def test_initialization(self):
        """Test PortfolioMonitor initialization."""
        monitor = PortfolioMonitor(initial_value=100000.0)

        assert monitor.state.portfolio_value == 100000.0
        assert monitor.daily_loss_limit == 0.02
        assert monitor.max_drawdown == 0.05
        assert not monitor.circuit_breaker_triggered

    def test_initialization_custom_limits(self):
        """Test PortfolioMonitor with custom limits."""
        monitor = PortfolioMonitor(
            initial_value=100000.0,
            daily_loss_limit=0.03,
            max_drawdown=0.08,
        )

        assert monitor.daily_loss_limit == 0.03
        assert monitor.max_drawdown == 0.08

    def test_update_value(self):
        """Test updating portfolio value."""
        monitor = PortfolioMonitor(initial_value=100000.0)
        monitor.update_value(105000.0)

        assert monitor.state.portfolio_value == 105000.0

    def test_reset_daily_start(self):
        """Test resetting daily tracking."""
        monitor = PortfolioMonitor(initial_value=100000.0)
        monitor.update_value(102000.0)
        monitor.circuit_breaker_triggered = True
        monitor.reset_daily_start()

        assert monitor.state.daily_start_value == 102000.0
        assert not monitor.circuit_breaker_triggered

    def test_check_circuit_breaker_daily_loss(self):
        """Test circuit breaker on daily loss limit."""
        monitor = PortfolioMonitor(initial_value=100000.0, daily_loss_limit=0.02)
        monitor.reset_daily_start()
        monitor.update_value(97500.0)  # -2.5% daily loss

        triggered = monitor.check_circuit_breaker()

        assert triggered
        assert monitor.circuit_breaker_triggered
        assert "daily loss" in monitor.circuit_breaker_reason.lower()

    def test_check_circuit_breaker_max_drawdown(self):
        """Test circuit breaker on max drawdown."""
        monitor = PortfolioMonitor(initial_value=100000.0, max_drawdown=0.05)
        monitor.update_value(110000.0)  # New peak
        monitor.update_value(104000.0)  # -5.45% from peak

        triggered = monitor.check_circuit_breaker()

        assert triggered
        assert monitor.circuit_breaker_triggered
        assert "drawdown" in monitor.circuit_breaker_reason.lower()

    def test_check_circuit_breaker_no_trigger(self):
        """Test circuit breaker doesn't trigger within limits."""
        monitor = PortfolioMonitor(
            initial_value=100000.0,
            daily_loss_limit=0.02,
            max_drawdown=0.05,
        )
        monitor.reset_daily_start()
        monitor.update_value(98500.0)  # -1.5% daily loss (within limit)

        triggered = monitor.check_circuit_breaker()

        assert not triggered
        assert not monitor.circuit_breaker_triggered

    def test_get_metrics(self):
        """Test getting portfolio metrics."""
        monitor = PortfolioMonitor(initial_value=100000.0)
        monitor.reset_daily_start()
        monitor.update_value(102000.0)

        metrics = monitor.get_metrics()

        assert metrics["portfolio_value"] == 102000.0
        assert metrics["peak_value"] == 102000.0
        assert metrics["daily_start_value"] == 100000.0
        assert metrics["daily_pnl_pct"] == pytest.approx(0.02)
        assert metrics["drawdown_from_peak"] == 0.0
        assert not metrics["circuit_breaker_triggered"]
