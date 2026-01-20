"""Heuristic rule-based portfolio allocator.

This module implements a simple, transparent allocation algorithm for Phase 1.
It converts trading signals to portfolio weights using configurable rules.

Algorithm:
1. Filter weak signals (only trade signals above threshold)
2. Select top N strongest signals (limit positions)
3. Allocate proportional to signal strength
4. Cap individual position size (risk control)
5. Maintain cash buffer
"""

from datetime import datetime
from typing import Dict, List, Optional

from src.portfolio.base import (
    AllocationResult,
    Order,
    OrderAction,
    PortfolioManager,
    PortfolioState,
)


class HeuristicAllocator(PortfolioManager):
    """Phase 1 heuristic portfolio allocator.

    Uses simple, transparent rules for allocation without optimization.
    Good enough to validate the system pipeline and establish baseline performance.

    Configuration Parameters:
        min_signal_threshold: Minimum signal strength to consider (default 0.3)
        max_positions: Maximum number of positions to hold (default 10)
        cash_buffer: Percentage of portfolio to keep in cash (default 0.10)
        max_position_size: Maximum weight for single position (default 0.20)
        min_trade_value: Minimum dollar value to generate an order (default 100)

    Example:
        >>> config = {
        ...     'min_signal_threshold': 0.3,
        ...     'max_positions': 10,
        ...     'cash_buffer': 0.10,
        ...     'max_position_size': 0.20,
        ...     'min_trade_value': 100
        ... }
        >>> allocator = HeuristicAllocator(config)
        >>> signals = {'AAPL': 0.8, 'MSFT': 0.5, 'GOOGL': 0.2, 'TSLA': -0.6}
        >>> weights = allocator.calculate_target_weights(signals)
        >>> # GOOGL filtered (0.2 < 0.3), TSLA filtered (negative)
        >>> # AAPL and MSFT allocated proportionally
    """

    def __init__(self, config: Optional[Dict] = None):
        """Initialize allocator with configuration.

        Args:
            config: Configuration dictionary with allocation parameters.
                   Uses sensible defaults if not provided.
        """
        config = config or {}

        self.min_signal_threshold = config.get("min_signal_threshold", 0.3)
        self.max_positions = config.get("max_positions", 10)
        self.cash_buffer = config.get("cash_buffer", 0.10)
        self.max_position_size = config.get("max_position_size", 0.20)
        self.min_trade_value = config.get("min_trade_value", 100.0)

        self._validate_config()

    def _validate_config(self) -> None:
        """Validate configuration parameters."""
        if not 0 <= self.min_signal_threshold <= 1:
            raise ValueError(
                f"min_signal_threshold must be in [0, 1], got {self.min_signal_threshold}"
            )
        if self.max_positions < 1:
            raise ValueError(
                f"max_positions must be >= 1, got {self.max_positions}"
            )
        if not 0 <= self.cash_buffer < 1:
            raise ValueError(f"cash_buffer must be in [0, 1), got {self.cash_buffer}")
        if not 0 < self.max_position_size <= 1:
            raise ValueError(
                f"max_position_size must be in (0, 1], got {self.max_position_size}"
            )
        if self.min_trade_value < 0:
            raise ValueError(
                f"min_trade_value must be >= 0, got {self.min_trade_value}"
            )

    def allocate(
        self,
        signals: Dict[str, float],
        portfolio: PortfolioState,
    ) -> AllocationResult:
        """Calculate target allocation and generate rebalancing orders.

        Args:
            signals: Trading signals {symbol: signal_value}
            portfolio: Current portfolio state

        Returns:
            AllocationResult with target weights, orders, and metrics
        """
        # Step 1: Calculate target weights from signals
        target_weights = self.calculate_target_weights(signals)

        # Step 2: Generate orders to achieve target allocation
        orders = self.generate_orders(
            current_positions=portfolio.positions,
            target_weights=target_weights,
            total_value=portfolio.total_value,
            prices=portfolio.prices,
        )

        # Step 3: Calculate metrics
        current_weights = self.calculate_current_weights(portfolio)
        metrics = self._calculate_metrics(
            signals=signals,
            target_weights=target_weights,
            current_weights=current_weights,
            orders=orders,
            total_value=portfolio.total_value,
        )

        return AllocationResult(
            target_weights=target_weights,
            orders=orders,
            metrics=metrics,
        )

    def calculate_target_weights(
        self,
        signals: Dict[str, float],
    ) -> Dict[str, float]:
        """Convert signals to target portfolio weights.

        Algorithm:
        1. Filter signals below threshold and negative signals
        2. Select top N by signal strength
        3. Allocate proportional to signal strength
        4. Apply position size cap
        5. Calculate remaining cash

        Args:
            signals: Trading signals {symbol: signal_value}

        Returns:
            Target weights {symbol: weight} summing to 1.0
        """
        # Step 1: Filter weak and negative signals
        strong_signals = {
            symbol: signal
            for symbol, signal in signals.items()
            if signal > self.min_signal_threshold
        }

        # Step 2: Select top N strongest signals
        sorted_signals = sorted(
            strong_signals.items(), key=lambda x: x[1], reverse=True
        )
        top_signals = dict(sorted_signals[: self.max_positions])

        # No strong signals -> 100% cash
        if not top_signals:
            return {"Cash": 1.0}

        # Step 3: Allocate proportional to signal strength
        total_strength = sum(top_signals.values())
        investable_ratio = 1.0 - self.cash_buffer

        weights = {}
        for symbol, signal in top_signals.items():
            weight = (signal / total_strength) * investable_ratio
            # Step 4: Cap individual position size
            weight = min(weight, self.max_position_size)
            weights[symbol] = weight

        # Step 5: Handle case where position caps reduce total allocation
        total_allocated = sum(weights.values())
        if total_allocated < investable_ratio:
            # Redistribute remaining capacity proportionally
            remaining = investable_ratio - total_allocated
            uncapped_symbols = [
                s for s, w in weights.items() if w < self.max_position_size
            ]

            if uncapped_symbols:
                uncapped_total = sum(weights[s] for s in uncapped_symbols)
                for symbol in uncapped_symbols:
                    additional = (weights[symbol] / uncapped_total) * remaining
                    new_weight = weights[symbol] + additional
                    weights[symbol] = min(new_weight, self.max_position_size)

        # Calculate cash weight
        weights["Cash"] = 1.0 - sum(w for s, w in weights.items() if s != "Cash")

        return weights

    def generate_orders(
        self,
        current_positions: Dict[str, float],
        target_weights: Dict[str, float],
        total_value: float,
        prices: Dict[str, float],
    ) -> List[Order]:
        """Generate orders to move from current to target positions.

        Orders are sorted with sells first (to free up cash for buys).

        Args:
            current_positions: Current holdings {symbol: dollar_value}
            target_weights: Target allocation {symbol: weight}
            total_value: Total portfolio value
            prices: Current prices {symbol: price}

        Returns:
            List of Order objects, sells first then buys
        """
        # Calculate target dollar positions
        target_positions = {
            symbol: weight * total_value
            for symbol, weight in target_weights.items()
            if symbol != "Cash"
        }

        orders: List[Order] = []
        sell_orders: List[Order] = []
        buy_orders: List[Order] = []

        # Check all symbols (current + target)
        all_symbols = set(current_positions.keys()) | set(target_positions.keys())
        all_symbols.discard("Cash")

        for symbol in all_symbols:
            current_value = current_positions.get(symbol, 0.0)
            target_value = target_positions.get(symbol, 0.0)
            diff_value = target_value - current_value

            # Skip small trades
            if abs(diff_value) < self.min_trade_value:
                continue

            # Skip if no price available
            price = prices.get(symbol)
            if price is None or price <= 0:
                continue

            # Convert to shares (truncate toward zero)
            shares = int(abs(diff_value) / price)
            if shares == 0:
                continue

            if diff_value > 0:
                # Buy order
                order = Order(
                    action=OrderAction.BUY,
                    symbol=symbol,
                    shares=shares,
                    estimated_value=shares * price,
                    reason=f"Increase position to {target_weights.get(symbol, 0):.1%}",
                )
                buy_orders.append(order)
            else:
                # Sell order
                order = Order(
                    action=OrderAction.SELL,
                    symbol=symbol,
                    shares=shares,
                    estimated_value=shares * price,
                    reason=f"Reduce position to {target_weights.get(symbol, 0):.1%}",
                )
                sell_orders.append(order)

        # Sells first, then buys (to free up cash)
        orders = sell_orders + buy_orders

        return orders

    def _calculate_metrics(
        self,
        signals: Dict[str, float],
        target_weights: Dict[str, float],
        current_weights: Dict[str, float],
        orders: List[Order],
        total_value: float,
    ) -> Dict[str, float]:
        """Calculate allocation metrics for monitoring.

        Returns:
            Dictionary with various metrics
        """
        # Position count (excluding cash)
        position_count = len([s for s in target_weights if s != "Cash"])

        # Cash allocation
        cash_weight = target_weights.get("Cash", 0.0)

        # Turnover (total order value / portfolio value)
        total_order_value = sum(o.estimated_value for o in orders)
        turnover = total_order_value / total_value if total_value > 0 else 0.0

        # Concentration (Herfindahl index)
        equity_weights = [w for s, w in target_weights.items() if s != "Cash"]
        herfindahl = sum(w**2 for w in equity_weights) if equity_weights else 0.0

        # Signal utilization (how many signals above threshold)
        strong_signal_count = sum(
            1 for s in signals.values() if s > self.min_signal_threshold
        )

        return {
            "position_count": float(position_count),
            "cash_weight": cash_weight,
            "turnover": turnover,
            "herfindahl_index": herfindahl,
            "strong_signal_count": float(strong_signal_count),
            "order_count": float(len(orders)),
            "buy_order_count": float(
                sum(1 for o in orders if o.action == OrderAction.BUY)
            ),
            "sell_order_count": float(
                sum(1 for o in orders if o.action == OrderAction.SELL)
            ),
        }
