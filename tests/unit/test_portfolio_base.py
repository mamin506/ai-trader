"""Unit tests for Portfolio base classes and data structures."""

from datetime import datetime

import pytest

from src.portfolio.base import (
    AllocationResult,
    Order,
    OrderAction,
    PortfolioManager,
    PortfolioState,
)


class TestOrder:
    """Test cases for Order dataclass."""

    def test_order_creation_buy(self) -> None:
        """Test creating a buy order."""
        order = Order(
            action=OrderAction.BUY,
            symbol="AAPL",
            shares=100,
            estimated_value=15000.0,
            reason="Test buy",
        )

        assert order.action == OrderAction.BUY
        assert order.symbol == "AAPL"
        assert order.shares == 100
        assert order.estimated_value == 15000.0
        assert order.reason == "Test buy"
        assert isinstance(order.timestamp, datetime)

    def test_order_creation_sell(self) -> None:
        """Test creating a sell order."""
        order = Order(
            action=OrderAction.SELL,
            symbol="MSFT",
            shares=50,
            estimated_value=17500.0,
        )

        assert order.action == OrderAction.SELL
        assert order.symbol == "MSFT"
        assert order.shares == 50

    def test_order_invalid_shares_zero(self) -> None:
        """Test order rejects zero shares."""
        with pytest.raises(ValueError, match="shares must be positive"):
            Order(
                action=OrderAction.BUY,
                symbol="AAPL",
                shares=0,
                estimated_value=0.0,
            )

    def test_order_invalid_shares_negative(self) -> None:
        """Test order rejects negative shares."""
        with pytest.raises(ValueError, match="shares must be positive"):
            Order(
                action=OrderAction.BUY,
                symbol="AAPL",
                shares=-10,
                estimated_value=1000.0,
            )

    def test_order_invalid_estimated_value_negative(self) -> None:
        """Test order rejects negative estimated value."""
        with pytest.raises(ValueError, match="estimated_value must be non-negative"):
            Order(
                action=OrderAction.BUY,
                symbol="AAPL",
                shares=10,
                estimated_value=-1000.0,
            )

    def test_order_default_timestamp(self) -> None:
        """Test order has default timestamp."""
        before = datetime.now()
        order = Order(
            action=OrderAction.BUY,
            symbol="AAPL",
            shares=10,
            estimated_value=1500.0,
        )
        after = datetime.now()

        assert before <= order.timestamp <= after

    def test_order_default_reason(self) -> None:
        """Test order has default empty reason."""
        order = Order(
            action=OrderAction.BUY,
            symbol="AAPL",
            shares=10,
            estimated_value=1500.0,
        )

        assert order.reason == ""


class TestPortfolioState:
    """Test cases for PortfolioState dataclass."""

    def test_portfolio_state_creation(self) -> None:
        """Test creating a portfolio state."""
        state = PortfolioState(
            positions={"AAPL": 15000.0, "MSFT": 10000.0},
            total_value=100000.0,
            cash=75000.0,
            prices={"AAPL": 150.0, "MSFT": 350.0},
        )

        assert state.positions == {"AAPL": 15000.0, "MSFT": 10000.0}
        assert state.total_value == 100000.0
        assert state.cash == 75000.0
        assert state.prices == {"AAPL": 150.0, "MSFT": 350.0}
        assert isinstance(state.timestamp, datetime)

    def test_portfolio_state_empty_positions(self) -> None:
        """Test portfolio with no positions (all cash)."""
        state = PortfolioState(
            positions={},
            total_value=50000.0,
            cash=50000.0,
            prices={},
        )

        assert state.positions == {}
        assert state.total_value == 50000.0
        assert state.cash == 50000.0

    def test_portfolio_state_invalid_total_value(self) -> None:
        """Test portfolio state rejects negative total value."""
        with pytest.raises(ValueError, match="total_value must be non-negative"):
            PortfolioState(
                positions={},
                total_value=-1000.0,
                cash=0.0,
                prices={},
            )

    def test_portfolio_state_invalid_cash(self) -> None:
        """Test portfolio state rejects negative cash."""
        with pytest.raises(ValueError, match="cash must be non-negative"):
            PortfolioState(
                positions={},
                total_value=10000.0,
                cash=-500.0,
                prices={},
            )

    def test_portfolio_state_zero_values(self) -> None:
        """Test portfolio state accepts zero values."""
        state = PortfolioState(
            positions={},
            total_value=0.0,
            cash=0.0,
            prices={},
        )

        assert state.total_value == 0.0
        assert state.cash == 0.0


class TestAllocationResult:
    """Test cases for AllocationResult dataclass."""

    def test_allocation_result_creation(self) -> None:
        """Test creating an allocation result."""
        orders = [
            Order(
                action=OrderAction.BUY,
                symbol="AAPL",
                shares=100,
                estimated_value=15000.0,
            )
        ]

        result = AllocationResult(
            target_weights={"AAPL": 0.25, "Cash": 0.75},
            orders=orders,
            metrics={"turnover": 0.15},
        )

        assert result.target_weights == {"AAPL": 0.25, "Cash": 0.75}
        assert len(result.orders) == 1
        assert result.metrics == {"turnover": 0.15}

    def test_allocation_result_default_metrics(self) -> None:
        """Test allocation result has default empty metrics."""
        result = AllocationResult(
            target_weights={"Cash": 1.0},
            orders=[],
        )

        assert result.metrics == {}

    def test_allocation_result_empty_orders(self) -> None:
        """Test allocation result with no orders."""
        result = AllocationResult(
            target_weights={"AAPL": 0.50, "Cash": 0.50},
            orders=[],
        )

        assert result.orders == []


class TestOrderAction:
    """Test cases for OrderAction enum."""

    def test_order_action_values(self) -> None:
        """Test OrderAction enum values."""
        assert OrderAction.BUY.value == "BUY"
        assert OrderAction.SELL.value == "SELL"

    def test_order_action_comparison(self) -> None:
        """Test OrderAction enum comparison."""
        assert OrderAction.BUY != OrderAction.SELL
        assert OrderAction.BUY == OrderAction.BUY


class ConcretePortfolioManager(PortfolioManager):
    """Concrete implementation for testing abstract class."""

    def allocate(self, signals, portfolio):
        target_weights = self.calculate_target_weights(signals)
        orders = self.generate_orders(
            portfolio.positions,
            target_weights,
            portfolio.total_value,
            portfolio.prices,
        )
        return AllocationResult(target_weights=target_weights, orders=orders)

    def calculate_target_weights(self, signals):
        # Simple: equal weight all positive signals
        positive = {s: v for s, v in signals.items() if v > 0}
        if not positive:
            return {"Cash": 1.0}
        weight = 0.9 / len(positive)  # 10% cash buffer
        weights = {s: weight for s in positive}
        weights["Cash"] = 0.1
        return weights

    def generate_orders(self, current_positions, target_weights, total_value, prices):
        orders = []
        for symbol, weight in target_weights.items():
            if symbol == "Cash":
                continue
            target_value = weight * total_value
            current_value = current_positions.get(symbol, 0)
            diff = target_value - current_value
            if abs(diff) > 100 and symbol in prices:
                shares = int(abs(diff) / prices[symbol])
                if shares > 0:
                    action = OrderAction.BUY if diff > 0 else OrderAction.SELL
                    orders.append(
                        Order(
                            action=action,
                            symbol=symbol,
                            shares=shares,
                            estimated_value=shares * prices[symbol],
                        )
                    )
        return orders


class TestPortfolioManagerInterface:
    """Test cases for PortfolioManager abstract interface."""

    def test_cannot_instantiate_abstract_class(self) -> None:
        """Test PortfolioManager cannot be instantiated directly."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            PortfolioManager()  # type: ignore

    def test_concrete_implementation_works(self) -> None:
        """Test concrete implementation can be instantiated."""
        manager = ConcretePortfolioManager()
        assert isinstance(manager, PortfolioManager)

    def test_should_rebalance_no_drift(self) -> None:
        """Test should_rebalance returns False when no drift."""
        manager = ConcretePortfolioManager()

        current = {"AAPL": 0.25, "MSFT": 0.25, "Cash": 0.50}
        target = {"AAPL": 0.25, "MSFT": 0.25, "Cash": 0.50}

        assert not manager.should_rebalance(current, target, threshold=0.05)

    def test_should_rebalance_small_drift(self) -> None:
        """Test should_rebalance returns False for small drift."""
        manager = ConcretePortfolioManager()

        current = {"AAPL": 0.26, "MSFT": 0.24, "Cash": 0.50}
        target = {"AAPL": 0.25, "MSFT": 0.25, "Cash": 0.50}

        # Max drift is 1%, below 5% threshold
        assert not manager.should_rebalance(current, target, threshold=0.05)

    def test_should_rebalance_large_drift(self) -> None:
        """Test should_rebalance returns True for large drift."""
        manager = ConcretePortfolioManager()

        current = {"AAPL": 0.35, "MSFT": 0.15, "Cash": 0.50}
        target = {"AAPL": 0.25, "MSFT": 0.25, "Cash": 0.50}

        # Max drift is 10%, above 5% threshold
        assert manager.should_rebalance(current, target, threshold=0.05)

    def test_should_rebalance_new_position(self) -> None:
        """Test should_rebalance detects new positions."""
        manager = ConcretePortfolioManager()

        current = {"AAPL": 0.50, "Cash": 0.50}
        target = {"AAPL": 0.25, "GOOGL": 0.25, "Cash": 0.50}

        # GOOGL is new (drift from 0 to 0.25 = 25%)
        assert manager.should_rebalance(current, target, threshold=0.05)

    def test_should_rebalance_removed_position(self) -> None:
        """Test should_rebalance detects removed positions."""
        manager = ConcretePortfolioManager()

        current = {"AAPL": 0.25, "MSFT": 0.25, "Cash": 0.50}
        target = {"AAPL": 0.50, "Cash": 0.50}

        # MSFT removed (drift from 0.25 to 0 = 25%)
        assert manager.should_rebalance(current, target, threshold=0.05)

    def test_calculate_current_weights(self) -> None:
        """Test calculate_current_weights from portfolio state."""
        manager = ConcretePortfolioManager()

        portfolio = PortfolioState(
            positions={"AAPL": 25000.0, "MSFT": 25000.0},
            total_value=100000.0,
            cash=50000.0,
            prices={"AAPL": 150.0, "MSFT": 350.0},
        )

        weights = manager.calculate_current_weights(portfolio)

        assert weights["AAPL"] == 0.25
        assert weights["MSFT"] == 0.25
        assert weights["Cash"] == 0.50

    def test_calculate_current_weights_all_cash(self) -> None:
        """Test calculate_current_weights with all cash portfolio."""
        manager = ConcretePortfolioManager()

        portfolio = PortfolioState(
            positions={},
            total_value=100000.0,
            cash=100000.0,
            prices={},
        )

        weights = manager.calculate_current_weights(portfolio)

        assert weights == {"Cash": 1.0}

    def test_calculate_current_weights_zero_value(self) -> None:
        """Test calculate_current_weights with zero portfolio value."""
        manager = ConcretePortfolioManager()

        portfolio = PortfolioState(
            positions={},
            total_value=0.0,
            cash=0.0,
            prices={},
        )

        weights = manager.calculate_current_weights(portfolio)

        assert weights == {"Cash": 1.0}
