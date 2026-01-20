"""Unit tests for BasicRiskManager."""

import pytest

from src.risk.base import PositionRisk, RiskAction
from src.risk.basic_risk_manager import BasicRiskManager


class TestBasicRiskManagerConfig:
    """Test cases for BasicRiskManager configuration."""

    def test_default_config(self) -> None:
        """Test manager with default configuration."""
        manager = BasicRiskManager()

        assert manager.max_position_size == 0.20
        assert manager.max_total_exposure == 0.90
        assert manager.min_cash_reserve == 0.05
        assert manager.stop_loss_pct == 0.08
        assert manager.take_profit_pct == 0.25
        assert manager.trailing_stop_pct == 0.05

    def test_custom_config(self) -> None:
        """Test manager with custom configuration."""
        config = {
            "max_position_size": 0.25,
            "max_total_exposure": 0.80,
            "min_cash_reserve": 0.10,
            "stop_loss_pct": 0.10,
            "take_profit_pct": 0.30,
            "trailing_stop_pct": 0.07,
        }
        manager = BasicRiskManager(config)

        assert manager.max_position_size == 0.25
        assert manager.max_total_exposure == 0.80
        assert manager.min_cash_reserve == 0.10

    def test_invalid_max_position_size_zero(self) -> None:
        """Test config validation for zero max_position_size."""
        with pytest.raises(ValueError, match="max_position_size must be in"):
            BasicRiskManager({"max_position_size": 0})

    def test_invalid_max_position_size_above_one(self) -> None:
        """Test config validation for max_position_size > 1."""
        with pytest.raises(ValueError, match="max_position_size must be in"):
            BasicRiskManager({"max_position_size": 1.5})

    def test_invalid_max_exposure_zero(self) -> None:
        """Test config validation for zero max_total_exposure."""
        with pytest.raises(ValueError, match="max_total_exposure must be in"):
            BasicRiskManager({"max_total_exposure": 0})

    def test_invalid_min_cash_negative(self) -> None:
        """Test config validation for negative min_cash_reserve."""
        with pytest.raises(ValueError, match="min_cash_reserve must be in"):
            BasicRiskManager({"min_cash_reserve": -0.1})

    def test_invalid_min_cash_one(self) -> None:
        """Test config validation for min_cash_reserve = 1."""
        with pytest.raises(ValueError, match="min_cash_reserve must be in"):
            BasicRiskManager({"min_cash_reserve": 1.0})

    def test_invalid_conflicting_exposure_cash(self) -> None:
        """Test config validation for conflicting exposure and cash."""
        # If exposure=90% and min_cash=15%, total would exceed 100%
        with pytest.raises(ValueError, match="cannot exceed 1.0"):
            BasicRiskManager({"max_total_exposure": 0.90, "min_cash_reserve": 0.15})


class TestValidateWeights:
    """Test cases for validate_weights method."""

    @pytest.fixture
    def manager(self) -> BasicRiskManager:
        """Create manager with test configuration."""
        return BasicRiskManager(
            {
                "max_position_size": 0.20,
                "max_total_exposure": 0.90,
                "min_cash_reserve": 0.05,
            }
        )

    def test_compliant_weights_approved(self, manager: BasicRiskManager) -> None:
        """Test compliant weights are approved without changes."""
        weights = {"AAPL": 0.15, "MSFT": 0.15, "Cash": 0.70}

        result = manager.validate_weights(weights)

        assert result.action == RiskAction.APPROVE
        assert result.is_compliant is True
        assert result.adjusted_weights == weights
        assert result.violations == []
        assert "passed" in result.message.lower()

    def test_position_size_violation_adjusted(self, manager: BasicRiskManager) -> None:
        """Test position size violation is auto-adjusted."""
        weights = {"AAPL": 0.30, "MSFT": 0.15, "Cash": 0.55}

        result = manager.validate_weights(weights)

        assert result.action == RiskAction.ADJUST
        assert result.is_compliant is True
        # AAPL should be capped at 20%
        assert result.adjusted_weights["AAPL"] == 0.20
        # Excess (10%) goes to Cash
        assert result.adjusted_weights["Cash"] == 0.65
        assert len(result.violations) == 1
        assert "AAPL" in result.violations[0]

    def test_multiple_position_violations(self, manager: BasicRiskManager) -> None:
        """Test multiple position size violations are all adjusted."""
        weights = {"AAPL": 0.35, "MSFT": 0.30, "GOOGL": 0.25, "Cash": 0.10}

        result = manager.validate_weights(weights)

        assert result.action == RiskAction.ADJUST
        # All positions should be capped at 20%
        assert result.adjusted_weights["AAPL"] == 0.20
        assert result.adjusted_weights["MSFT"] == 0.20
        assert result.adjusted_weights["GOOGL"] == 0.20
        # Excess goes to cash (use approximate comparison for float)
        assert abs(result.adjusted_weights["Cash"] - 0.40) < 0.001

    def test_exposure_violation_adjusted(self, manager: BasicRiskManager) -> None:
        """Test total exposure violation is scaled down."""
        # 95% exposure exceeds 90% limit
        weights = {"AAPL": 0.20, "MSFT": 0.20, "GOOGL": 0.20, "AMZN": 0.20, "NVDA": 0.15, "Cash": 0.05}

        result = manager.validate_weights(weights)

        assert result.action == RiskAction.ADJUST
        # Total exposure should be scaled to 90%
        total_equity = sum(w for s, w in result.adjusted_weights.items() if s != "Cash")
        assert abs(total_equity - 0.90) < 0.001

    def test_cash_reserve_violation_adjusted(self, manager: BasicRiskManager) -> None:
        """Test cash reserve violation increases cash."""
        # Only 2% cash, below 5% minimum
        weights = {"AAPL": 0.20, "MSFT": 0.20, "GOOGL": 0.20, "AMZN": 0.20, "NVDA": 0.18, "Cash": 0.02}

        result = manager.validate_weights(weights)

        assert result.action == RiskAction.ADJUST
        # Cash should be at least 5%
        assert result.adjusted_weights["Cash"] >= 0.05

    def test_weights_sum_to_one(self, manager: BasicRiskManager) -> None:
        """Test adjusted weights always sum to 1.0."""
        test_cases = [
            {"AAPL": 0.50, "Cash": 0.50},  # Position violation
            {"AAPL": 0.18, "MSFT": 0.18, "GOOGL": 0.18, "AMZN": 0.18, "NVDA": 0.18, "Cash": 0.10},  # Exposure
            {"AAPL": 0.20, "MSFT": 0.78, "Cash": 0.02},  # Multiple violations
        ]

        for weights in test_cases:
            result = manager.validate_weights(weights)
            total = sum(result.adjusted_weights.values())
            assert abs(total - 1.0) < 0.001, f"Weights don't sum to 1: {result.adjusted_weights}"

    def test_empty_portfolio_all_cash(self, manager: BasicRiskManager) -> None:
        """Test empty portfolio (all cash) is valid."""
        weights = {"Cash": 1.0}

        result = manager.validate_weights(weights)

        assert result.action == RiskAction.APPROVE
        assert result.adjusted_weights == {"Cash": 1.0}

    def test_preserves_original_weights(self, manager: BasicRiskManager) -> None:
        """Test original weights are preserved in result."""
        original = {"AAPL": 0.30, "Cash": 0.70}

        result = manager.validate_weights(original)

        assert result.original_weights == original
        # Original should not be modified
        assert original["AAPL"] == 0.30


class TestCheckPositionRisk:
    """Test cases for check_position_risk method."""

    @pytest.fixture
    def manager(self) -> BasicRiskManager:
        """Create manager with test configuration."""
        return BasicRiskManager(
            {
                "stop_loss_pct": 0.08,
                "take_profit_pct": 0.25,
                "trailing_stop_pct": 0.05,
            }
        )

    def test_no_exit_normal_position(self, manager: BasicRiskManager) -> None:
        """Test no exit signal for normal position."""
        position = PositionRisk(
            symbol="AAPL",
            entry_price=150.0,
            current_price=155.0,  # +3.3% gain
            shares=100,
            pnl_pct=0.033,
        )

        result = manager.check_position_risk(position)

        assert result is None

    def test_stop_loss_triggered(self, manager: BasicRiskManager) -> None:
        """Test stop-loss exit signal when loss exceeds threshold."""
        position = PositionRisk(
            symbol="AAPL",
            entry_price=150.0,
            current_price=135.0,  # -10% loss
            shares=100,
            pnl_pct=-0.10,
        )

        result = manager.check_position_risk(position)

        assert result is not None
        assert result.symbol == "AAPL"
        assert result.shares == 100
        assert result.trigger_type == "stop_loss"
        assert "Stop-loss" in result.reason

    def test_stop_loss_exactly_at_threshold(self, manager: BasicRiskManager) -> None:
        """Test no exit when loss is exactly at threshold."""
        position = PositionRisk(
            symbol="AAPL",
            entry_price=100.0,
            current_price=92.0,  # Exactly -8%
            shares=100,
            pnl_pct=-0.08,
            peak_price=100.0,  # Peak same as entry, so no trailing stop trigger
        )
        # Manually set drawdown to match peak
        position.drawdown_from_peak = (92.0 - 100.0) / 100.0  # -8%

        result = manager.check_position_risk(position)

        # At -8%, stop_loss threshold is also -8%, but check is < not <=
        # However trailing stop at -8% from peak (threshold 5%) will trigger
        # So this should trigger trailing stop
        assert result is not None
        assert result.trigger_type == "trailing_stop"

    def test_take_profit_triggered(self, manager: BasicRiskManager) -> None:
        """Test take-profit exit signal when gain exceeds threshold."""
        position = PositionRisk(
            symbol="AAPL",
            entry_price=100.0,
            current_price=130.0,  # +30% gain
            shares=100,
            pnl_pct=0.30,
        )

        result = manager.check_position_risk(position)

        assert result is not None
        assert result.trigger_type == "take_profit"
        assert "Take-profit" in result.reason

    def test_trailing_stop_triggered(self, manager: BasicRiskManager) -> None:
        """Test trailing stop exit when drawdown from peak exceeds threshold."""
        position = PositionRisk(
            symbol="AAPL",
            entry_price=100.0,
            current_price=108.0,  # Still profitable from entry
            shares=100,
            pnl_pct=0.08,
            peak_price=120.0,  # Was at $120, now at $108 = -10% from peak
        )
        # Recalculate drawdown
        position.drawdown_from_peak = (108.0 - 120.0) / 120.0  # -10%

        result = manager.check_position_risk(position)

        assert result is not None
        assert result.trigger_type == "trailing_stop"
        assert "Trailing" in result.reason

    def test_stop_loss_priority_over_trailing(self, manager: BasicRiskManager) -> None:
        """Test stop-loss takes priority when multiple triggers."""
        # Position is down 10% from entry AND 15% from peak
        position = PositionRisk(
            symbol="AAPL",
            entry_price=100.0,
            current_price=90.0,
            shares=100,
            pnl_pct=-0.10,  # Stop-loss trigger
            peak_price=105.0,
        )
        position.drawdown_from_peak = (90.0 - 105.0) / 105.0  # Also trailing trigger

        result = manager.check_position_risk(position)

        # Should be stop-loss (first check)
        assert result is not None
        assert result.trigger_type == "stop_loss"


class TestGetRiskMetrics:
    """Test cases for get_risk_metrics method."""

    @pytest.fixture
    def manager(self) -> BasicRiskManager:
        """Create manager with test configuration."""
        return BasicRiskManager(
            {
                "max_position_size": 0.20,
                "max_total_exposure": 0.90,
                "min_cash_reserve": 0.05,
            }
        )

    def test_metrics_calculation(self, manager: BasicRiskManager) -> None:
        """Test risk metrics are calculated correctly."""
        weights = {"AAPL": 0.20, "MSFT": 0.15, "GOOGL": 0.10, "Cash": 0.55}

        metrics = manager.get_risk_metrics(weights)

        assert metrics["total_exposure"] == 0.45
        assert metrics["cash_weight"] == 0.55
        assert metrics["position_count"] == 3
        assert metrics["max_position_weight"] == 0.20
        assert metrics["compliant_position_size"] is True
        assert metrics["compliant_exposure"] is True
        assert metrics["compliant_cash"] is True

    def test_metrics_non_compliant(self, manager: BasicRiskManager) -> None:
        """Test metrics show non-compliance."""
        weights = {"AAPL": 0.30, "Cash": 0.70}  # Exceeds position limit

        metrics = manager.get_risk_metrics(weights)

        assert metrics["max_position_weight"] == 0.30
        assert metrics["compliant_position_size"] is False

    def test_metrics_all_cash(self, manager: BasicRiskManager) -> None:
        """Test metrics for all-cash portfolio."""
        weights = {"Cash": 1.0}

        metrics = manager.get_risk_metrics(weights)

        assert metrics["total_exposure"] == 0.0
        assert metrics["cash_weight"] == 1.0
        assert metrics["position_count"] == 0
        assert metrics["max_position_weight"] == 0.0
        assert metrics["herfindahl_index"] == 0.0


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_no_cash_key_in_weights(self) -> None:
        """Test handling weights without Cash key."""
        manager = BasicRiskManager()
        weights = {"AAPL": 0.20, "MSFT": 0.15}  # No Cash key, sum = 0.35

        result = manager.validate_weights(weights)

        # Should add Cash to make sum = 1.0
        assert "Cash" in result.adjusted_weights
        total = sum(result.adjusted_weights.values())
        assert abs(total - 1.0) < 0.001

    def test_rounding_errors_handled(self) -> None:
        """Test rounding errors are corrected."""
        manager = BasicRiskManager()
        # Weights that might cause floating point issues
        weights = {"AAPL": 0.1, "MSFT": 0.1, "GOOGL": 0.1, "Cash": 0.7}

        result = manager.validate_weights(weights)

        total = sum(result.adjusted_weights.values())
        assert abs(total - 1.0) < 0.001

    def test_very_small_weights(self) -> None:
        """Test handling very small position weights."""
        manager = BasicRiskManager()
        weights = {"AAPL": 0.001, "Cash": 0.999}

        result = manager.validate_weights(weights)

        assert result.action == RiskAction.APPROVE
        # Small position should be preserved

    def test_position_exactly_at_limit(self) -> None:
        """Test position exactly at size limit is not adjusted."""
        manager = BasicRiskManager({"max_position_size": 0.20})
        weights = {"AAPL": 0.20, "Cash": 0.80}

        result = manager.validate_weights(weights)

        assert result.action == RiskAction.APPROVE
        assert result.adjusted_weights["AAPL"] == 0.20
