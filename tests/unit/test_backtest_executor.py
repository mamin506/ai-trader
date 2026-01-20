"""Unit tests for BacktestExecutor."""

from datetime import datetime

import pytest

from src.execution.backtest_executor import BacktestExecutor
from src.execution.base import OrderStatus
from src.portfolio.base import Order, OrderAction


class TestBacktestExecutorConfig:
    """Test cases for BacktestExecutor configuration."""

    def test_default_config(self) -> None:
        """Test executor with default configuration."""
        executor = BacktestExecutor()

        assert executor.initial_cash == 100000.0
        assert executor.slippage_pct == 0.001
        assert executor.commission_per_share == 0.0
        assert executor.commission_min == 0.0

    def test_custom_config(self) -> None:
        """Test executor with custom configuration."""
        config = {
            "initial_cash": 50000.0,
            "slippage_pct": 0.002,
            "commission_per_share": 0.01,
            "commission_min": 1.0,
        }
        executor = BacktestExecutor(config)

        assert executor.initial_cash == 50000.0
        assert executor.slippage_pct == 0.002
        assert executor.commission_per_share == 0.01
        assert executor.commission_min == 1.0

    def test_invalid_initial_cash(self) -> None:
        """Test config validation for non-positive initial_cash."""
        with pytest.raises(ValueError, match="initial_cash must be positive"):
            BacktestExecutor({"initial_cash": 0})

    def test_invalid_slippage(self) -> None:
        """Test config validation for negative slippage."""
        with pytest.raises(ValueError, match="slippage_pct must be non-negative"):
            BacktestExecutor({"slippage_pct": -0.001})

    def test_invalid_commission(self) -> None:
        """Test config validation for negative commission."""
        with pytest.raises(ValueError, match="commission_per_share must be non-negative"):
            BacktestExecutor({"commission_per_share": -1.0})


class TestSubmitOrders:
    """Test cases for submit_orders method."""

    @pytest.fixture
    def executor(self) -> BacktestExecutor:
        """Create executor with test configuration."""
        executor = BacktestExecutor(
            {
                "initial_cash": 100000.0,
                "slippage_pct": 0.001,  # 0.1%
                "commission_per_share": 0.0,
            }
        )
        executor.set_prices({"AAPL": 150.0, "MSFT": 350.0})
        return executor

    def test_buy_order_fills(self, executor: BacktestExecutor) -> None:
        """Test buy order fills correctly."""
        orders = [
            Order(
                action=OrderAction.BUY,
                symbol="AAPL",
                shares=100,
                estimated_value=15000.0,
            )
        ]

        results = executor.submit_orders(orders)

        assert len(results) == 1
        assert results[0].status == OrderStatus.FILLED
        assert results[0].filled_qty == 100
        # Price with slippage: 150 * 1.001 = 150.15
        assert abs(results[0].filled_avg_price - 150.15) < 0.01

    def test_sell_order_fills(self, executor: BacktestExecutor) -> None:
        """Test sell order fills correctly."""
        # First buy some shares
        buy_orders = [
            Order(action=OrderAction.BUY, symbol="AAPL", shares=100, estimated_value=15000.0)
        ]
        executor.submit_orders(buy_orders)

        # Then sell
        sell_orders = [
            Order(action=OrderAction.SELL, symbol="AAPL", shares=50, estimated_value=7500.0)
        ]
        results = executor.submit_orders(sell_orders)

        assert len(results) == 1
        assert results[0].status == OrderStatus.FILLED
        assert results[0].filled_qty == 50
        # Price with slippage: 150 * 0.999 = 149.85
        assert abs(results[0].filled_avg_price - 149.85) < 0.01

    def test_order_rejected_no_price(self, executor: BacktestExecutor) -> None:
        """Test order rejected when no price available."""
        orders = [
            Order(action=OrderAction.BUY, symbol="UNKNOWN", shares=100, estimated_value=10000.0)
        ]

        results = executor.submit_orders(orders)

        assert len(results) == 1
        assert results[0].status == OrderStatus.REJECTED
        assert "No price available" in results[0].rejected_reason

    def test_order_rejected_insufficient_funds(self, executor: BacktestExecutor) -> None:
        """Test order rejected when insufficient funds."""
        # Try to buy more than we can afford
        orders = [
            Order(
                action=OrderAction.BUY,
                symbol="AAPL",
                shares=1000,  # Would cost ~$150,000
                estimated_value=150000.0,
            )
        ]

        results = executor.submit_orders(orders)

        assert len(results) == 1
        assert results[0].status == OrderStatus.REJECTED
        assert "Insufficient funds" in results[0].rejected_reason

    def test_order_rejected_insufficient_shares(self, executor: BacktestExecutor) -> None:
        """Test sell order rejected when insufficient shares."""
        orders = [
            Order(action=OrderAction.SELL, symbol="AAPL", shares=100, estimated_value=15000.0)
        ]

        results = executor.submit_orders(orders)

        assert len(results) == 1
        assert results[0].status == OrderStatus.REJECTED
        assert "Insufficient shares" in results[0].rejected_reason

    def test_multiple_orders(self, executor: BacktestExecutor) -> None:
        """Test submitting multiple orders."""
        orders = [
            Order(action=OrderAction.BUY, symbol="AAPL", shares=50, estimated_value=7500.0),
            Order(action=OrderAction.BUY, symbol="MSFT", shares=20, estimated_value=7000.0),
        ]

        results = executor.submit_orders(orders)

        assert len(results) == 2
        assert all(r.status == OrderStatus.FILLED for r in results)


class TestPositions:
    """Test cases for position management."""

    @pytest.fixture
    def executor(self) -> BacktestExecutor:
        """Create executor with test configuration."""
        executor = BacktestExecutor({"initial_cash": 100000.0, "slippage_pct": 0.0})
        executor.set_prices({"AAPL": 150.0, "MSFT": 350.0})
        return executor

    def test_position_created_on_buy(self, executor: BacktestExecutor) -> None:
        """Test position is created after buy."""
        orders = [
            Order(action=OrderAction.BUY, symbol="AAPL", shares=100, estimated_value=15000.0)
        ]
        executor.submit_orders(orders)

        positions = executor.get_positions()

        assert "AAPL" in positions
        assert positions["AAPL"].shares == 100
        assert positions["AAPL"].avg_cost == 150.0

    def test_position_updated_on_additional_buy(self, executor: BacktestExecutor) -> None:
        """Test position avg cost updates on additional buy."""
        # Buy at $150
        orders1 = [
            Order(action=OrderAction.BUY, symbol="AAPL", shares=100, estimated_value=15000.0)
        ]
        executor.submit_orders(orders1)

        # Change price and buy more at $160
        executor.set_prices({"AAPL": 160.0})
        orders2 = [
            Order(action=OrderAction.BUY, symbol="AAPL", shares=100, estimated_value=16000.0)
        ]
        executor.submit_orders(orders2)

        positions = executor.get_positions()

        assert positions["AAPL"].shares == 200
        # Avg cost: (100*150 + 100*160) / 200 = 155
        assert positions["AAPL"].avg_cost == 155.0

    def test_position_reduced_on_sell(self, executor: BacktestExecutor) -> None:
        """Test position is reduced after sell."""
        # Buy
        orders1 = [
            Order(action=OrderAction.BUY, symbol="AAPL", shares=100, estimated_value=15000.0)
        ]
        executor.submit_orders(orders1)

        # Sell half
        orders2 = [
            Order(action=OrderAction.SELL, symbol="AAPL", shares=50, estimated_value=7500.0)
        ]
        executor.submit_orders(orders2)

        positions = executor.get_positions()

        assert positions["AAPL"].shares == 50

    def test_position_removed_on_full_sell(self, executor: BacktestExecutor) -> None:
        """Test position is removed when fully sold."""
        # Buy
        orders1 = [
            Order(action=OrderAction.BUY, symbol="AAPL", shares=100, estimated_value=15000.0)
        ]
        executor.submit_orders(orders1)

        # Sell all
        orders2 = [
            Order(action=OrderAction.SELL, symbol="AAPL", shares=100, estimated_value=15000.0)
        ]
        executor.submit_orders(orders2)

        positions = executor.get_positions()

        assert "AAPL" not in positions


class TestAccountInfo:
    """Test cases for account info."""

    @pytest.fixture
    def executor(self) -> BacktestExecutor:
        """Create executor with test configuration."""
        executor = BacktestExecutor({"initial_cash": 100000.0, "slippage_pct": 0.0})
        executor.set_prices({"AAPL": 150.0})
        return executor

    def test_initial_account_info(self, executor: BacktestExecutor) -> None:
        """Test account info at start."""
        account = executor.get_account_info()

        assert account.cash == 100000.0
        assert account.portfolio_value == 100000.0
        assert account.positions_value == 0.0

    def test_account_info_after_buy(self, executor: BacktestExecutor) -> None:
        """Test account info after buying."""
        orders = [
            Order(action=OrderAction.BUY, symbol="AAPL", shares=100, estimated_value=15000.0)
        ]
        executor.submit_orders(orders)

        account = executor.get_account_info()

        # Cash reduced by purchase
        assert account.cash == 100000.0 - 15000.0
        # Positions value = 100 shares * $150
        assert account.positions_value == 15000.0
        # Total value should be same (no slippage in this test)
        assert account.portfolio_value == 100000.0


class TestSlippageAndCommission:
    """Test cases for slippage and commission."""

    def test_slippage_on_buy(self) -> None:
        """Test slippage increases buy price."""
        executor = BacktestExecutor(
            {"initial_cash": 100000.0, "slippage_pct": 0.01}  # 1% slippage
        )
        executor.set_prices({"AAPL": 100.0})

        orders = [
            Order(action=OrderAction.BUY, symbol="AAPL", shares=100, estimated_value=10000.0)
        ]
        results = executor.submit_orders(orders)

        # Should fill at 100 * 1.01 = 101
        assert abs(results[0].filled_avg_price - 101.0) < 0.001

    def test_slippage_on_sell(self) -> None:
        """Test slippage decreases sell price."""
        executor = BacktestExecutor(
            {"initial_cash": 100000.0, "slippage_pct": 0.01}  # 1% slippage
        )
        executor.set_prices({"AAPL": 100.0})

        # Buy first (at 101)
        executor.submit_orders(
            [Order(action=OrderAction.BUY, symbol="AAPL", shares=100, estimated_value=10000.0)]
        )

        # Sell (at 99)
        results = executor.submit_orders(
            [Order(action=OrderAction.SELL, symbol="AAPL", shares=100, estimated_value=10000.0)]
        )

        # Should fill at 100 * 0.99 = 99
        assert abs(results[0].filled_avg_price - 99.0) < 0.001

    def test_commission_applied(self) -> None:
        """Test commission is applied to orders."""
        executor = BacktestExecutor(
            {
                "initial_cash": 100000.0,
                "slippage_pct": 0.0,
                "commission_per_share": 0.01,  # $0.01 per share
            }
        )
        executor.set_prices({"AAPL": 100.0})

        orders = [
            Order(action=OrderAction.BUY, symbol="AAPL", shares=100, estimated_value=10000.0)
        ]
        results = executor.submit_orders(orders)

        # Commission = 100 shares * $0.01 = $1.00
        assert results[0].commission == 1.0

    def test_minimum_commission(self) -> None:
        """Test minimum commission is applied."""
        executor = BacktestExecutor(
            {
                "initial_cash": 100000.0,
                "slippage_pct": 0.0,
                "commission_per_share": 0.001,
                "commission_min": 5.0,  # Minimum $5
            }
        )
        executor.set_prices({"AAPL": 100.0})

        orders = [
            Order(action=OrderAction.BUY, symbol="AAPL", shares=10, estimated_value=1000.0)
        ]
        results = executor.submit_orders(orders)

        # Calculated = 10 * 0.001 = $0.01, but minimum is $5
        assert results[0].commission == 5.0


class TestReset:
    """Test cases for reset functionality."""

    def test_reset_restores_initial_state(self) -> None:
        """Test reset restores executor to initial state."""
        executor = BacktestExecutor({"initial_cash": 100000.0, "slippage_pct": 0.0})
        executor.set_prices({"AAPL": 150.0})

        # Execute some trades
        executor.submit_orders(
            [Order(action=OrderAction.BUY, symbol="AAPL", shares=100, estimated_value=15000.0)]
        )

        # Verify state changed
        assert executor.get_account_info().cash < 100000.0
        assert len(executor.get_positions()) > 0

        # Reset
        executor.reset()

        # Verify initial state restored
        account = executor.get_account_info()
        assert account.cash == 100000.0
        assert len(executor.get_positions()) == 0
        assert len(executor.get_fills()) == 0


class TestPerformanceSummary:
    """Test cases for performance summary."""

    def test_performance_summary(self) -> None:
        """Test getting performance summary."""
        executor = BacktestExecutor({"initial_cash": 100000.0, "slippage_pct": 0.0})
        executor.set_prices({"AAPL": 100.0})

        # Buy
        executor.submit_orders(
            [Order(action=OrderAction.BUY, symbol="AAPL", shares=100, estimated_value=10000.0)]
        )

        # Price goes up
        executor.set_prices({"AAPL": 110.0})

        summary = executor.get_performance_summary()

        assert summary["initial_cash"] == 100000.0
        # Cash = 100000 - 10000 = 90000, positions = 100 * 110 = 11000
        assert summary["final_value"] == 101000.0
        assert summary["total_return"] == 0.01  # 1% return
        assert summary["num_trades"] == 1
        assert summary["num_buys"] == 1
        assert summary["num_sells"] == 0


class TestTimestamp:
    """Test cases for timestamp handling."""

    def test_timestamp_on_fill(self) -> None:
        """Test fills have correct timestamp."""
        executor = BacktestExecutor({"initial_cash": 100000.0})
        executor.set_prices({"AAPL": 150.0})

        test_time = datetime(2024, 6, 15, 10, 30, 0)
        executor.set_timestamp(test_time)

        executor.submit_orders(
            [Order(action=OrderAction.BUY, symbol="AAPL", shares=100, estimated_value=15000.0)]
        )

        fills = executor.get_fills()
        assert fills[0].timestamp == test_time
