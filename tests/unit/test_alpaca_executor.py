"""Unit tests for AlpacaExecutor.

Tests the Alpaca order executor with mocked API responses.
"""

from datetime import datetime
from unittest.mock import Mock

import pytest

from src.execution.alpaca_executor import AlpacaExecutor
from src.execution.base import OrderStatus
from src.portfolio.base import Order, OrderAction
from src.utils.exceptions import BrokerConnectionError


@pytest.fixture
def mock_alpaca_client():
    """Create a mock AlpacaClient."""
    client = Mock()
    client.with_retry = Mock(side_effect=lambda func, *args, **kwargs: func(*args, **kwargs))
    return client


@pytest.fixture
def mock_trading_client():
    """Create a mock TradingClient."""
    return Mock()


@pytest.fixture
def alpaca_executor(mock_alpaca_client, mock_trading_client):
    """Create AlpacaExecutor with mocked client."""
    mock_alpaca_client.get_trading_client.return_value = mock_trading_client
    return AlpacaExecutor(mock_alpaca_client)


@pytest.fixture
def sample_buy_order():
    """Create a sample buy order."""
    return Order(
        action=OrderAction.BUY,
        symbol="AAPL",
        shares=100,
        estimated_value=15000.0,
        reason="Test buy",
    )


@pytest.fixture
def sample_sell_order():
    """Create a sample sell order."""
    return Order(
        action=OrderAction.SELL,
        symbol="AAPL",
        shares=50,
        estimated_value=7500.0,
        reason="Test sell",
    )


class TestAlpacaExecutorInit:
    """Test AlpacaExecutor initialization."""

    def test_init(self, mock_alpaca_client, mock_trading_client):
        """Test executor initialization."""
        mock_alpaca_client.get_trading_client.return_value = mock_trading_client
        executor = AlpacaExecutor(mock_alpaca_client)

        assert executor.client == mock_alpaca_client
        assert executor.trading_client == mock_trading_client
        mock_alpaca_client.get_trading_client.assert_called_once()


class TestAlpacaExecutorSubmitOrders:
    """Test submit_orders method."""

    def test_submit_orders_success(
        self,
        alpaca_executor,
        mock_trading_client,
        sample_buy_order,
    ):
        """Test successful order submission."""
        # Mock submitted order from Alpaca
        mock_submitted = Mock()
        mock_submitted.id = "order-123"
        mock_submitted.symbol = "AAPL"
        mock_submitted.qty = 100
        mock_submitted.side = "buy"
        mock_submitted.status = "new"
        mock_submitted.filled_qty = 0
        mock_submitted.filled_avg_price = 0.0
        mock_submitted.submitted_at = datetime(2024, 1, 1, 10, 0, 0)
        mock_submitted.filled_at = None
        mock_submitted.notional = 15000.0

        mock_trading_client.submit_order.return_value = mock_submitted

        # Submit order
        results = alpaca_executor.submit_orders([sample_buy_order])

        # Verify
        assert len(results) == 1
        result = results[0]
        assert result.order_id == "order-123"
        assert result.order == sample_buy_order
        assert result.status == OrderStatus.SUBMITTED
        assert result.filled_qty == 0

    def test_submit_orders_empty_list(self, alpaca_executor):
        """Test submitting empty order list."""
        results = alpaca_executor.submit_orders([])
        assert results == []

    def test_submit_orders_multiple(
        self,
        alpaca_executor,
        mock_trading_client,
        sample_buy_order,
        sample_sell_order,
    ):
        """Test submitting multiple orders."""
        # Mock responses
        mock_buy_order = Mock()
        mock_buy_order.id = "order-buy-123"
        mock_buy_order.symbol = "AAPL"
        mock_buy_order.qty = 100
        mock_buy_order.side = "buy"
        mock_buy_order.status = "new"
        mock_buy_order.filled_qty = 0
        mock_buy_order.filled_avg_price = 0.0
        mock_buy_order.submitted_at = datetime(2024, 1, 1, 10, 0, 0)
        mock_buy_order.filled_at = None
        mock_buy_order.notional = 15000.0

        mock_sell_order = Mock()
        mock_sell_order.id = "order-sell-456"
        mock_sell_order.symbol = "AAPL"
        mock_sell_order.qty = 50
        mock_sell_order.side = "sell"
        mock_sell_order.status = "new"
        mock_sell_order.filled_qty = 0
        mock_sell_order.filled_avg_price = 0.0
        mock_sell_order.submitted_at = datetime(2024, 1, 1, 10, 0, 0)
        mock_sell_order.filled_at = None
        mock_sell_order.notional = 7500.0

        mock_trading_client.submit_order.side_effect = [mock_buy_order, mock_sell_order]

        # Submit orders
        results = alpaca_executor.submit_orders([sample_buy_order, sample_sell_order])

        # Verify
        assert len(results) == 2
        assert results[0].order_id == "order-buy-123"
        assert results[1].order_id == "order-sell-456"

    def test_submit_orders_rejection(
        self,
        alpaca_executor,
        mock_trading_client,
        sample_buy_order,
    ):
        """Test order rejection."""
        mock_trading_client.submit_order.side_effect = Exception("Insufficient funds")

        # Submit order
        results = alpaca_executor.submit_orders([sample_buy_order])

        # Verify rejection
        assert len(results) == 1
        result = results[0]
        assert result.status == OrderStatus.REJECTED
        assert "Insufficient funds" in result.rejected_reason


class TestAlpacaExecutorGetOrderStatus:
    """Test get_order_status method."""

    def test_get_order_status_success(self, alpaca_executor, mock_trading_client):
        """Test successful order status query."""
        # Mock order from Alpaca
        mock_order = Mock()
        mock_order.id = "order-123"
        mock_order.symbol = "AAPL"
        mock_order.qty = 100
        mock_order.side = "buy"
        mock_order.status = "filled"
        mock_order.filled_qty = 100
        mock_order.filled_avg_price = 150.0
        mock_order.submitted_at = datetime(2024, 1, 1, 10, 0, 0)
        mock_order.filled_at = datetime(2024, 1, 1, 10, 5, 0)
        mock_order.notional = 15000.0

        mock_trading_client.get_order_by_id.return_value = mock_order

        # Query status
        results = alpaca_executor.get_order_status(["order-123"])

        # Verify
        assert len(results) == 1
        result = results[0]
        assert result.order_id == "order-123"
        assert result.status == OrderStatus.FILLED
        assert result.filled_qty == 100
        assert result.filled_avg_price == 150.0

    def test_get_order_status_empty_list(self, alpaca_executor):
        """Test querying empty order list."""
        results = alpaca_executor.get_order_status([])
        assert results == []

    def test_get_order_status_error(self, alpaca_executor, mock_trading_client):
        """Test order status query error."""
        mock_trading_client.get_order_by_id.side_effect = Exception("Order not found")

        # Query status (should not raise, just skip failed orders)
        results = alpaca_executor.get_order_status(["invalid-id"])

        # Should return empty list (error logged but not raised)
        assert results == []


class TestAlpacaExecutorCancelOrders:
    """Test cancel_orders method."""

    def test_cancel_orders_success(self, alpaca_executor, mock_trading_client):
        """Test successful order cancellation."""
        mock_trading_client.cancel_order_by_id.return_value = None

        results = alpaca_executor.cancel_orders(["order-123"])

        assert results == {"order-123": True}
        mock_trading_client.cancel_order_by_id.assert_called_once_with("order-123")

    def test_cancel_orders_failure(self, alpaca_executor, mock_trading_client):
        """Test order cancellation failure."""
        mock_trading_client.cancel_order_by_id.side_effect = Exception("Cannot cancel")

        results = alpaca_executor.cancel_orders(["order-123"])

        assert results == {"order-123": False}

    def test_cancel_orders_empty_list(self, alpaca_executor):
        """Test canceling empty order list."""
        results = alpaca_executor.cancel_orders([])
        assert results == {}

    def test_cancel_orders_multiple(self, alpaca_executor, mock_trading_client):
        """Test canceling multiple orders."""
        # First succeeds, second fails
        mock_trading_client.cancel_order_by_id.side_effect = [
            None,
            Exception("Cannot cancel"),
        ]

        results = alpaca_executor.cancel_orders(["order-1", "order-2"])

        assert results == {"order-1": True, "order-2": False}


class TestAlpacaExecutorGetPositions:
    """Test get_positions method."""

    def test_get_positions_success(self, alpaca_executor, mock_trading_client):
        """Test successful position fetching."""
        # Mock positions
        mock_pos1 = Mock()
        mock_pos1.symbol = "AAPL"
        mock_pos1.qty = 100
        mock_pos1.avg_entry_price = 150.0
        mock_pos1.market_value = 15500.0
        mock_pos1.unrealized_pl = 500.0

        mock_pos2 = Mock()
        mock_pos2.symbol = "MSFT"
        mock_pos2.qty = 50
        mock_pos2.avg_entry_price = 300.0
        mock_pos2.market_value = 15250.0
        mock_pos2.unrealized_pl = 250.0

        mock_trading_client.get_all_positions.return_value = [mock_pos1, mock_pos2]

        # Get positions
        positions = alpaca_executor.get_positions()

        # Verify
        assert len(positions) == 2
        assert "AAPL" in positions
        assert "MSFT" in positions

        aapl_pos = positions["AAPL"]
        assert aapl_pos.symbol == "AAPL"
        assert aapl_pos.shares == 100
        assert aapl_pos.avg_cost == 150.0
        assert aapl_pos.market_value == 15500.0
        assert aapl_pos.unrealized_pnl == 500.0

    def test_get_positions_empty(self, alpaca_executor, mock_trading_client):
        """Test when no positions exist."""
        mock_trading_client.get_all_positions.return_value = []

        positions = alpaca_executor.get_positions()

        assert positions == {}

    def test_get_positions_error(self, alpaca_executor, mock_trading_client):
        """Test position fetching error."""
        mock_trading_client.get_all_positions.side_effect = Exception("API Error")

        with pytest.raises(BrokerConnectionError, match="Failed to fetch positions"):
            alpaca_executor.get_positions()


class TestAlpacaExecutorGetAccountInfo:
    """Test get_account_info method."""

    def test_get_account_info_success(self, alpaca_executor, mock_trading_client):
        """Test successful account info fetching."""
        # Mock account
        mock_account = Mock()
        mock_account.cash = 50000.0
        mock_account.portfolio_value = 100000.0
        mock_account.buying_power = 75000.0
        mock_account.long_market_value = 50000.0

        mock_trading_client.get_account.return_value = mock_account

        # Get account info
        account_info = alpaca_executor.get_account_info()

        # Verify
        assert account_info.cash == 50000.0
        assert account_info.portfolio_value == 100000.0
        assert account_info.buying_power == 75000.0
        assert account_info.positions_value == 50000.0

    def test_get_account_info_error(self, alpaca_executor, mock_trading_client):
        """Test account info fetching error."""
        mock_trading_client.get_account.side_effect = Exception("API Error")

        with pytest.raises(BrokerConnectionError, match="Failed to fetch account info"):
            alpaca_executor.get_account_info()


class TestAlpacaExecutorGetOpenOrders:
    """Test get_open_orders method."""

    def test_get_open_orders_success(self, alpaca_executor, mock_trading_client):
        """Test successful open orders fetching."""
        # Mock open order
        mock_order = Mock()
        mock_order.id = "order-123"
        mock_order.symbol = "AAPL"
        mock_order.qty = 100
        mock_order.side = "buy"
        mock_order.status = "new"
        mock_order.filled_qty = 0
        mock_order.filled_avg_price = 0.0
        mock_order.submitted_at = datetime(2024, 1, 1, 10, 0, 0)
        mock_order.filled_at = None
        mock_order.notional = 15000.0

        mock_trading_client.get_orders.return_value = [mock_order]

        # Get open orders
        open_orders = alpaca_executor.get_open_orders()

        # Verify
        assert len(open_orders) == 1
        assert open_orders[0].order_id == "order-123"
        assert open_orders[0].status == OrderStatus.SUBMITTED

    def test_get_open_orders_empty(self, alpaca_executor, mock_trading_client):
        """Test when no open orders exist."""
        mock_trading_client.get_orders.return_value = []

        open_orders = alpaca_executor.get_open_orders()

        assert open_orders == []

    def test_get_open_orders_error(self, alpaca_executor, mock_trading_client):
        """Test open orders fetching error."""
        mock_trading_client.get_orders.side_effect = Exception("API Error")

        # Should return empty list on error (not raise)
        open_orders = alpaca_executor.get_open_orders()

        assert open_orders == []
