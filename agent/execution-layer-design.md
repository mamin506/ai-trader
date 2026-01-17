# Execution Layer Design

## Overview

The Execution Layer is responsible for converting Portfolio Manager's target allocations into actual market orders. It sits between the Risk Management Layer and the broker/market, handling order routing, execution strategies, and order state management.

**Key Principle**: Abstract the execution mechanism to support multiple execution modes (backtesting, paper trading, live trading) through a unified interface.

## Execution Modes

The system will support three execution modes through abstraction:

### 1. Backtesting Executor
- **Purpose**: Historical simulation for strategy validation
- **Data Source**: Historical price data (from Data Layer)
- **Order Execution**: Instantaneous fill at historical prices
- **Slippage**: Configurable slippage model (percentage-based or fixed)
- **Commissions**: Configurable commission structure
- **Market Impact**: Optional market impact modeling
- **Use Case**: Phase 1 strategy validation before risking capital

### 2. Paper Trading Executor
- **Purpose**: Real-time simulation with live market data
- **Data Source**: Live market data (real-time quotes)
- **Order Execution**: Simulated fills at live market prices
- **Risk**: Zero financial risk, fully simulated
- **Recommended Provider**: Alpaca Paper Trading API
- **Use Case**: Phase 2 validation after backtesting, before live trading

**Alpaca Paper Trading Benefits**:
- Free tier with real-time data
- API identical to live trading (smooth migration path)
- Full order type support (market, limit, stop, stop-limit)
- Instant account setup, no broker approval needed
- Realistic simulation environment

### 3. Live Trading Executor
- **Purpose**: Production trading with real capital
- **Data Source**: Live market data
- **Order Execution**: Actual broker execution
- **Risk**: Real financial risk
- **Recommended Providers**: Alpaca API (initial), Interactive Brokers (advanced)
- **Use Case**: Phase 3 production deployment after paper trading validation

## Abstraction Design

### Core Interface: `OrderExecutor`

All execution modes implement a common interface:

```python
class OrderExecutor(ABC):
    """Abstract base class for order execution."""

    @abstractmethod
    def submit_orders(self, orders: List[Order]) -> List[OrderStatus]:
        """
        Submit a batch of orders for execution.

        Args:
            orders: List of Order objects from Portfolio Manager

        Returns:
            List of OrderStatus objects with execution results
        """
        pass

    @abstractmethod
    def get_order_status(self, order_ids: List[str]) -> List[OrderStatus]:
        """Query status of submitted orders."""
        pass

    @abstractmethod
    def cancel_orders(self, order_ids: List[str]) -> List[bool]:
        """Cancel pending orders."""
        pass

    @abstractmethod
    def get_positions(self) -> Dict[str, Position]:
        """Get current positions."""
        pass

    @abstractmethod
    def get_account_info(self) -> AccountInfo:
        """Get account balance, buying power, etc."""
        pass
```

### Configuration-Based Switching

```python
# config.yaml
execution:
  mode: "paper"  # Options: backtest, paper, live
  provider: "alpaca"  # Options: alpaca, ib

  alpaca:
    api_key: "${ALPACA_API_KEY}"
    api_secret: "${ALPACA_API_SECRET}"
    paper: true  # true for paper trading, false for live

  backtest:
    slippage: 0.001  # 0.1% slippage
    commission: 0.0  # $0 commission (Alpaca is zero-commission)
```

## Order Types

### Phase 1 Support (Minimum Viable)
- **Market Orders**: Immediate execution at current market price
- **Limit Orders**: Execute only at specified price or better

### Phase 2 Enhancement
- **Stop-Loss Orders**: Trigger market order when price reaches stop level
- **Stop-Limit Orders**: Trigger limit order at stop level
- **Bracket Orders**: Combined entry + stop-loss + take-profit

### Phase 3 Advanced
- **TWAP (Time-Weighted Average Price)**: Split large orders over time
- **VWAP (Volume-Weighted Average Price)**: Execute based on volume profile
- **Iceberg Orders**: Display only portion of full order size

## Order Lifecycle Management

### State Diagram
```
PENDING → SUBMITTED → PARTIALLY_FILLED → FILLED
                   ↘ REJECTED
                   ↘ CANCELLED
```

### State Tracking
- **PENDING**: Created by Portfolio Manager, not yet submitted
- **SUBMITTED**: Sent to broker/executor, awaiting fill
- **PARTIALLY_FILLED**: Partial execution (relevant for large orders)
- **FILLED**: Fully executed
- **REJECTED**: Broker rejected (insufficient funds, invalid symbol, etc.)
- **CANCELLED**: User/system cancellation

## Error Handling

### Pre-Submission Validation
- **Symbol Validation**: Ensure tradable symbol
- **Quantity Validation**: Meet broker lot size requirements
- **Price Validation**: Limit prices within reasonable bounds
- **Buying Power Check**: Ensure sufficient cash/margin

### Execution Failure Handling
- **Rejection Handling**: Log reason, notify Risk Manager
- **Retry Logic**: Configurable retry for transient failures
- **Partial Fill Handling**: Accept partial fills or cancel remainder
- **Circuit Breaker**: Halt trading on repeated failures

## Integration with Other Layers

### Input: Portfolio Manager
```python
# Portfolio Manager generates target allocations
target_positions = {
    "AAPL": 10,   # Target 10 shares of AAPL
    "MSFT": 5,    # Target 5 shares of MSFT
    "GOOGL": 0    # Close GOOGL position
}

# Execution Layer converts to orders
orders = execution_layer.generate_orders(
    current_positions=current_positions,
    target_positions=target_positions
)
```

### Output: Position Updates
```python
# After execution, update portfolio state
filled_orders = executor.get_filled_orders()
portfolio_manager.update_positions(filled_orders)
```

### Risk Management Integration
- Risk Manager approves orders before submission
- Real-time position monitoring during execution
- Emergency liquidation capability for circuit breakers

## Implementation Phases

### Phase 1: Backtesting (Immediate Priority)
- Implement `BacktestExecutor` with historical data
- Simple slippage model (percentage-based)
- Market orders only
- **Goal**: Validate strategy through historical simulation

### Phase 2: Paper Trading (Post-Backtest Validation)
- Implement `AlpacaPaperExecutor` using Alpaca Paper Trading API
- Real-time order submission and monitoring
- Support market and limit orders
- **Goal**: Real-time validation with zero financial risk

### Phase 3: Live Trading (Production)
- Implement `AlpacaLiveExecutor` for production trading
- Full order type support (stop-loss, bracket orders)
- Advanced execution strategies (TWAP, VWAP)
- **Goal**: Production deployment with real capital

## Technical Stack Decisions

### Primary Provider: Alpaca
**Rationale**:
- **Zero commissions**: No per-trade cost overhead
- **Unified API**: Identical interface for paper and live trading
- **Developer-friendly**: REST API + Python SDK, excellent documentation
- **Paper trading**: Free tier with realistic simulation
- **Real-time data**: WebSocket streaming for live quotes
- **Ease of setup**: Minutes to create account and start paper trading

### Alternative Provider: Interactive Brokers
**When to Consider**:
- Phase 3 optimization for large-scale trading
- Need for advanced order types (algorithmic orders, multi-leg options)
- Global market access (non-US equities, forex, futures)
- Professional-grade execution analytics

**Trade-offs**:
- More complex API (ibapi Python wrapper)
- Steeper learning curve
- Higher account minimums
- More suitable for advanced/institutional use

### Migration Path
1. **Phase 1**: Backtesting with synthetic executor
2. **Phase 2**: Alpaca Paper Trading API
3. **Phase 2.5**: Alpaca Live Trading (small capital)
4. **Phase 3** (Optional): Migrate to IB if requirements demand it

## Key Design Principles

1. **Mode-Agnostic Code**: Portfolio and Risk layers should not know execution mode
2. **Configuration-Driven**: Switch modes via config file, not code changes
3. **Realistic Simulation**: Paper trading should mirror live trading behavior
4. **Graceful Degradation**: Handle broker outages, market closures
5. **Audit Trail**: Log all orders, fills, rejections for post-mortem analysis

## Implementation Deferred

As discussed, **execution layer implementation is deferred until after backtesting validation**. The strategy validation workflow is:

```
Backtesting (Phase 1) → Paper Trading (Phase 2) → Live Trading (Phase 3)
```

This document serves as the design blueprint for when execution layer implementation begins in Phase 2.

## Related Documents

- [tech-stack.md](tech-stack.md) - Technology stack decisions
- [architecture-overview.md](architecture-overview.md) - Overall system architecture
- [risk-management-design.md](risk-management-design.md) - Risk controls before execution
- [portfolio-management-design.md](portfolio-management-design.md) - Source of target allocations
