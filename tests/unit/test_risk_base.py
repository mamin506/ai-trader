"""Unit tests for Risk base classes and data structures."""

from datetime import datetime

import pytest

from src.risk.base import (
    ExitSignal,
    PositionRisk,
    RiskAction,
    RiskCheckResult,
    RiskManager,
)


class TestRiskAction:
    """Test cases for RiskAction enum."""

    def test_action_values(self) -> None:
        """Test RiskAction enum values."""
        assert RiskAction.APPROVE.value == "approve"
        assert RiskAction.ADJUST.value == "adjust"
        assert RiskAction.REJECT.value == "reject"
        assert RiskAction.REDUCE_EXPOSURE.value == "reduce_exposure"
        assert RiskAction.HALT_TRADING.value == "halt_trading"


class TestRiskCheckResult:
    """Test cases for RiskCheckResult dataclass."""

    def test_result_creation_approved(self) -> None:
        """Test creating an approved result."""
        result = RiskCheckResult(
            action=RiskAction.APPROVE,
            is_compliant=True,
            original_weights={"AAPL": 0.20, "Cash": 0.80},
            adjusted_weights={"AAPL": 0.20, "Cash": 0.80},
            message="All risk checks passed",
        )

        assert result.action == RiskAction.APPROVE
        assert result.is_compliant is True
        assert result.violations == []
        assert result.adjustments == []

    def test_result_creation_adjusted(self) -> None:
        """Test creating an adjusted result."""
        result = RiskCheckResult(
            action=RiskAction.ADJUST,
            is_compliant=True,
            original_weights={"AAPL": 0.30, "Cash": 0.70},
            adjusted_weights={"AAPL": 0.20, "Cash": 0.80},
            violations=["AAPL weight 30% exceeds limit 20%"],
            adjustments=["Capped 1 position(s) at 20%"],
            message="Risk adjustments: Capped 1 position(s) at 20%",
        )

        assert result.action == RiskAction.ADJUST
        assert result.is_compliant is True
        assert len(result.violations) == 1
        assert len(result.adjustments) == 1

    def test_result_has_timestamp(self) -> None:
        """Test result has default timestamp."""
        before = datetime.now()
        result = RiskCheckResult(
            action=RiskAction.APPROVE,
            is_compliant=True,
            original_weights={},
            adjusted_weights={},
        )
        after = datetime.now()

        assert before <= result.timestamp <= after


class TestPositionRisk:
    """Test cases for PositionRisk dataclass."""

    def test_position_creation(self) -> None:
        """Test creating a position risk."""
        position = PositionRisk(
            symbol="AAPL",
            entry_price=150.0,
            current_price=165.0,
            shares=100,
            pnl_pct=0.10,
        )

        assert position.symbol == "AAPL"
        assert position.entry_price == 150.0
        assert position.current_price == 165.0
        assert position.shares == 100

    def test_position_pnl_calculation(self) -> None:
        """Test P&L percentage is calculated."""
        position = PositionRisk(
            symbol="AAPL",
            entry_price=100.0,
            current_price=110.0,
            shares=100,
            pnl_pct=0.0,  # Will be recalculated
        )

        # P&L should be calculated in __post_init__
        assert abs(position.pnl_pct - 0.10) < 0.001

    def test_position_loss_pnl(self) -> None:
        """Test negative P&L calculation."""
        position = PositionRisk(
            symbol="AAPL",
            entry_price=100.0,
            current_price=90.0,
            shares=100,
            pnl_pct=0.0,
        )

        assert abs(position.pnl_pct - (-0.10)) < 0.001

    def test_position_peak_price_default(self) -> None:
        """Test peak price defaults to max of entry and current."""
        position = PositionRisk(
            symbol="AAPL",
            entry_price=100.0,
            current_price=110.0,
            shares=100,
            pnl_pct=0.10,
        )

        assert position.peak_price == 110.0

    def test_position_peak_price_explicit(self) -> None:
        """Test peak price can be set explicitly."""
        position = PositionRisk(
            symbol="AAPL",
            entry_price=100.0,
            current_price=105.0,
            shares=100,
            pnl_pct=0.05,
            peak_price=120.0,  # Position has fallen from peak
        )

        assert position.peak_price == 120.0

    def test_position_drawdown_calculation(self) -> None:
        """Test drawdown from peak is calculated."""
        position = PositionRisk(
            symbol="AAPL",
            entry_price=100.0,
            current_price=95.0,
            shares=100,
            pnl_pct=-0.05,
            peak_price=110.0,
        )

        # Drawdown = (95 - 110) / 110 = -13.6%
        expected_dd = (95.0 - 110.0) / 110.0
        assert abs(position.drawdown_from_peak - expected_dd) < 0.001


class TestExitSignal:
    """Test cases for ExitSignal dataclass."""

    def test_exit_signal_creation(self) -> None:
        """Test creating an exit signal."""
        signal = ExitSignal(
            symbol="AAPL",
            shares=100,
            reason="Stop-loss triggered (-10%)",
            trigger_type="stop_loss",
            current_price=135.0,
        )

        assert signal.symbol == "AAPL"
        assert signal.shares == 100
        assert signal.trigger_type == "stop_loss"
        assert "Stop-loss" in signal.reason

    def test_exit_signal_has_timestamp(self) -> None:
        """Test exit signal has default timestamp."""
        before = datetime.now()
        signal = ExitSignal(
            symbol="AAPL",
            shares=100,
            reason="Test",
            trigger_type="test",
            current_price=100.0,
        )
        after = datetime.now()

        assert before <= signal.timestamp <= after


class ConcreteRiskManager(RiskManager):
    """Concrete implementation for testing abstract class."""

    def validate_weights(self, target_weights):
        return RiskCheckResult(
            action=RiskAction.APPROVE,
            is_compliant=True,
            original_weights=target_weights,
            adjusted_weights=target_weights,
            message="Test passed",
        )

    def check_position_risk(self, position):
        # Simple test: exit if loss > 10%
        if position.pnl_pct < -0.10:
            return ExitSignal(
                symbol=position.symbol,
                shares=position.shares,
                reason="Test stop-loss",
                trigger_type="stop_loss",
                current_price=position.current_price,
            )
        return None


class TestRiskManagerInterface:
    """Test cases for RiskManager abstract interface."""

    def test_cannot_instantiate_abstract_class(self) -> None:
        """Test RiskManager cannot be instantiated directly."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            RiskManager()  # type: ignore

    def test_concrete_implementation_works(self) -> None:
        """Test concrete implementation can be instantiated."""
        manager = ConcreteRiskManager()
        assert isinstance(manager, RiskManager)

    def test_validate_and_adjust_convenience(self) -> None:
        """Test validate_and_adjust convenience method."""
        manager = ConcreteRiskManager()
        weights = {"AAPL": 0.25, "Cash": 0.75}

        result = manager.validate_and_adjust(weights)

        assert result == weights

    def test_check_positions_multiple(self) -> None:
        """Test check_positions with multiple positions."""
        manager = ConcreteRiskManager()

        positions = [
            PositionRisk(
                symbol="AAPL",
                entry_price=100.0,
                current_price=95.0,  # -5%, no exit
                shares=100,
                pnl_pct=-0.05,
            ),
            PositionRisk(
                symbol="MSFT",
                entry_price=100.0,
                current_price=85.0,  # -15%, should exit
                shares=50,
                pnl_pct=-0.15,
            ),
        ]

        exits = manager.check_positions(positions)

        assert len(exits) == 1
        assert exits[0].symbol == "MSFT"

    def test_check_positions_empty(self) -> None:
        """Test check_positions with no positions."""
        manager = ConcreteRiskManager()

        exits = manager.check_positions([])

        assert exits == []
