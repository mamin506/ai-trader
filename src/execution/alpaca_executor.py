"""Alpaca order execution implementation.

This module implements the OrderExecutor interface for Alpaca Paper Trading.
"""

from datetime import datetime
from typing import Dict, List

from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce as AlpacaTimeInForce

from src.execution.base import (
    AccountInfo,
    ExecutionOrder,
    OrderExecutor,
    OrderStatus,
    OrderType,
    Position,
    TimeInForce,
)
from src.portfolio.base import Order, OrderAction
from src.utils.alpaca_client import AlpacaClient
from src.utils.exceptions import (
    BrokerConnectionError,
    OrderExecutionError,
    OrderRejectedError,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)


class AlpacaExecutor(OrderExecutor):
    """Alpaca Paper Trading executor.

    Implements OrderExecutor interface for submitting orders to Alpaca
    Paper Trading API.

    Example:
        >>> client = AlpacaClient.from_env()
        >>> executor = AlpacaExecutor(client)
        >>> orders = [Order(action=OrderAction.BUY, symbol='AAPL', shares=100, ...)]
        >>> results = executor.submit_orders(orders)
    """

    def __init__(self, alpaca_client: AlpacaClient):
        """Initialize Alpaca executor.

        Args:
            alpaca_client: AlpacaClient instance for API access
        """
        self.client = alpaca_client
        self.trading_client = alpaca_client.get_trading_client()
        logger.info("AlpacaExecutor initialized")

    def submit_orders(self, orders: List[Order]) -> List[ExecutionOrder]:
        """Submit orders to Alpaca Paper Trading API.

        Args:
            orders: List of Order objects from Portfolio Layer

        Returns:
            List of ExecutionOrder with execution status

        Raises:
            OrderExecutionError: If order submission fails
            OrderRejectedError: If broker rejects the order
        """
        if not orders:
            logger.info("No orders to submit")
            return []

        logger.info("Submitting %d orders to Alpaca", len(orders))
        execution_orders = []

        for order in orders:
            try:
                # Convert Portfolio Order to Alpaca MarketOrderRequest
                alpaca_order = self._convert_to_alpaca_order(order)

                # Submit order with retry logic
                submitted_order = self.client.with_retry(
                    self.trading_client.submit_order, alpaca_order
                )

                # Convert to ExecutionOrder
                execution_order = self._convert_to_execution_order(
                    submitted_order, order
                )

                execution_orders.append(execution_order)

                logger.info(
                    "Order submitted: %s %d shares of %s (order_id: %s)",
                    order.action.value,
                    order.shares,
                    order.symbol,
                    execution_order.order_id,
                )

            except Exception as e:
                # Create a rejected execution order
                error_msg = f"Failed to submit order for {order.symbol}: {e}"
                logger.error(error_msg)

                execution_order = ExecutionOrder(
                    order_id=f"rejected_{order.symbol}_{datetime.now().timestamp()}",
                    order=order,
                    status=OrderStatus.REJECTED,
                    rejected_reason=str(e),
                    submitted_at=datetime.now(),
                )
                execution_orders.append(execution_order)

        return execution_orders

    def get_order_status(self, order_ids: List[str]) -> List[ExecutionOrder]:
        """Query status of submitted orders.

        Args:
            order_ids: List of order IDs to query

        Returns:
            List of ExecutionOrder objects with current status

        Raises:
            BrokerConnectionError: If API query fails
        """
        if not order_ids:
            return []

        logger.info("Querying status for %d orders", len(order_ids))
        execution_orders = []

        for order_id in order_ids:
            try:
                # Fetch order from Alpaca
                alpaca_order = self.client.with_retry(
                    self.trading_client.get_order_by_id, order_id
                )

                # Convert to ExecutionOrder (without original Order object)
                execution_order = self._convert_alpaca_order_to_execution(alpaca_order)
                execution_orders.append(execution_order)

            except Exception as e:
                error_msg = f"Failed to get status for order {order_id}: {e}"
                logger.error(error_msg)
                # Continue with other orders

        return execution_orders

    def cancel_orders(self, order_ids: List[str]) -> Dict[str, bool]:
        """Cancel pending orders.

        Args:
            order_ids: List of order IDs to cancel

        Returns:
            Dict mapping order_id to success (True) or failure (False)
        """
        if not order_ids:
            return {}

        logger.info("Canceling %d orders", len(order_ids))
        results = {}

        for order_id in order_ids:
            try:
                self.client.with_retry(
                    self.trading_client.cancel_order_by_id, order_id
                )
                results[order_id] = True
                logger.info("Order %s canceled successfully", order_id)

            except Exception as e:
                logger.error("Failed to cancel order %s: %s", order_id, e)
                results[order_id] = False

        return results

    def get_positions(self) -> Dict[str, Position]:
        """Get current positions from Alpaca account.

        Returns:
            Dict mapping symbol to Position object

        Raises:
            BrokerConnectionError: If API query fails
        """
        try:
            # Fetch all positions
            alpaca_positions = self.client.with_retry(
                self.trading_client.get_all_positions
            )

            positions = {}
            for alpaca_pos in alpaca_positions:
                position = Position(
                    symbol=alpaca_pos.symbol,
                    shares=int(alpaca_pos.qty),
                    avg_cost=float(alpaca_pos.avg_entry_price),
                    market_value=float(alpaca_pos.market_value),
                    unrealized_pnl=float(alpaca_pos.unrealized_pl),
                    realized_pnl=0.0,  # Alpaca doesn't track realized P&L per position
                )
                positions[alpaca_pos.symbol] = position

            logger.info("Fetched %d positions from Alpaca", len(positions))
            return positions

        except Exception as e:
            error_msg = f"Failed to fetch positions: {e}"
            logger.error(error_msg)
            raise BrokerConnectionError(error_msg) from e

    def get_account_info(self) -> AccountInfo:
        """Get account balance and status from Alpaca.

        Returns:
            AccountInfo with cash, portfolio value, etc.

        Raises:
            BrokerConnectionError: If API query fails
        """
        try:
            # Fetch account info
            account = self.client.with_retry(self.trading_client.get_account)

            account_info = AccountInfo(
                cash=float(account.cash),
                portfolio_value=float(account.portfolio_value),
                buying_power=float(account.buying_power),
                positions_value=float(account.long_market_value),
                timestamp=datetime.now(),
            )

            logger.info(
                "Account info: cash=$%.2f, portfolio=$%.2f, buying_power=$%.2f",
                account_info.cash,
                account_info.portfolio_value,
                account_info.buying_power,
            )

            return account_info

        except Exception as e:
            error_msg = f"Failed to fetch account info: {e}"
            logger.error(error_msg)
            raise BrokerConnectionError(error_msg) from e

    def get_open_orders(self) -> List[ExecutionOrder]:
        """Get all orders that are not in a terminal state.

        Returns:
            List of open ExecutionOrder objects
        """
        try:
            # Fetch all open orders
            alpaca_orders = self.client.with_retry(
                self.trading_client.get_orders, filter={"status": "open"}
            )

            execution_orders = []
            for alpaca_order in alpaca_orders:
                execution_order = self._convert_alpaca_order_to_execution(alpaca_order)
                execution_orders.append(execution_order)

            logger.info("Fetched %d open orders", len(execution_orders))
            return execution_orders

        except Exception as e:
            logger.error("Failed to fetch open orders: %s", e)
            return []

    def _convert_to_alpaca_order(self, order: Order) -> MarketOrderRequest:
        """Convert Portfolio Order to Alpaca MarketOrderRequest.

        Args:
            order: Order from Portfolio Layer

        Returns:
            Alpaca MarketOrderRequest

        Raises:
            OrderExecutionError: If order conversion fails
        """
        try:
            # Determine order side
            side = (
                OrderSide.BUY if order.action == OrderAction.BUY else OrderSide.SELL
            )

            # Create market order request
            # (Limit orders can be added later if needed)
            alpaca_order = MarketOrderRequest(
                symbol=order.symbol,
                qty=order.shares,
                side=side,
                time_in_force=AlpacaTimeInForce.DAY,
            )

            return alpaca_order

        except Exception as e:
            error_msg = f"Failed to convert order to Alpaca format: {e}"
            logger.error(error_msg)
            raise OrderExecutionError(error_msg) from e

    def _convert_to_execution_order(
        self, alpaca_order, original_order: Order
    ) -> ExecutionOrder:
        """Convert Alpaca order to ExecutionOrder.

        Args:
            alpaca_order: Order object from Alpaca API
            original_order: Original Order from Portfolio Layer

        Returns:
            ExecutionOrder with execution details
        """
        # Map Alpaca status to OrderStatus
        status = self._map_alpaca_status(alpaca_order.status)

        # Parse filled quantity and price
        filled_qty = int(alpaca_order.filled_qty or 0)
        filled_avg_price = float(alpaca_order.filled_avg_price or 0.0)

        # Parse timestamps
        submitted_at = alpaca_order.submitted_at
        filled_at = alpaca_order.filled_at

        # Remove timezone info if present
        if submitted_at and submitted_at.tzinfo is not None:
            submitted_at = submitted_at.replace(tzinfo=None)
        if filled_at and filled_at.tzinfo is not None:
            filled_at = filled_at.replace(tzinfo=None)

        return ExecutionOrder(
            order_id=str(alpaca_order.id),
            order=original_order,
            order_type=OrderType.MARKET,  # Currently only market orders
            status=status,
            filled_qty=filled_qty,
            filled_avg_price=filled_avg_price,
            commission=0.0,  # Alpaca doesn't charge commissions
            submitted_at=submitted_at,
            filled_at=filled_at,
            rejected_reason="",
        )

    def _convert_alpaca_order_to_execution(self, alpaca_order) -> ExecutionOrder:
        """Convert Alpaca order to ExecutionOrder (without original Order).

        Used when querying order status without the original Portfolio Order.

        Args:
            alpaca_order: Order object from Alpaca API

        Returns:
            ExecutionOrder (with placeholder original order)
        """
        # Create placeholder Order
        action = (
            OrderAction.BUY
            if alpaca_order.side == OrderSide.BUY
            else OrderAction.SELL
        )

        original_order = Order(
            action=action,
            symbol=alpaca_order.symbol,
            shares=int(alpaca_order.qty),
            estimated_value=float(alpaca_order.notional or 0.0),
            reason="Queried from Alpaca",
        )

        return self._convert_to_execution_order(alpaca_order, original_order)

    def _map_alpaca_status(self, alpaca_status: str) -> OrderStatus:
        """Map Alpaca order status to OrderStatus enum.

        Args:
            alpaca_status: Status string from Alpaca

        Returns:
            OrderStatus enum value
        """
        # Alpaca status values:
        # new, partially_filled, filled, done_for_day, canceled,
        # expired, replaced, pending_cancel, pending_replace,
        # accepted, pending_new, accepted_for_bidding, stopped, rejected, suspended, calculated

        status_map = {
            "new": OrderStatus.SUBMITTED,
            "accepted": OrderStatus.SUBMITTED,
            "pending_new": OrderStatus.PENDING,
            "partially_filled": OrderStatus.PARTIALLY_FILLED,
            "filled": OrderStatus.FILLED,
            "canceled": OrderStatus.CANCELLED,
            "expired": OrderStatus.EXPIRED,
            "rejected": OrderStatus.REJECTED,
            "replaced": OrderStatus.CANCELLED,
            "pending_cancel": OrderStatus.SUBMITTED,
            "pending_replace": OrderStatus.SUBMITTED,
        }

        return status_map.get(alpaca_status, OrderStatus.PENDING)
