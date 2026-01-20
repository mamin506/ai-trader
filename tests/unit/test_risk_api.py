"""Unit tests for RiskAPI."""

import pytest
import pandas as pd

from src.api.risk_api import RiskAPI
from src.risk.basic_risk_manager import BasicRiskManager


class TestRiskAPIInit:
    """Test cases for RiskAPI initialization."""

    def test_default_initialization(self) -> None:
        """Test RiskAPI with default configuration."""
        api = RiskAPI()
        assert isinstance(api.risk_manager, BasicRiskManager)

    def test_custom_risk_manager(self) -> None:
        """Test RiskAPI with custom risk manager."""
        custom_manager = BasicRiskManager({"max_position_size": 0.25})
        api = RiskAPI(risk_manager=custom_manager)
        assert api.risk_manager.max_position_size == 0.25


class TestValidateAllocation:
    """Test cases for validate_allocation method."""

    @pytest.fixture
    def api(self) -> RiskAPI:
        """Create RiskAPI instance."""
        return RiskAPI()

    def test_compliant_allocation(self, api: RiskAPI) -> None:
        """Test compliant allocation returns valid result."""
        weights = {"AAPL": 0.15, "MSFT": 0.15, "Cash": 0.70}

        result = api.validate_allocation(weights)

        assert result["valid"] is True
        assert result["adjusted"] is False
        assert result["final_weights"] == weights
        assert result["violations"] == []

    def test_non_compliant_allocation(self, api: RiskAPI) -> None:
        """Test non-compliant allocation is adjusted."""
        weights = {"AAPL": 0.30, "Cash": 0.70}  # AAPL exceeds 20% limit

        result = api.validate_allocation(weights)

        assert result["valid"] is True  # Valid after adjustment
        assert result["adjusted"] is True
        assert result["final_weights"]["AAPL"] == 0.20
        assert abs(result["final_weights"]["Cash"] - 0.80) < 0.001
        assert len(result["violations"]) > 0

    def test_result_contains_all_keys(self, api: RiskAPI) -> None:
        """Test result dictionary contains all expected keys."""
        weights = {"AAPL": 0.20, "Cash": 0.80}

        result = api.validate_allocation(weights)

        assert "valid" in result
        assert "adjusted" in result
        assert "original_weights" in result
        assert "final_weights" in result
        assert "violations" in result
        assert "adjustments" in result
        assert "message" in result


class TestValidateAndGetWeights:
    """Test cases for validate_and_get_weights method."""

    @pytest.fixture
    def api(self) -> RiskAPI:
        """Create RiskAPI instance."""
        return RiskAPI()

    def test_returns_adjusted_weights(self, api: RiskAPI) -> None:
        """Test method returns adjusted weights directly."""
        weights = {"AAPL": 0.30, "Cash": 0.70}

        result = api.validate_and_get_weights(weights)

        assert result["AAPL"] == 0.20
        assert abs(result["Cash"] - 0.80) < 0.001

    def test_returns_original_if_compliant(self, api: RiskAPI) -> None:
        """Test method returns original weights if compliant."""
        weights = {"AAPL": 0.15, "Cash": 0.85}

        result = api.validate_and_get_weights(weights)

        assert result == weights


class TestCheckPositionRisks:
    """Test cases for check_position_risks method."""

    @pytest.fixture
    def api(self) -> RiskAPI:
        """Create RiskAPI with test configuration."""
        manager = BasicRiskManager(
            {
                "stop_loss_pct": 0.08,
                "take_profit_pct": 0.25,
                "trailing_stop_pct": 0.05,
            }
        )
        return RiskAPI(risk_manager=manager)

    def test_no_exits_for_healthy_positions(self, api: RiskAPI) -> None:
        """Test no exit signals for healthy positions."""
        positions = [
            {"symbol": "AAPL", "entry_price": 150, "current_price": 155, "shares": 100},
            {"symbol": "MSFT", "entry_price": 350, "current_price": 360, "shares": 50},
        ]

        exits = api.check_position_risks(positions)

        assert exits == []

    def test_stop_loss_exit(self, api: RiskAPI) -> None:
        """Test stop-loss triggers exit signal."""
        positions = [
            {"symbol": "AAPL", "entry_price": 150, "current_price": 135, "shares": 100},  # -10%
        ]

        exits = api.check_position_risks(positions)

        assert len(exits) == 1
        assert exits[0]["symbol"] == "AAPL"
        assert exits[0]["trigger_type"] == "stop_loss"

    def test_take_profit_exit(self, api: RiskAPI) -> None:
        """Test take-profit triggers exit signal."""
        positions = [
            {"symbol": "AAPL", "entry_price": 100, "current_price": 130, "shares": 100},  # +30%
        ]

        exits = api.check_position_risks(positions)

        assert len(exits) == 1
        assert exits[0]["trigger_type"] == "take_profit"

    def test_exit_signal_format(self, api: RiskAPI) -> None:
        """Test exit signal dictionary format."""
        positions = [
            {"symbol": "AAPL", "entry_price": 150, "current_price": 130, "shares": 100},
        ]

        exits = api.check_position_risks(positions)

        assert "symbol" in exits[0]
        assert "shares" in exits[0]
        assert "reason" in exits[0]
        assert "trigger_type" in exits[0]
        assert "current_price" in exits[0]


class TestGetRiskMetrics:
    """Test cases for get_risk_metrics method."""

    @pytest.fixture
    def api(self) -> RiskAPI:
        """Create RiskAPI instance."""
        return RiskAPI()

    def test_metrics_calculation(self, api: RiskAPI) -> None:
        """Test risk metrics are calculated correctly."""
        weights = {"AAPL": 0.20, "MSFT": 0.15, "Cash": 0.65}

        metrics = api.get_risk_metrics(weights)

        assert metrics["total_exposure"] == 0.35
        assert metrics["cash_weight"] == 0.65
        assert metrics["position_count"] == 2

    def test_metrics_all_cash(self, api: RiskAPI) -> None:
        """Test metrics for all-cash portfolio."""
        weights = {"Cash": 1.0}

        metrics = api.get_risk_metrics(weights)

        assert metrics["total_exposure"] == 0.0
        assert metrics["cash_weight"] == 1.0


class TestIsCompliant:
    """Test cases for is_compliant method."""

    @pytest.fixture
    def api(self) -> RiskAPI:
        """Create RiskAPI instance."""
        return RiskAPI()

    def test_compliant_returns_true(self, api: RiskAPI) -> None:
        """Test compliant weights return True."""
        weights = {"AAPL": 0.15, "Cash": 0.85}

        assert api.is_compliant(weights) is True

    def test_non_compliant_returns_false(self, api: RiskAPI) -> None:
        """Test non-compliant weights return False."""
        weights = {"AAPL": 0.30, "Cash": 0.70}  # Exceeds limit

        assert api.is_compliant(weights) is False


class TestFormatMethods:
    """Test cases for formatting methods."""

    @pytest.fixture
    def api(self) -> RiskAPI:
        """Create RiskAPI instance."""
        return RiskAPI()

    def test_format_validation_result(self, api: RiskAPI) -> None:
        """Test formatting validation result."""
        result = {
            "original_weights": {"AAPL": 0.30, "Cash": 0.70},
            "final_weights": {"AAPL": 0.20, "Cash": 0.80},
        }

        df = api.format_validation_result(result)

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2
        assert "symbol" in df.columns
        assert "original" in df.columns
        assert "final" in df.columns

    def test_format_exit_signals_with_data(self, api: RiskAPI) -> None:
        """Test formatting exit signals with data."""
        exits = [
            {
                "symbol": "AAPL",
                "shares": 100,
                "trigger_type": "stop_loss",
                "reason": "Stop-loss triggered",
            }
        ]

        df = api.format_exit_signals(exits)

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 1
        assert df.iloc[0]["symbol"] == "AAPL"

    def test_format_exit_signals_empty(self, api: RiskAPI) -> None:
        """Test formatting empty exit signals."""
        df = api.format_exit_signals([])

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0
