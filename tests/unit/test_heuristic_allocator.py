"""Unit tests for HeuristicAllocator."""

import pytest

from src.portfolio.base import OrderAction, PortfolioState
from src.portfolio.heuristic_allocator import HeuristicAllocator


class TestHeuristicAllocatorConfig:
    """Test cases for HeuristicAllocator configuration."""

    def test_default_config(self) -> None:
        """Test allocator with default configuration."""
        allocator = HeuristicAllocator()

        assert allocator.min_signal_threshold == 0.3
        assert allocator.max_positions == 10
        assert allocator.cash_buffer == 0.10
        assert allocator.max_position_size == 0.20
        assert allocator.min_trade_value == 100.0

    def test_custom_config(self) -> None:
        """Test allocator with custom configuration."""
        config = {
            "min_signal_threshold": 0.5,
            "max_positions": 5,
            "cash_buffer": 0.20,
            "max_position_size": 0.30,
            "min_trade_value": 500.0,
        }
        allocator = HeuristicAllocator(config)

        assert allocator.min_signal_threshold == 0.5
        assert allocator.max_positions == 5
        assert allocator.cash_buffer == 0.20
        assert allocator.max_position_size == 0.30
        assert allocator.min_trade_value == 500.0

    def test_invalid_min_signal_threshold_negative(self) -> None:
        """Test config validation for negative min_signal_threshold."""
        with pytest.raises(ValueError, match="min_signal_threshold must be in"):
            HeuristicAllocator({"min_signal_threshold": -0.1})

    def test_invalid_min_signal_threshold_above_one(self) -> None:
        """Test config validation for min_signal_threshold > 1."""
        with pytest.raises(ValueError, match="min_signal_threshold must be in"):
            HeuristicAllocator({"min_signal_threshold": 1.5})

    def test_invalid_max_positions(self) -> None:
        """Test config validation for max_positions < 1."""
        with pytest.raises(ValueError, match="max_positions must be >= 1"):
            HeuristicAllocator({"max_positions": 0})

    def test_invalid_cash_buffer_negative(self) -> None:
        """Test config validation for negative cash_buffer."""
        with pytest.raises(ValueError, match="cash_buffer must be in"):
            HeuristicAllocator({"cash_buffer": -0.1})

    def test_invalid_cash_buffer_one(self) -> None:
        """Test config validation for cash_buffer = 1."""
        with pytest.raises(ValueError, match="cash_buffer must be in"):
            HeuristicAllocator({"cash_buffer": 1.0})

    def test_invalid_max_position_size_zero(self) -> None:
        """Test config validation for max_position_size = 0."""
        with pytest.raises(ValueError, match="max_position_size must be in"):
            HeuristicAllocator({"max_position_size": 0})

    def test_invalid_min_trade_value(self) -> None:
        """Test config validation for negative min_trade_value."""
        with pytest.raises(ValueError, match="min_trade_value must be >= 0"):
            HeuristicAllocator({"min_trade_value": -100})


class TestCalculateTargetWeights:
    """Test cases for calculate_target_weights method."""

    @pytest.fixture
    def allocator(self) -> HeuristicAllocator:
        """Create allocator with test configuration."""
        return HeuristicAllocator(
            {
                "min_signal_threshold": 0.3,
                "max_positions": 5,
                "cash_buffer": 0.10,
                "max_position_size": 0.25,
            }
        )

    def test_no_strong_signals(self, allocator: HeuristicAllocator) -> None:
        """Test 100% cash when no signals above threshold."""
        signals = {"AAPL": 0.2, "MSFT": 0.1, "GOOGL": -0.5}
        weights = allocator.calculate_target_weights(signals)

        assert weights == {"Cash": 1.0}

    def test_all_negative_signals(self, allocator: HeuristicAllocator) -> None:
        """Test 100% cash when all signals are negative."""
        signals = {"AAPL": -0.8, "MSFT": -0.5, "GOOGL": -0.3}
        weights = allocator.calculate_target_weights(signals)

        assert weights == {"Cash": 1.0}

    def test_single_strong_signal(self, allocator: HeuristicAllocator) -> None:
        """Test allocation with single strong signal."""
        signals = {"AAPL": 0.8, "MSFT": 0.1, "GOOGL": 0.2}
        weights = allocator.calculate_target_weights(signals)

        # Only AAPL above threshold, gets full investable (90% - 10% cash)
        # But capped at max_position_size (25%)
        assert "AAPL" in weights
        assert "Cash" in weights
        assert weights["AAPL"] <= 0.25  # Capped
        assert weights["Cash"] >= 0.10  # At least cash buffer
        assert abs(sum(weights.values()) - 1.0) < 0.001

    def test_multiple_strong_signals(self, allocator: HeuristicAllocator) -> None:
        """Test proportional allocation with multiple signals."""
        signals = {"AAPL": 0.8, "MSFT": 0.4}  # Both above 0.3
        weights = allocator.calculate_target_weights(signals)

        # Both signals should be allocated
        assert "AAPL" in weights
        assert "MSFT" in weights
        assert "Cash" in weights
        # When both get capped at max_position_size, they may be equal
        # AAPL should get >= MSFT (stronger signal, but may be capped)
        assert weights["AAPL"] >= weights["MSFT"]
        assert abs(sum(weights.values()) - 1.0) < 0.001

    def test_max_positions_limit(self, allocator: HeuristicAllocator) -> None:
        """Test max_positions limit is enforced."""
        # Create 10 signals, all above threshold
        signals = {f"STOCK{i}": 0.5 + i * 0.05 for i in range(10)}
        weights = allocator.calculate_target_weights(signals)

        # Should only have max_positions (5) + Cash
        equity_positions = [k for k in weights.keys() if k != "Cash"]
        assert len(equity_positions) <= 5

    def test_top_signals_selected(self, allocator: HeuristicAllocator) -> None:
        """Test that strongest signals are selected."""
        signals = {
            "WEAK1": 0.35,
            "WEAK2": 0.40,
            "STRONG1": 0.80,
            "STRONG2": 0.90,
            "STRONG3": 0.70,
            "MID1": 0.50,
            "MID2": 0.55,
        }
        weights = allocator.calculate_target_weights(signals)

        # Top 5 should be: STRONG2, STRONG1, STRONG3, MID2, MID1
        equity_positions = [k for k in weights.keys() if k != "Cash"]
        assert "STRONG2" in equity_positions
        assert "STRONG1" in equity_positions
        assert "STRONG3" in equity_positions

    def test_position_size_cap(self) -> None:
        """Test individual position size is capped."""
        # Very high cap with only 2 signals to test proportional allocation
        allocator = HeuristicAllocator(
            {
                "min_signal_threshold": 0.3,
                "max_positions": 10,
                "cash_buffer": 0.10,
                "max_position_size": 0.20,
            }
        )

        # Two signals with very different strengths
        signals = {"STRONG": 0.9, "WEAK": 0.4}
        weights = allocator.calculate_target_weights(signals)

        # Both should be capped at 20%
        assert weights["STRONG"] <= 0.20 + 0.001
        assert weights["WEAK"] <= 0.20 + 0.001

    def test_weights_sum_to_one(self, allocator: HeuristicAllocator) -> None:
        """Test all weights sum to 1.0."""
        signals = {"AAPL": 0.8, "MSFT": 0.6, "GOOGL": 0.5, "AMZN": 0.4}
        weights = allocator.calculate_target_weights(signals)

        total = sum(weights.values())
        assert abs(total - 1.0) < 0.001

    def test_cash_buffer_maintained(self, allocator: HeuristicAllocator) -> None:
        """Test cash buffer is always maintained."""
        signals = {"AAPL": 1.0, "MSFT": 1.0, "GOOGL": 1.0}
        weights = allocator.calculate_target_weights(signals)

        assert weights.get("Cash", 0) >= allocator.cash_buffer - 0.001

    def test_empty_signals(self, allocator: HeuristicAllocator) -> None:
        """Test handling of empty signals dict."""
        weights = allocator.calculate_target_weights({})
        assert weights == {"Cash": 1.0}


class TestGenerateOrders:
    """Test cases for generate_orders method."""

    @pytest.fixture
    def allocator(self) -> HeuristicAllocator:
        """Create allocator with test configuration."""
        return HeuristicAllocator(
            {
                "min_signal_threshold": 0.3,
                "max_positions": 5,
                "cash_buffer": 0.10,
                "max_position_size": 0.25,
                "min_trade_value": 100.0,
            }
        )

    def test_buy_order_generation(self, allocator: HeuristicAllocator) -> None:
        """Test generating buy orders for new positions."""
        orders = allocator.generate_orders(
            current_positions={},
            target_weights={"AAPL": 0.25, "Cash": 0.75},
            total_value=100000.0,
            prices={"AAPL": 150.0},
        )

        assert len(orders) == 1
        assert orders[0].action == OrderAction.BUY
        assert orders[0].symbol == "AAPL"
        # Target: $25,000, shares = 25000/150 = 166
        assert orders[0].shares == 166

    def test_sell_order_generation(self, allocator: HeuristicAllocator) -> None:
        """Test generating sell orders to reduce positions."""
        orders = allocator.generate_orders(
            current_positions={"AAPL": 25000.0},
            target_weights={"AAPL": 0.10, "Cash": 0.90},
            total_value=100000.0,
            prices={"AAPL": 150.0},
        )

        assert len(orders) == 1
        assert orders[0].action == OrderAction.SELL
        assert orders[0].symbol == "AAPL"
        # Current: $25,000, Target: $10,000, Sell $15,000 = 100 shares
        assert orders[0].shares == 100

    def test_full_exit_order(self, allocator: HeuristicAllocator) -> None:
        """Test generating order to fully exit position."""
        orders = allocator.generate_orders(
            current_positions={"AAPL": 15000.0},
            target_weights={"Cash": 1.0},  # No AAPL in target
            total_value=100000.0,
            prices={"AAPL": 150.0},
        )

        assert len(orders) == 1
        assert orders[0].action == OrderAction.SELL
        assert orders[0].symbol == "AAPL"
        # Sell all: $15,000 / $150 = 100 shares
        assert orders[0].shares == 100

    def test_no_orders_when_on_target(self, allocator: HeuristicAllocator) -> None:
        """Test no orders when current matches target."""
        orders = allocator.generate_orders(
            current_positions={"AAPL": 25000.0},
            target_weights={"AAPL": 0.25, "Cash": 0.75},
            total_value=100000.0,
            prices={"AAPL": 150.0},
        )

        # Current matches target (25% = $25,000), no orders needed
        assert len(orders) == 0

    def test_skip_small_trades(self, allocator: HeuristicAllocator) -> None:
        """Test orders below min_trade_value are skipped."""
        orders = allocator.generate_orders(
            current_positions={"AAPL": 24950.0},  # $50 below target
            target_weights={"AAPL": 0.25, "Cash": 0.75},
            total_value=100000.0,
            prices={"AAPL": 150.0},
        )

        # Difference is $50, below $100 threshold
        assert len(orders) == 0

    def test_skip_missing_prices(self, allocator: HeuristicAllocator) -> None:
        """Test symbols without prices are skipped."""
        orders = allocator.generate_orders(
            current_positions={},
            target_weights={"AAPL": 0.25, "MSFT": 0.25, "Cash": 0.50},
            total_value=100000.0,
            prices={"AAPL": 150.0},  # No MSFT price
        )

        # Only AAPL order generated
        assert len(orders) == 1
        assert orders[0].symbol == "AAPL"

    def test_sells_before_buys(self, allocator: HeuristicAllocator) -> None:
        """Test sell orders come before buy orders."""
        orders = allocator.generate_orders(
            current_positions={"AAPL": 30000.0, "MSFT": 0.0},
            target_weights={"AAPL": 0.20, "MSFT": 0.20, "Cash": 0.60},
            total_value=100000.0,
            prices={"AAPL": 150.0, "MSFT": 350.0},
        )

        # Should have sell AAPL (30k -> 20k) and buy MSFT (0 -> 20k)
        assert len(orders) == 2

        # Sells should come first
        sell_orders = [o for o in orders if o.action == OrderAction.SELL]
        buy_orders = [o for o in orders if o.action == OrderAction.BUY]

        assert len(sell_orders) == 1
        assert len(buy_orders) == 1

        # Find indices
        sell_idx = orders.index(sell_orders[0])
        buy_idx = orders.index(buy_orders[0])
        assert sell_idx < buy_idx

    def test_multiple_orders(self, allocator: HeuristicAllocator) -> None:
        """Test generating multiple orders."""
        orders = allocator.generate_orders(
            current_positions={"AAPL": 10000.0},
            target_weights={
                "AAPL": 0.20,  # Increase from 10k to 20k
                "MSFT": 0.15,  # New position 15k
                "GOOGL": 0.10,  # New position 10k
                "Cash": 0.55,
            },
            total_value=100000.0,
            prices={"AAPL": 150.0, "MSFT": 350.0, "GOOGL": 140.0},
        )

        # Should have 3 buy orders
        assert len(orders) == 3
        assert all(o.action == OrderAction.BUY for o in orders)

    def test_order_estimated_value(self, allocator: HeuristicAllocator) -> None:
        """Test order estimated_value is calculated correctly."""
        orders = allocator.generate_orders(
            current_positions={},
            target_weights={"AAPL": 0.25, "Cash": 0.75},
            total_value=100000.0,
            prices={"AAPL": 150.0},
        )

        order = orders[0]
        # estimated_value = shares * price
        assert order.estimated_value == order.shares * 150.0

    def test_skip_zero_price(self, allocator: HeuristicAllocator) -> None:
        """Test symbols with zero price are skipped."""
        orders = allocator.generate_orders(
            current_positions={},
            target_weights={"AAPL": 0.25, "Cash": 0.75},
            total_value=100000.0,
            prices={"AAPL": 0.0},
        )

        assert len(orders) == 0


class TestAllocate:
    """Test cases for allocate method (full pipeline)."""

    @pytest.fixture
    def allocator(self) -> HeuristicAllocator:
        """Create allocator with test configuration."""
        return HeuristicAllocator(
            {
                "min_signal_threshold": 0.3,
                "max_positions": 5,
                "cash_buffer": 0.10,
                "max_position_size": 0.25,
                "min_trade_value": 100.0,
            }
        )

    @pytest.fixture
    def portfolio(self) -> PortfolioState:
        """Create test portfolio state."""
        return PortfolioState(
            positions={"MSFT": 10000.0},
            total_value=100000.0,
            cash=90000.0,
            prices={"AAPL": 150.0, "MSFT": 350.0, "GOOGL": 140.0},
        )

    def test_full_allocation_pipeline(
        self, allocator: HeuristicAllocator, portfolio: PortfolioState
    ) -> None:
        """Test full allocation from signals to orders."""
        signals = {"AAPL": 0.8, "MSFT": 0.5, "GOOGL": 0.2}

        result = allocator.allocate(signals, portfolio)

        # Check result structure
        assert "AAPL" in result.target_weights  # Strong signal
        assert "MSFT" in result.target_weights  # Medium signal
        assert "GOOGL" not in result.target_weights  # Weak signal (0.2 < 0.3)
        assert "Cash" in result.target_weights

        # Check weights sum to 1
        assert abs(sum(result.target_weights.values()) - 1.0) < 0.001

        # Check orders exist
        assert isinstance(result.orders, list)

        # Check metrics
        assert "position_count" in result.metrics
        assert "cash_weight" in result.metrics
        assert "turnover" in result.metrics

    def test_metrics_calculation(
        self, allocator: HeuristicAllocator, portfolio: PortfolioState
    ) -> None:
        """Test metrics are calculated correctly."""
        signals = {"AAPL": 0.8, "MSFT": 0.5}

        result = allocator.allocate(signals, portfolio)

        # Position count should be 2 (AAPL + MSFT)
        assert result.metrics["position_count"] == 2.0

        # Cash weight should be at least buffer
        assert result.metrics["cash_weight"] >= 0.10

        # Turnover should be positive (we're making changes)
        assert result.metrics["turnover"] >= 0

        # Order counts
        assert result.metrics["order_count"] >= 0
        assert result.metrics["buy_order_count"] >= 0
        assert result.metrics["sell_order_count"] >= 0

    def test_all_cash_allocation(
        self, allocator: HeuristicAllocator, portfolio: PortfolioState
    ) -> None:
        """Test allocation with no investable signals."""
        signals = {"AAPL": 0.1, "MSFT": -0.5}  # All below threshold or negative

        result = allocator.allocate(signals, portfolio)

        # Should be 100% cash
        assert result.target_weights == {"Cash": 1.0}

        # Should have sell order for existing MSFT position
        sell_orders = [o for o in result.orders if o.action == OrderAction.SELL]
        assert len(sell_orders) == 1
        assert sell_orders[0].symbol == "MSFT"


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_zero_total_value_portfolio(self) -> None:
        """Test handling portfolio with zero total value."""
        allocator = HeuristicAllocator()
        portfolio = PortfolioState(
            positions={},
            total_value=0.0,
            cash=0.0,
            prices={"AAPL": 150.0},
        )

        result = allocator.allocate({"AAPL": 0.8}, portfolio)

        # No orders should be generated (can't trade with no value)
        assert result.orders == []
        assert result.target_weights == {"Cash": 1.0} or "AAPL" in result.target_weights

    def test_signal_exactly_at_threshold(self) -> None:
        """Test signal exactly at threshold is not included."""
        allocator = HeuristicAllocator({"min_signal_threshold": 0.3})

        weights = allocator.calculate_target_weights({"AAPL": 0.3})

        # Signal at exactly threshold should be excluded (> not >=)
        assert weights == {"Cash": 1.0}

    def test_signal_just_above_threshold(self) -> None:
        """Test signal just above threshold is included."""
        allocator = HeuristicAllocator({"min_signal_threshold": 0.3})

        weights = allocator.calculate_target_weights({"AAPL": 0.31})

        assert "AAPL" in weights

    def test_very_small_share_calculation(self) -> None:
        """Test when share calculation results in zero shares."""
        allocator = HeuristicAllocator({"min_trade_value": 100.0})

        # Target $50 worth but price is $1000 -> 0 shares
        orders = allocator.generate_orders(
            current_positions={},
            target_weights={"AAPL": 0.005, "Cash": 0.995},  # 0.5% = $500
            total_value=100000.0,
            prices={"AAPL": 1000.0},  # High price
        )

        # $500 target, but after truncation to shares: 500/1000 = 0 shares
        # Actually 500/1000 = 0.5, truncated to 0
        # Wait, 500 / 1000 = 0.5 -> int(0.5) = 0, so no order
        # But min_trade_value check comes first: 500 > 100, so we try
        # Then shares = int(500/1000) = 0, skipped
        assert len(orders) == 0

    def test_large_portfolio(self) -> None:
        """Test with large portfolio value."""
        allocator = HeuristicAllocator()

        signals = {"AAPL": 0.8, "MSFT": 0.7, "GOOGL": 0.6}
        portfolio = PortfolioState(
            positions={},
            total_value=10_000_000.0,  # $10M
            cash=10_000_000.0,
            prices={"AAPL": 150.0, "MSFT": 350.0, "GOOGL": 140.0},
        )

        result = allocator.allocate(signals, portfolio)

        # Should still work correctly
        assert abs(sum(result.target_weights.values()) - 1.0) < 0.001
        assert len(result.orders) > 0
