"""Unit tests for PortfolioAPI."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.api.portfolio_api import PortfolioAPI
from src.portfolio.base import AllocationResult, Order, OrderAction, PortfolioState
from src.portfolio.heuristic_allocator import HeuristicAllocator


class TestPortfolioAPIInit:
    """Test cases for PortfolioAPI initialization."""

    def test_default_initialization(self) -> None:
        """Test PortfolioAPI with default configuration."""
        api = PortfolioAPI()

        assert isinstance(api.allocator, HeuristicAllocator)
        assert api.data_api is not None
        assert api.strategy_api is not None

    def test_custom_allocator(self) -> None:
        """Test PortfolioAPI with custom allocator."""
        custom_allocator = HeuristicAllocator({"max_positions": 5})
        api = PortfolioAPI(allocator=custom_allocator)

        assert api.allocator.max_positions == 5


class TestShouldRebalance:
    """Test cases for should_rebalance method."""

    @pytest.fixture
    def api(self) -> PortfolioAPI:
        """Create PortfolioAPI instance."""
        return PortfolioAPI()

    def test_no_rebalance_needed(self, api: PortfolioAPI) -> None:
        """Test no rebalance when weights match."""
        current = {"AAPL": 0.25, "MSFT": 0.25, "Cash": 0.50}
        target = {"AAPL": 0.25, "MSFT": 0.25, "Cash": 0.50}

        assert not api.should_rebalance(current, target)

    def test_rebalance_needed_large_drift(self, api: PortfolioAPI) -> None:
        """Test rebalance needed when drift is large."""
        current = {"AAPL": 0.35, "MSFT": 0.15, "Cash": 0.50}
        target = {"AAPL": 0.25, "MSFT": 0.25, "Cash": 0.50}

        assert api.should_rebalance(current, target, threshold=0.05)

    def test_custom_threshold(self, api: PortfolioAPI) -> None:
        """Test custom threshold parameter."""
        current = {"AAPL": 0.30, "Cash": 0.70}
        target = {"AAPL": 0.25, "Cash": 0.75}

        # 5% drift, above 3% threshold
        assert api.should_rebalance(current, target, threshold=0.03)

        # 5% drift, below 10% threshold
        assert not api.should_rebalance(current, target, threshold=0.10)


class TestFormatOrders:
    """Test cases for format_orders method."""

    @pytest.fixture
    def api(self) -> PortfolioAPI:
        """Create PortfolioAPI instance."""
        return PortfolioAPI()

    def test_format_empty_orders(self, api: PortfolioAPI) -> None:
        """Test formatting empty order list."""
        df = api.format_orders([])

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0
        assert "action" in df.columns
        assert "symbol" in df.columns

    def test_format_orders_with_data(self, api: PortfolioAPI) -> None:
        """Test formatting orders with data."""
        orders = [
            Order(
                action=OrderAction.BUY,
                symbol="AAPL",
                shares=100,
                estimated_value=15000.0,
                reason="New position",
            ),
            Order(
                action=OrderAction.SELL,
                symbol="MSFT",
                shares=50,
                estimated_value=17500.0,
                reason="Reduce position",
            ),
        ]

        df = api.format_orders(orders)

        assert len(df) == 2
        assert df.iloc[0]["action"] == "BUY"
        assert df.iloc[0]["symbol"] == "AAPL"
        assert df.iloc[0]["shares"] == 100
        assert df.iloc[1]["action"] == "SELL"


class TestFormatWeights:
    """Test cases for format_weights method."""

    @pytest.fixture
    def api(self) -> PortfolioAPI:
        """Create PortfolioAPI instance."""
        return PortfolioAPI()

    def test_format_weights(self, api: PortfolioAPI) -> None:
        """Test formatting weights."""
        weights = {"AAPL": 0.30, "MSFT": 0.20, "Cash": 0.50}

        df = api.format_weights(weights)

        assert len(df) == 3
        # Should be sorted by weight descending
        assert df.iloc[0]["symbol"] == "Cash"
        assert df.iloc[0]["weight"] == 0.50
        assert "weight_pct" in df.columns

    def test_format_empty_weights(self, api: PortfolioAPI) -> None:
        """Test formatting empty weights."""
        df = api.format_weights({})

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0


class TestGetAllocation:
    """Test cases for get_allocation method."""

    @pytest.fixture
    def mock_strategy(self) -> MagicMock:
        """Create mock strategy."""
        strategy = MagicMock()
        strategy.validate_data.return_value = True
        return strategy

    def test_get_allocation_with_mocked_data(self, mock_strategy: MagicMock) -> None:
        """Test get_allocation with mocked dependencies."""
        # Create mocked dependencies
        mock_data_api = MagicMock()
        mock_strategy_api = MagicMock()

        # Setup mock returns
        signal_series = pd.Series(
            [0.0, 0.5, 0.8],
            index=pd.DatetimeIndex(
                ["2024-01-01", "2024-01-02", "2024-01-03"], name="date"
            ),
        )
        mock_strategy_api.get_signals.return_value = signal_series

        price_data = pd.DataFrame(
            {"close": [150.0, 151.0, 152.0]},
            index=pd.DatetimeIndex(
                ["2024-01-01", "2024-01-02", "2024-01-03"], name="date"
            ),
        )
        mock_data_api.get_daily_bars.return_value = price_data

        # Create API with mocked dependencies
        api = PortfolioAPI(
            data_api=mock_data_api,
            strategy_api=mock_strategy_api,
        )

        result = api.get_allocation(
            symbols=["AAPL"],
            strategy=mock_strategy,
            portfolio_value=100000.0,
            as_of_date="2024-01-03",
        )

        # Check result structure
        assert "signals" in result
        assert "target_weights" in result
        assert "orders" in result
        assert "metrics" in result

        # Check signals
        assert "AAPL" in result["signals"]
        assert result["signals"]["AAPL"] == 0.8  # Latest signal

    def test_get_allocation_no_signals(self, mock_strategy: MagicMock) -> None:
        """Test get_allocation when no signals are generated."""
        mock_data_api = MagicMock()
        mock_strategy_api = MagicMock()

        # Return empty signals
        mock_strategy_api.get_signals.return_value = pd.Series(dtype=float)

        api = PortfolioAPI(
            data_api=mock_data_api,
            strategy_api=mock_strategy_api,
        )

        result = api.get_allocation(
            symbols=["AAPL"],
            strategy=mock_strategy,
            portfolio_value=100000.0,
            as_of_date="2024-01-03",
        )

        # Should return 100% cash
        assert result["target_weights"] == {"Cash": 1.0}
        assert result["orders"] == []

    def test_get_allocation_with_current_positions(
        self, mock_strategy: MagicMock
    ) -> None:
        """Test get_allocation with existing positions."""
        mock_data_api = MagicMock()
        mock_strategy_api = MagicMock()

        signal_series = pd.Series(
            [0.8], index=pd.DatetimeIndex(["2024-01-03"], name="date")
        )
        mock_strategy_api.get_signals.return_value = signal_series

        price_data = pd.DataFrame(
            {"close": [150.0]},
            index=pd.DatetimeIndex(["2024-01-03"], name="date"),
        )
        mock_data_api.get_daily_bars.return_value = price_data

        api = PortfolioAPI(
            data_api=mock_data_api,
            strategy_api=mock_strategy_api,
        )

        result = api.get_allocation(
            symbols=["AAPL"],
            strategy=mock_strategy,
            portfolio_value=100000.0,
            as_of_date="2024-01-03",
            current_positions={"MSFT": 25000.0},
        )

        assert "signals" in result
        assert "target_weights" in result


class TestAnalyzeSignals:
    """Test cases for analyze_signals method."""

    def test_analyze_signals(self) -> None:
        """Test analyzing signals across multiple symbols."""
        mock_strategy_api = MagicMock()

        # Create different signal series for each symbol
        aapl_signals = pd.Series(
            [0.5, 0.8],
            index=pd.DatetimeIndex(["2024-01-01", "2024-01-02"], name="date"),
        )
        msft_signals = pd.Series(
            [0.3, 0.4],
            index=pd.DatetimeIndex(["2024-01-01", "2024-01-02"], name="date"),
        )

        mock_strategy_api.get_signals.side_effect = [aapl_signals, msft_signals]

        api = PortfolioAPI(strategy_api=mock_strategy_api)

        result = api.analyze_signals(
            symbols=["AAPL", "MSFT"],
            strategy=MagicMock(),
            start="2024-01-01",
            end="2024-01-02",
        )

        assert isinstance(result, pd.DataFrame)
        assert "AAPL" in result.columns
        assert "MSFT" in result.columns
        assert len(result) == 2

    def test_analyze_signals_empty_result(self) -> None:
        """Test analyze_signals when no signals generated."""
        mock_strategy_api = MagicMock()
        mock_strategy_api.get_signals.return_value = pd.Series(dtype=float)

        api = PortfolioAPI(strategy_api=mock_strategy_api)

        result = api.analyze_signals(
            symbols=["AAPL"],
            strategy=MagicMock(),
            start="2024-01-01",
            end="2024-01-02",
        )

        assert isinstance(result, pd.DataFrame)
        assert result.empty


class TestGetLatestSignals:
    """Test cases for get_latest_signals method."""

    def test_get_latest_signals(self) -> None:
        """Test getting latest signals for multiple symbols."""
        mock_strategy_api = MagicMock()

        aapl_signals = pd.Series(
            [0.5, 0.8],
            index=pd.DatetimeIndex(["2024-01-01", "2024-01-02"], name="date"),
        )
        msft_signals = pd.Series(
            [0.3, -0.2],
            index=pd.DatetimeIndex(["2024-01-01", "2024-01-02"], name="date"),
        )

        mock_strategy_api.get_signals.side_effect = [aapl_signals, msft_signals]

        api = PortfolioAPI(strategy_api=mock_strategy_api)

        result = api.get_latest_signals(
            symbols=["AAPL", "MSFT"],
            strategy=MagicMock(),
            as_of_date="2024-01-02",
        )

        assert result["AAPL"] == 0.8  # Latest
        assert result["MSFT"] == -0.2  # Latest

    def test_get_latest_signals_datetime_input(self) -> None:
        """Test get_latest_signals with datetime input."""
        mock_strategy_api = MagicMock()

        signals = pd.Series(
            [0.5], index=pd.DatetimeIndex(["2024-01-02"], name="date")
        )
        mock_strategy_api.get_signals.return_value = signals

        api = PortfolioAPI(strategy_api=mock_strategy_api)

        result = api.get_latest_signals(
            symbols=["AAPL"],
            strategy=MagicMock(),
            as_of_date=datetime(2024, 1, 2),
        )

        assert "AAPL" in result
