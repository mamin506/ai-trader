"""Unit tests for ExecutionAPI."""

from datetime import datetime

import pytest

from src.api.execution_api import ExecutionAPI
from src.portfolio.base import Order, OrderAction


class TestExecutionAPIInit:
    """Test cases for ExecutionAPI initialization."""

    def test_default_init(self) -> None:
        """Test API with default configuration."""
        api = ExecutionAPI()

        account = api.get_account_info()
        assert account["cash"] == 100000.0
        assert account["portfolio_value"] == 100000.0

    def test_custom_init(self) -> None:
        """Test API with custom configuration."""
        api = ExecutionAPI(
            initial_cash=50000.0,
            slippage_pct=0.002,
            commission_per_share=0.01,
            commission_min=1.0,
        )

        account = api.get_account_info()
        assert account["cash"] == 50000.0

    def test_invalid_initial_cash(self) -> None:
        """Test validation of initial_cash."""
        with pytest.raises(ValueError, match="initial_cash must be positive"):
            ExecutionAPI(initial_cash=0)


class TestBuyAndSell:
    """Test cases for buy and sell operations."""

    @pytest.fixture
    def api(self) -> ExecutionAPI:
        """Create API with test configuration."""
        api = ExecutionAPI(initial_cash=100000.0, slippage_pct=0.0)
        api.set_prices({"AAPL": 150.0, "MSFT": 350.0})
        return api

    def test_buy_order(self, api: ExecutionAPI) -> None:
        """Test successful buy order."""
        result = api.buy("AAPL", 100)

        assert result["status"] == "filled"
        assert result["symbol"] == "AAPL"
        assert result["action"] == "BUY"
        assert result["filled_qty"] == 100
        assert result["filled_price"] == 150.0

    def test_sell_order(self, api: ExecutionAPI) -> None:
        """Test successful sell order."""
        # First buy
        api.buy("AAPL", 100)

        # Then sell
        result = api.sell("AAPL", 50)

        assert result["status"] == "filled"
        assert result["action"] == "SELL"
        assert result["filled_qty"] == 50

    def test_buy_rejected_insufficient_funds(self, api: ExecutionAPI) -> None:
        """Test buy order rejected when insufficient funds."""
        result = api.buy("AAPL", 1000)  # Would cost $150,000

        assert result["status"] == "rejected"
        assert "Insufficient funds" in result["rejected_reason"]

    def test_sell_rejected_no_position(self, api: ExecutionAPI) -> None:
        """Test sell order rejected when no position."""
        result = api.sell("AAPL", 100)

        assert result["status"] == "rejected"
        assert "Insufficient shares" in result["rejected_reason"]

    def test_buy_rejected_no_price(self, api: ExecutionAPI) -> None:
        """Test buy order rejected when no price available."""
        result = api.buy("UNKNOWN", 100)

        assert result["status"] == "rejected"
        assert "No price available" in result["rejected_reason"]

    def test_buy_auto_estimate_value(self, api: ExecutionAPI) -> None:
        """Test buy with auto-calculated estimated value."""
        result = api.buy("AAPL", 100)
        assert result["status"] == "filled"

    def test_sell_auto_estimate_value(self, api: ExecutionAPI) -> None:
        """Test sell with auto-calculated estimated value."""
        api.buy("AAPL", 100)
        result = api.sell("AAPL", 50)
        assert result["status"] == "filled"


class TestExecuteOrders:
    """Test cases for execute_orders method."""

    @pytest.fixture
    def api(self) -> ExecutionAPI:
        """Create API with test configuration."""
        api = ExecutionAPI(initial_cash=100000.0, slippage_pct=0.0)
        api.set_prices({"AAPL": 150.0, "MSFT": 350.0})
        return api

    def test_execute_multiple_orders(self, api: ExecutionAPI) -> None:
        """Test executing multiple orders."""
        orders = [
            Order(action=OrderAction.BUY, symbol="AAPL", shares=50, estimated_value=7500.0),
            Order(action=OrderAction.BUY, symbol="MSFT", shares=20, estimated_value=7000.0),
        ]

        results = api.execute_orders(orders)

        assert len(results) == 2
        assert all(r["status"] == "filled" for r in results)


class TestPositions:
    """Test cases for position management."""

    @pytest.fixture
    def api(self) -> ExecutionAPI:
        """Create API with test configuration."""
        api = ExecutionAPI(initial_cash=100000.0, slippage_pct=0.0)
        api.set_prices({"AAPL": 150.0, "MSFT": 350.0})
        return api

    def test_get_position(self, api: ExecutionAPI) -> None:
        """Test getting a specific position."""
        api.buy("AAPL", 100)

        pos = api.get_position("AAPL")

        assert pos is not None
        assert pos["symbol"] == "AAPL"
        assert pos["shares"] == 100
        assert pos["avg_cost"] == 150.0

    def test_get_position_none(self, api: ExecutionAPI) -> None:
        """Test getting non-existent position."""
        pos = api.get_position("AAPL")
        assert pos is None

    def test_get_all_positions(self, api: ExecutionAPI) -> None:
        """Test getting all positions."""
        api.buy("AAPL", 100)
        api.buy("MSFT", 50)

        positions = api.get_all_positions()

        assert len(positions) == 2
        assert "AAPL" in positions
        assert "MSFT" in positions

    def test_position_market_value(self, api: ExecutionAPI) -> None:
        """Test position market value updates with price."""
        api.buy("AAPL", 100)  # Buy at $150

        # Price goes up
        api.set_prices({"AAPL": 160.0})

        pos = api.get_position("AAPL")
        assert pos["market_value"] == 16000.0  # 100 * 160
        assert pos["unrealized_pnl"] == 1000.0  # 16000 - 15000


class TestAccountInfo:
    """Test cases for account information."""

    @pytest.fixture
    def api(self) -> ExecutionAPI:
        """Create API with test configuration."""
        api = ExecutionAPI(initial_cash=100000.0, slippage_pct=0.0)
        api.set_prices({"AAPL": 150.0})
        return api

    def test_get_account_info(self, api: ExecutionAPI) -> None:
        """Test getting account info."""
        account = api.get_account_info()

        assert account["cash"] == 100000.0
        assert account["portfolio_value"] == 100000.0
        assert account["positions_value"] == 0.0

    def test_account_after_buy(self, api: ExecutionAPI) -> None:
        """Test account info after buying."""
        api.buy("AAPL", 100)

        account = api.get_account_info()

        assert account["cash"] == 85000.0  # 100000 - 15000
        assert account["positions_value"] == 15000.0
        assert account["portfolio_value"] == 100000.0

    def test_cash_property(self, api: ExecutionAPI) -> None:
        """Test cash property."""
        assert api.cash == 100000.0

        api.buy("AAPL", 100)
        assert api.cash == 85000.0

    def test_portfolio_value_property(self, api: ExecutionAPI) -> None:
        """Test portfolio_value property."""
        assert api.portfolio_value == 100000.0

        api.buy("AAPL", 100)
        assert api.portfolio_value == 100000.0


class TestFills:
    """Test cases for fill tracking."""

    @pytest.fixture
    def api(self) -> ExecutionAPI:
        """Create API with test configuration."""
        api = ExecutionAPI(initial_cash=100000.0, slippage_pct=0.0)
        api.set_prices({"AAPL": 150.0})
        return api

    def test_get_fills(self, api: ExecutionAPI) -> None:
        """Test getting fills."""
        api.buy("AAPL", 100)

        fills = api.get_fills()

        assert len(fills) == 1
        assert fills[0]["symbol"] == "AAPL"
        assert fills[0]["shares"] == 100
        assert fills[0]["price"] == 150.0
        assert fills[0]["value"] == 15000.0


class TestPerformance:
    """Test cases for performance tracking."""

    @pytest.fixture
    def api(self) -> ExecutionAPI:
        """Create API with test configuration."""
        api = ExecutionAPI(initial_cash=100000.0, slippage_pct=0.0)
        api.set_prices({"AAPL": 100.0})
        return api

    def test_get_performance_summary(self, api: ExecutionAPI) -> None:
        """Test getting performance summary."""
        api.buy("AAPL", 100)  # Buy at $100
        api.set_prices({"AAPL": 110.0})  # Price goes up

        summary = api.get_performance_summary()

        assert summary["initial_cash"] == 100000.0
        assert summary["final_value"] == 101000.0  # 90000 cash + 11000 position
        assert summary["total_return"] == 0.01
        assert summary["num_trades"] == 1

    def test_format_performance_summary(self, api: ExecutionAPI) -> None:
        """Test formatted performance summary."""
        api.buy("AAPL", 100)

        output = api.format_performance_summary()

        assert "PERFORMANCE SUMMARY" in output
        assert "Initial Cash" in output
        assert "Total Return" in output


class TestPortfolioSummary:
    """Test cases for portfolio summary."""

    @pytest.fixture
    def api(self) -> ExecutionAPI:
        """Create API with test configuration."""
        api = ExecutionAPI(initial_cash=100000.0, slippage_pct=0.0)
        api.set_prices({"AAPL": 150.0, "MSFT": 350.0})
        return api

    def test_get_portfolio_summary_no_positions(self, api: ExecutionAPI) -> None:
        """Test portfolio summary with no positions."""
        output = api.get_portfolio_summary()

        assert "PORTFOLIO SUMMARY" in output
        assert "No positions" in output

    def test_get_portfolio_summary_with_positions(self, api: ExecutionAPI) -> None:
        """Test portfolio summary with positions."""
        api.buy("AAPL", 100)
        api.buy("MSFT", 50)

        output = api.get_portfolio_summary()

        assert "PORTFOLIO SUMMARY" in output
        assert "POSITIONS" in output
        assert "AAPL" in output
        assert "MSFT" in output


class TestTimestamp:
    """Test cases for timestamp handling."""

    def test_set_timestamp(self) -> None:
        """Test setting simulation timestamp."""
        api = ExecutionAPI(initial_cash=100000.0)
        api.set_prices({"AAPL": 150.0})

        test_time = datetime(2024, 6, 15, 10, 30, 0)
        api.set_timestamp(test_time)

        api.buy("AAPL", 100)
        fills = api.get_fills()

        assert fills[0]["timestamp"] == test_time.isoformat()


class TestReset:
    """Test cases for reset functionality."""

    def test_reset(self) -> None:
        """Test resetting to initial state."""
        api = ExecutionAPI(initial_cash=100000.0, slippage_pct=0.0)
        api.set_prices({"AAPL": 150.0})

        # Execute some trades
        api.buy("AAPL", 100)
        assert api.cash < 100000.0
        assert len(api.get_all_positions()) > 0

        # Reset
        api.reset()

        # Verify initial state
        assert api.cash == 100000.0
        assert len(api.get_all_positions()) == 0
        assert len(api.get_fills()) == 0
