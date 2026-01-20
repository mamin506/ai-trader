"""Unit tests for Execution base classes and data structures."""

from datetime import datetime

import pytest

from src.execution.base import (
    AccountInfo,
    ExecutionOrder,
    Fill,
    OrderExecutor,
    OrderStatus,
    OrderType,
    Position,
    TimeInForce,
)
from src.portfolio.base import Order, OrderAction


class TestOrderStatus:
    """Test cases for OrderStatus enum."""

    def test_status_values(self) -> None:
        """Test OrderStatus enum values."""
        assert OrderStatus.PENDING.value == "pending"
        assert OrderStatus.SUBMITTED.value == "submitted"
        assert OrderStatus.PARTIALLY_FILLED.value == "partially_filled"
        assert OrderStatus.FILLED.value == "filled"
        assert OrderStatus.REJECTED.value == "rejected"
        assert OrderStatus.CANCELLED.value == "cancelled"
        assert OrderStatus.EXPIRED.value == "expired"


class TestOrderType:
    """Test cases for OrderType enum."""

    def test_order_type_values(self) -> None:
        """Test OrderType enum values."""
        assert OrderType.MARKET.value == "market"
        assert OrderType.LIMIT.value == "limit"
        assert OrderType.STOP.value == "stop"
        assert OrderType.STOP_LIMIT.value == "stop_limit"


class TestTimeInForce:
    """Test cases for TimeInForce enum."""

    def test_time_in_force_values(self) -> None:
        """Test TimeInForce enum values."""
        assert TimeInForce.DAY.value == "day"
        assert TimeInForce.GTC.value == "gtc"
        assert TimeInForce.IOC.value == "ioc"
        assert TimeInForce.FOK.value == "fok"


class TestExecutionOrder:
    """Test cases for ExecutionOrder dataclass."""

    @pytest.fixture
    def sample_order(self) -> Order:
        """Create sample Order."""
        return Order(
            action=OrderAction.BUY,
            symbol="AAPL",
            shares=100,
            estimated_value=15000.0,
        )

    def test_execution_order_creation(self, sample_order: Order) -> None:
        """Test creating an execution order."""
        exec_order = ExecutionOrder(
            order_id="ABC123",
            order=sample_order,
            order_type=OrderType.MARKET,
            status=OrderStatus.PENDING,
        )

        assert exec_order.order_id == "ABC123"
        assert exec_order.order == sample_order
        assert exec_order.order_type == OrderType.MARKET
        assert exec_order.status == OrderStatus.PENDING
        assert exec_order.filled_qty == 0
        assert exec_order.filled_avg_price == 0.0

    def test_execution_order_is_complete(self, sample_order: Order) -> None:
        """Test is_complete property for terminal states."""
        exec_order = ExecutionOrder(order_id="ABC123", order=sample_order)

        # Pending is not complete
        exec_order.status = OrderStatus.PENDING
        assert not exec_order.is_complete

        # Submitted is not complete
        exec_order.status = OrderStatus.SUBMITTED
        assert not exec_order.is_complete

        # Filled is complete
        exec_order.status = OrderStatus.FILLED
        assert exec_order.is_complete

        # Rejected is complete
        exec_order.status = OrderStatus.REJECTED
        assert exec_order.is_complete

        # Cancelled is complete
        exec_order.status = OrderStatus.CANCELLED
        assert exec_order.is_complete

    def test_execution_order_remaining_qty(self, sample_order: Order) -> None:
        """Test remaining_qty calculation."""
        exec_order = ExecutionOrder(
            order_id="ABC123",
            order=sample_order,
            filled_qty=40,
        )

        assert exec_order.remaining_qty == 60  # 100 - 40

    def test_execution_order_fill_ratio(self, sample_order: Order) -> None:
        """Test fill_ratio calculation."""
        exec_order = ExecutionOrder(
            order_id="ABC123",
            order=sample_order,
            filled_qty=50,
        )

        assert exec_order.fill_ratio == 0.5  # 50/100


class TestFill:
    """Test cases for Fill dataclass."""

    def test_fill_creation(self) -> None:
        """Test creating a fill."""
        fill = Fill(
            order_id="ABC123",
            symbol="AAPL",
            shares=100,
            price=150.0,
            commission=1.0,
        )

        assert fill.order_id == "ABC123"
        assert fill.symbol == "AAPL"
        assert fill.shares == 100
        assert fill.price == 150.0
        assert fill.commission == 1.0
        assert isinstance(fill.timestamp, datetime)

    def test_fill_value(self) -> None:
        """Test fill value calculation."""
        fill = Fill(
            order_id="ABC123",
            symbol="AAPL",
            shares=100,
            price=150.0,
        )

        assert fill.value == 15000.0  # 100 * 150


class TestPosition:
    """Test cases for Position dataclass."""

    def test_position_creation(self) -> None:
        """Test creating a position."""
        position = Position(
            symbol="AAPL",
            shares=100,
            avg_cost=150.0,
            market_value=16000.0,
            unrealized_pnl=1000.0,
        )

        assert position.symbol == "AAPL"
        assert position.shares == 100
        assert position.avg_cost == 150.0
        assert position.market_value == 16000.0
        assert position.unrealized_pnl == 1000.0

    def test_position_cost_basis(self) -> None:
        """Test cost_basis calculation."""
        position = Position(
            symbol="AAPL",
            shares=100,
            avg_cost=150.0,
        )

        assert position.cost_basis == 15000.0  # 100 * 150


class TestAccountInfo:
    """Test cases for AccountInfo dataclass."""

    def test_account_info_creation(self) -> None:
        """Test creating account info."""
        account = AccountInfo(
            cash=50000.0,
            portfolio_value=100000.0,
            buying_power=50000.0,
            positions_value=50000.0,
        )

        assert account.cash == 50000.0
        assert account.portfolio_value == 100000.0
        assert account.buying_power == 50000.0
        assert account.positions_value == 50000.0
        assert isinstance(account.timestamp, datetime)


class ConcreteExecutor(OrderExecutor):
    """Concrete implementation for testing abstract class."""

    def __init__(self):
        self._orders = {}
        self._positions = {}

    def submit_orders(self, orders):
        results = []
        for i, order in enumerate(orders):
            exec_order = ExecutionOrder(
                order_id=f"ORDER-{i}",
                order=order,
                status=OrderStatus.FILLED,
                filled_qty=order.shares,
                filled_avg_price=150.0,
            )
            self._orders[exec_order.order_id] = exec_order
            results.append(exec_order)
        return results

    def get_order_status(self, order_ids):
        return [self._orders[oid] for oid in order_ids if oid in self._orders]

    def cancel_orders(self, order_ids):
        return {oid: oid in self._orders for oid in order_ids}

    def get_positions(self):
        return self._positions.copy()

    def get_account_info(self):
        return AccountInfo(
            cash=100000.0,
            portfolio_value=100000.0,
            buying_power=100000.0,
        )


class TestOrderExecutorInterface:
    """Test cases for OrderExecutor abstract interface."""

    def test_cannot_instantiate_abstract_class(self) -> None:
        """Test OrderExecutor cannot be instantiated directly."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            OrderExecutor()  # type: ignore

    def test_concrete_implementation_works(self) -> None:
        """Test concrete implementation can be instantiated."""
        executor = ConcreteExecutor()
        assert isinstance(executor, OrderExecutor)

    def test_submit_orders(self) -> None:
        """Test submitting orders."""
        executor = ConcreteExecutor()
        orders = [
            Order(action=OrderAction.BUY, symbol="AAPL", shares=100, estimated_value=15000.0),
        ]

        results = executor.submit_orders(orders)

        assert len(results) == 1
        assert results[0].status == OrderStatus.FILLED

    def test_get_position_convenience(self) -> None:
        """Test get_position convenience method."""
        executor = ConcreteExecutor()
        executor._positions["AAPL"] = Position(symbol="AAPL", shares=100, avg_cost=150.0)

        position = executor.get_position("AAPL")
        assert position is not None
        assert position.shares == 100

        # Non-existent position
        assert executor.get_position("MSFT") is None
