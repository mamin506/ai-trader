"""Unit tests for DynamicRiskManager.

Tests the DynamicRiskManager class for combined static validation
and dynamic position monitoring.
"""

import pytest

from src.execution.base import Position
from src.risk.dynamic_risk_manager import DynamicRiskManager


class TestDynamicRiskManagerInitialization:
    """Tests for DynamicRiskManager initialization."""

    def test_initialization_default_values(self):
        """Test initialization with default parameters."""
        manager = DynamicRiskManager()

        assert manager.max_position_size == 0.20
        assert manager.min_position_size == 0.02
        assert manager.max_total_exposure == 0.95
        assert manager.cash_buffer == 0.05
        assert manager.stop_loss_pct == 0.03
        assert manager.take_profit_pct == 0.10
        assert manager.trailing_stop_pct is None
        assert manager.daily_loss_limit == 0.02
        assert manager.max_drawdown == 0.05

    def test_initialization_custom_values(self):
        """Test initialization with custom parameters."""
        manager = DynamicRiskManager(
            max_position_size=0.25,
            stop_loss_pct=0.05,
            take_profit_pct=0.15,
            trailing_stop_pct=0.08,
            daily_loss_limit=0.03,
            max_drawdown=0.10,
            initial_portfolio_value=200000.0,
        )

        assert manager.max_position_size == 0.25
        assert manager.stop_loss_pct == 0.05
        assert manager.take_profit_pct == 0.15
        assert manager.trailing_stop_pct == 0.08
        assert manager.daily_loss_limit == 0.03
        assert manager.max_drawdown == 0.10

    def test_from_config(self):
        """Test initialization from configuration dict."""
        config = {
            "portfolio": {
                "max_position_size": 0.15,
                "min_position_size": 0.03,
                "cash_buffer": 0.10,
                "initial_capital": 150000.0,
            },
            "alpaca": {
                "risk_monitoring": {
                    "max_total_exposure": 0.90,
                    "stop_loss_pct": 0.04,
                    "take_profit_pct": 0.12,
                    "trailing_stop_pct": 0.06,
                    "daily_loss_limit": 0.025,
                    "max_drawdown": 0.08,
                }
            },
        }

        manager = DynamicRiskManager.from_config(config)

        assert manager.max_position_size == 0.15
        assert manager.min_position_size == 0.03
        assert manager.cash_buffer == 0.10
        assert manager.max_total_exposure == 0.90
        assert manager.stop_loss_pct == 0.04
        assert manager.take_profit_pct == 0.12
        assert manager.trailing_stop_pct == 0.06
        assert manager.daily_loss_limit == 0.025
        assert manager.max_drawdown == 0.08


class TestDynamicRiskManagerPreTradeValidation:
    """Tests for pre-trade validation (static checks)."""

    def test_validate_weights_compliant(self):
        """Test validating compliant weights."""
        manager = DynamicRiskManager(max_position_size=0.20)
        weights = {"AAPL": 0.15, "MSFT": 0.10, "Cash": 0.75}

        result = manager.validate_weights(weights)

        assert result.is_compliant
        assert result.adjusted_weights == weights

    def test_validate_weights_oversized_position(self):
        """Test validating weights with oversized position."""
        manager = DynamicRiskManager(max_position_size=0.20)
        weights = {"AAPL": 0.30, "MSFT": 0.10, "Cash": 0.60}

        result = manager.validate_weights(weights)

        # Should auto-adjust AAPL down to 20%
        assert result.adjusted_weights["AAPL"] <= 0.20


class TestDynamicRiskManagerPositionTracking:
    """Tests for position tracking and monitoring."""

    def test_start_position(self):
        """Test starting to track a position."""
        manager = DynamicRiskManager()
        manager.start_position("AAPL", entry_price=150.0, shares=100)

        risks = manager.get_position_risks()
        assert len(risks) == 1
        assert risks[0].symbol == "AAPL"
        assert risks[0].entry_price == 150.0

    def test_close_position(self):
        """Test closing a tracked position."""
        manager = DynamicRiskManager()
        manager.start_position("AAPL", entry_price=150.0, shares=100)
        manager.close_position("AAPL")

        risks = manager.get_position_risks()
        assert len(risks) == 0

    def test_update_prices(self):
        """Test updating prices for tracked positions."""
        manager = DynamicRiskManager()
        manager.start_position("AAPL", entry_price=150.0, shares=100)
        manager.update_prices({"AAPL": 155.0})

        risks = manager.get_position_risks()
        assert risks[0].current_price == 155.0

    def test_check_all_positions_stop_loss(self):
        """Test detecting stop-loss trigger."""
        manager = DynamicRiskManager(stop_loss_pct=0.05)
        manager.start_position("AAPL", entry_price=100.0, shares=100)
        manager.update_prices({"AAPL": 94.0})  # -6% loss

        exit_signals = manager.check_all_positions()

        assert len(exit_signals) == 1
        assert exit_signals[0].symbol == "AAPL"
        assert exit_signals[0].trigger_type == "stop_loss"

    def test_check_all_positions_take_profit(self):
        """Test detecting take-profit trigger."""
        manager = DynamicRiskManager(take_profit_pct=0.10)
        manager.start_position("AAPL", entry_price=100.0, shares=100)
        manager.update_prices({"AAPL": 112.0})  # +12% gain

        exit_signals = manager.check_all_positions()

        assert len(exit_signals) == 1
        assert exit_signals[0].symbol == "AAPL"
        assert exit_signals[0].trigger_type == "take_profit"

    def test_check_all_positions_multiple_triggers(self):
        """Test detecting multiple position triggers."""
        manager = DynamicRiskManager(stop_loss_pct=0.05, take_profit_pct=0.10)
        manager.start_position("AAPL", entry_price=100.0, shares=100)
        manager.start_position("MSFT", entry_price=200.0, shares=50)
        manager.start_position("GOOGL", entry_price=150.0, shares=75)

        # AAPL hits stop-loss, MSFT hits take-profit, GOOGL is safe
        manager.update_prices({"AAPL": 94.0, "MSFT": 222.0, "GOOGL": 155.0})

        exit_signals = manager.check_all_positions()

        assert len(exit_signals) == 2
        symbols = {signal.symbol for signal in exit_signals}
        assert symbols == {"AAPL", "MSFT"}


class TestDynamicRiskManagerPortfolioMonitoring:
    """Tests for portfolio-level monitoring."""

    def test_update_portfolio_value(self):
        """Test updating portfolio value."""
        manager = DynamicRiskManager(initial_portfolio_value=100000.0)
        manager.update_portfolio_value(105000.0)

        metrics = manager.get_portfolio_metrics()
        assert metrics["portfolio_value"] == 105000.0

    def test_reset_daily_tracking(self):
        """Test resetting daily tracking."""
        manager = DynamicRiskManager(initial_portfolio_value=100000.0)
        manager.update_portfolio_value(105000.0)
        manager.reset_daily_tracking()

        metrics = manager.get_portfolio_metrics()
        assert metrics["daily_start_value"] == 105000.0

    def test_check_circuit_breaker_daily_loss(self):
        """Test circuit breaker on daily loss limit."""
        manager = DynamicRiskManager(
            initial_portfolio_value=100000.0,
            daily_loss_limit=0.02,
        )
        manager.reset_daily_tracking()
        manager.update_portfolio_value(97500.0)  # -2.5% daily loss

        triggered = manager.check_circuit_breaker()

        assert triggered
        assert manager.is_circuit_breaker_active()
        assert "daily loss" in manager.get_circuit_breaker_reason().lower()

    def test_check_circuit_breaker_max_drawdown(self):
        """Test circuit breaker on max drawdown."""
        manager = DynamicRiskManager(
            initial_portfolio_value=100000.0,
            max_drawdown=0.05,
        )
        manager.update_portfolio_value(110000.0)  # New peak
        manager.update_portfolio_value(104000.0)  # -5.45% from peak

        triggered = manager.check_circuit_breaker()

        assert triggered
        assert manager.is_circuit_breaker_active()
        assert "drawdown" in manager.get_circuit_breaker_reason().lower()

    def test_check_circuit_breaker_no_trigger(self):
        """Test circuit breaker doesn't trigger within limits."""
        manager = DynamicRiskManager(
            initial_portfolio_value=100000.0,
            daily_loss_limit=0.02,
            max_drawdown=0.05,
        )
        manager.reset_daily_tracking()
        manager.update_portfolio_value(98500.0)  # -1.5% (within limit)

        triggered = manager.check_circuit_breaker()

        assert not triggered
        assert not manager.is_circuit_breaker_active()

    def test_get_portfolio_metrics(self):
        """Test getting comprehensive portfolio metrics."""
        manager = DynamicRiskManager(initial_portfolio_value=100000.0)
        manager.reset_daily_tracking()
        manager.update_portfolio_value(102000.0)

        metrics = manager.get_portfolio_metrics()

        assert "portfolio_value" in metrics
        assert "daily_pnl_pct" in metrics
        assert "drawdown_from_peak" in metrics
        assert metrics["portfolio_value"] == 102000.0
        assert metrics["daily_pnl_pct"] == pytest.approx(0.02)


class TestDynamicRiskManagerPositionSync:
    """Tests for position synchronization with broker."""

    def test_sync_positions_add_new(self):
        """Test syncing adds new positions."""
        manager = DynamicRiskManager()

        positions = [
            Position(
                symbol="AAPL",
                shares=100,
                avg_cost=150.0,
                market_value=15500.0,
            ),
            Position(
                symbol="MSFT",
                shares=50,
                avg_cost=300.0,
                market_value=15250.0,
            ),
        ]

        manager.sync_positions(positions)

        risks = manager.get_position_risks()
        assert len(risks) == 2
        symbols = {risk.symbol for risk in risks}
        assert symbols == {"AAPL", "MSFT"}

    def test_sync_positions_remove_closed(self):
        """Test syncing removes closed positions."""
        manager = DynamicRiskManager()
        manager.start_position("AAPL", entry_price=150.0, shares=100)
        manager.start_position("MSFT", entry_price=300.0, shares=50)

        # Only AAPL position remains
        positions = [
            Position(
                symbol="AAPL",
                shares=100,
                avg_cost=150.0,
                market_value=15500.0,
            ),
        ]

        manager.sync_positions(positions)

        risks = manager.get_position_risks()
        assert len(risks) == 1
        assert risks[0].symbol == "AAPL"

    def test_sync_positions_no_duplicates(self):
        """Test syncing doesn't duplicate existing positions."""
        manager = DynamicRiskManager()
        manager.start_position("AAPL", entry_price=150.0, shares=100)

        positions = [
            Position(
                symbol="AAPL",
                shares=100,
                avg_cost=150.0,
                market_value=15500.0,
            ),
        ]

        manager.sync_positions(positions)

        risks = manager.get_position_risks()
        assert len(risks) == 1


class TestDynamicRiskManagerSummary:
    """Tests for risk summary reporting."""

    def test_get_summary(self):
        """Test getting comprehensive risk summary."""
        manager = DynamicRiskManager(
            initial_portfolio_value=100000.0,
            stop_loss_pct=0.05,
            take_profit_pct=0.15,
        )
        manager.start_position("AAPL", entry_price=150.0, shares=100)
        manager.start_position("MSFT", entry_price=300.0, shares=50)
        manager.update_portfolio_value(102000.0)

        summary = manager.get_summary()

        assert summary["positions_tracked"] == 2
        assert summary["portfolio_value"] == 102000.0
        assert not summary["circuit_breaker_active"]
        assert summary["circuit_breaker_reason"] is None
        assert "thresholds" in summary
        assert summary["thresholds"]["stop_loss_pct"] == 0.05
        assert summary["thresholds"]["take_profit_pct"] == 0.15

    def test_get_summary_with_circuit_breaker(self):
        """Test summary includes circuit breaker status."""
        manager = DynamicRiskManager(
            initial_portfolio_value=100000.0,
            daily_loss_limit=0.02,
        )
        manager.reset_daily_tracking()
        manager.update_portfolio_value(97000.0)  # -3% daily loss
        manager.check_circuit_breaker()

        summary = manager.get_summary()

        assert summary["circuit_breaker_active"]
        assert summary["circuit_breaker_reason"] is not None
        assert "daily loss" in summary["circuit_breaker_reason"].lower()


class TestDynamicRiskManagerIntegration:
    """Integration tests combining multiple features."""

    def test_full_workflow(self):
        """Test complete risk management workflow."""
        manager = DynamicRiskManager(
            initial_portfolio_value=100000.0,
            max_position_size=0.20,
            stop_loss_pct=0.05,
            take_profit_pct=0.10,
            daily_loss_limit=0.02,
        )

        # Pre-trade validation
        weights = {"AAPL": 0.15, "MSFT": 0.10, "Cash": 0.75}
        result = manager.validate_weights(weights)
        assert result.is_compliant

        # Start tracking positions
        manager.start_position("AAPL", entry_price=150.0, shares=100)
        manager.start_position("MSFT", entry_price=300.0, shares=33)

        # Initialize daily tracking
        manager.reset_daily_tracking()

        # Update prices (AAPL gains +10%, MSFT drops -3%)
        manager.update_prices({"AAPL": 165.0, "MSFT": 291.0})
        manager.update_portfolio_value(101950.0)

        # Check for position exits
        exit_signals = manager.check_all_positions()
        assert len(exit_signals) == 1  # Only AAPL hits take-profit at +10%
        assert exit_signals[0].symbol == "AAPL"

        # Check circuit breaker
        triggered = manager.check_circuit_breaker()
        assert not triggered  # Within daily loss limit

        # Get summary
        summary = manager.get_summary()
        assert summary["positions_tracked"] == 2
        assert not summary["circuit_breaker_active"]

    def test_circuit_breaker_halts_trading(self):
        """Test circuit breaker detection in realistic scenario."""
        manager = DynamicRiskManager(
            initial_portfolio_value=100000.0,
            daily_loss_limit=0.02,
            max_drawdown=0.05,
        )

        manager.reset_daily_tracking()

        # Market crashes, portfolio drops 3%
        manager.update_portfolio_value(97000.0)

        # Check circuit breaker
        triggered = manager.check_circuit_breaker()

        assert triggered
        assert manager.is_circuit_breaker_active()

        # Trading should be halted
        summary = manager.get_summary()
        assert summary["circuit_breaker_active"]
