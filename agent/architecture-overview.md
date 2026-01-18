# Architecture Overview

## System Architecture

The AI Trader system follows a **layered architecture** with clear separation of concerns. Each layer communicates through well-defined interfaces, enabling independent development and testing.

### High-Level Layer Diagram

```mermaid
graph TB
    subgraph External["External Services"]
        Market[Market Data<br/>yfinance/Alpaca/IB]
        Broker[Broker API<br/>Alpaca/IB]
    end

    subgraph Core["AI Trader System"]
        Data[Data Layer<br/>Market Data + Storage]
        Strategy[Strategy Layer<br/>Signal Generation]
        Portfolio[Portfolio Management<br/>Allocation & Rebalancing]
        Risk[Risk Management<br/>Validation & Monitoring]
        Execution[Execution Layer<br/>Order Management]
        Scheduler[Task Scheduler<br/>APScheduler]
    end

    subgraph Storage["Persistent Storage"]
        DB[(SQLite Database<br/>Prices, Signals, Results)]
    end

    Market -->|Historical/Live Data| Data
    Data -->|Price Data| Strategy
    Data <-->|Read/Write| DB
    Strategy -->|Signals| Portfolio
    Strategy -->|Signal History| DB
    Portfolio -->|Target Allocations| Risk
    Risk -->|Approved Orders| Execution
    Execution -->|Order Submission| Broker
    Broker -->|Fill Confirmation| Execution
    Execution -->|Position Updates| Portfolio
    Execution -->|Trade History| DB
    Scheduler -.->|Triggers| Data
    Scheduler -.->|Triggers| Strategy
    Scheduler -.->|Triggers| Portfolio

    classDef layerStyle fill:#e1f5ff,stroke:#0066cc,stroke-width:2px
    classDef externalStyle fill:#fff4e6,stroke:#ff9800,stroke-width:2px
    classDef storageStyle fill:#f3e5f5,stroke:#9c27b0,stroke-width:2px

    class Data,Strategy,Portfolio,Risk,Execution,Scheduler layerStyle
    class Market,Broker externalStyle
    class DB storageStyle
```

## Data Flow

### Daily Trading Workflow

```mermaid
sequenceDiagram
    participant S as Scheduler
    participant D as Data Layer
    participant ST as Strategy Layer
    participant P as Portfolio Manager
    participant R as Risk Manager
    participant E as Execution Layer
    participant B as Broker
    participant DB as SQLite DB

    Note over S: Daily 16:30 (Post-Market)
    Note over S: Task Chain: Data → Signal → Portfolio

    S->>D: Trigger data update job
    D->>D: Fetch latest market data
    D->>DB: Store daily prices
    D-->>S: Data update complete

    Note over S: Wait for data job completion
    S->>ST: Trigger signal generation job
    ST->>DB: Load historical prices
    ST->>ST: Calculate indicators (TA-Lib)
    ST->>ST: Generate signals [-1.0, 1.0]
    ST->>DB: Store signals
    ST-->>S: Signal generation complete

    Note over S: Wait for signal job completion
    S->>P: Trigger portfolio rebalancing job
    alt Rebalancing Day
        P->>DB: Load current positions
        P->>DB: Load latest signals
        P->>P: Calculate target allocations
        P->>R: Submit target positions

        R->>R: Validate position limits
        R->>R: Check cash reserves
        R->>R: Apply stop-loss rules

        alt Risk Checks Pass
            R->>E: Approve orders
            E->>E: Generate order objects
            E->>B: Submit orders
            B-->>E: Fill confirmation
            E->>DB: Log trades
            E->>P: Update positions
        else Risk Checks Fail
            R->>P: Reject with reason
            P->>DB: Log rejection
        end
    end
```

**Task Dependency Chain**:
- APScheduler orchestrates tasks with explicit dependencies
- Each task waits for previous task completion before execution
- Prevents race conditions and ensures data consistency
- Failed tasks halt the chain and trigger alerts

## Module Dependencies

### Layer Dependency Graph

```mermaid
graph LR
    subgraph Layer_1["Layer 1: Foundation"]
        Data[Data Layer]
        Storage[SQLite Storage]
    end

    subgraph Layer_2["Layer 2: Intelligence"]
        Strategy[Strategy Layer]
    end

    subgraph Layer_3["Layer 3: Decision"]
        Portfolio[Portfolio Manager]
    end

    subgraph Layer_4["Layer 4: Control"]
        Risk[Risk Manager]
    end

    subgraph Layer_5["Layer 5: Action"]
        Execution[Execution Layer]
    end

    subgraph Layer_0["Layer 0: Orchestration"]
        Scheduler[APScheduler]
    end

    Data --> Strategy
    Storage --> Data
    Storage --> Strategy
    Storage --> Portfolio
    Storage --> Execution
    Strategy --> Portfolio
    Portfolio --> Risk
    Risk --> Execution
    Scheduler -.-> Data
    Scheduler -.-> Strategy
    Scheduler -.-> Portfolio

    classDef foundationStyle fill:#e8f5e9,stroke:#4caf50,stroke-width:2px
    classDef intelligenceStyle fill:#e3f2fd,stroke:#2196f3,stroke-width:2px
    classDef decisionStyle fill:#fff3e0,stroke:#ff9800,stroke-width:2px
    classDef controlStyle fill:#fce4ec,stroke:#e91e63,stroke-width:2px
    classDef actionStyle fill:#f3e5f5,stroke:#9c27b0,stroke-width:2px
    classDef orchestrationStyle fill:#eceff1,stroke:#607d8b,stroke-width:2px

    class Data,Storage foundationStyle
    class Strategy intelligenceStyle
    class Portfolio decisionStyle
    class Risk controlStyle
    class Execution actionStyle
    class Scheduler orchestrationStyle
```

## Core Interfaces

### 1. Data Provider Interface

```python
class DataProvider(ABC):
    """Abstract interface for market data providers."""

    @abstractmethod
    def get_historical_bars(
        self,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime,
        timeframe: str = "1D"
    ) -> pd.DataFrame:
        """Fetch historical OHLCV data."""
        pass

    @abstractmethod
    def get_latest_quote(self, symbols: List[str]) -> pd.DataFrame:
        """Get latest quotes for symbols."""
        pass
```

**Implementations**: `YFinanceProvider`, `AlpacaProvider`, `IBProvider`

### 2. Strategy Interface

```python
class Strategy(ABC):
    """Abstract base for trading strategies."""

    @abstractmethod
    def generate_signals(
        self,
        price_data: pd.DataFrame,
        lookback_days: int = 252
    ) -> Dict[str, float]:
        """
        Generate trading signals.

        Returns:
            Dict mapping symbol -> signal strength [-1.0, 1.0]
            -1.0 = Strong Sell, 0.0 = Neutral, +1.0 = Strong Buy
        """
        pass
```

**Implementations**: `MACrossoverStrategy`, `MomentumStrategy`, `MultiFactorStrategy`

### 3. Portfolio Manager Interface

```python
class PortfolioManager(ABC):
    """Abstract interface for portfolio allocation."""

    @abstractmethod
    def calculate_target_positions(
        self,
        signals: Dict[str, float],
        current_positions: Dict[str, int],
        account_value: float
    ) -> Dict[str, int]:
        """
        Convert signals to target share quantities.

        Returns:
            Dict mapping symbol -> target share quantity
        """
        pass
```

**Implementations**: `HeuristicAllocator`, `RiskParityAllocator`, `BlackLittermanAllocator`

### 4. Risk Manager Interface

```python
class RiskManager(ABC):
    """Abstract interface for risk control."""

    @abstractmethod
    def validate_orders(
        self,
        proposed_orders: List[Order],
        current_positions: Dict[str, Position],
        account_info: AccountInfo
    ) -> Tuple[List[Order], List[Order]]:
        """
        Validate proposed orders against risk limits.

        Returns:
            (approved_orders, rejected_orders)
        """
        pass
```

**Implementations**: `BasicRiskManager`, `DynamicRiskManager`, `AdvancedRiskManager`

### 5. Order Executor Interface

```python
class OrderExecutor(ABC):
    """Abstract interface for order execution."""

    @abstractmethod
    def submit_orders(self, orders: List[Order]) -> List[OrderStatus]:
        """Submit orders for execution."""
        pass

    @abstractmethod
    def get_positions(self) -> Dict[str, Position]:
        """Get current positions."""
        pass
```

**Implementations**: `BacktestExecutor`, `PaperTradingExecutor`, `LiveTradingExecutor`

## Execution Modes

The system supports three execution modes through abstraction:

```mermaid
graph TD
    Config[Configuration File]

    Config -->|mode: backtest| Backtest[BacktestExecutor<br/>Historical Simulation]
    Config -->|mode: paper| Paper[PaperTradingExecutor<br/>Alpaca Paper Trading]
    Config -->|mode: live| Live[LiveTradingExecutor<br/>Alpaca Live Trading]

    Backtest -->|Historical Prices| Data1[Historical Data]
    Paper -->|Real-time Quotes| Data2[Live Market Data]
    Live -->|Real-time Quotes| Data3[Live Market Data]

    Backtest -->|Simulated Fills| Portfolio
    Paper -->|Simulated Fills| Portfolio
    Live -->|Real Fills| Portfolio

    classDef configStyle fill:#fff9c4,stroke:#fbc02d,stroke-width:2px
    classDef backtestStyle fill:#e1f5ff,stroke:#0066cc,stroke-width:2px
    classDef paperStyle fill:#e8f5e9,stroke:#4caf50,stroke-width:2px
    classDef liveStyle fill:#ffebee,stroke:#f44336,stroke-width:2px

    class Config configStyle
    class Backtest backtestStyle
    class Paper paperStyle
    class Live liveStyle
```

**Mode Switching**: Configuration-driven, no code changes required.

## Implementation Roadmap

The system will be built in three progressive phases, each building on the previous phase's foundation. See [development-plan.md](development-plan.md) for detailed timeline, task breakdown, and progress tracking.

### Phase 1: Backtesting Foundation (Current Focus)

**Goal**: Complete backtesting system with historical data

**Key Deliverables**:
- Data Layer: YFinance provider, SQLite storage, data quality validation
- Strategy Layer: TA-Lib integration, MA Crossover strategy, signal generation
- Portfolio Layer: Heuristic allocation, weekly/monthly rebalancing
- Risk Layer: Position limits, cash reserve checks, basic stop-loss
- Execution Layer: Backtest executor, VectorBT integration
- User Interface: Python APIs, CLI tools, Jupyter notebooks, visualization

**Success Criteria**: End-to-end backtest runs on 1-year historical data with performance metrics

### Phase 2: Paper Trading

**Goal**: Real-time paper trading with Alpaca API

**Key Deliverables**:
- Real-time data streaming from Alpaca
- Enhanced portfolio allocation (risk-adjusted)
- Dynamic stop-loss/take-profit
- Paper trading execution with order tracking
- Real-time monitoring and alerts

**Success Criteria**: System runs autonomously in paper trading mode for 2+ weeks without errors

### Phase 3: Production

**Goal**: Live trading with advanced features and production-grade infrastructure

**Key Deliverables**:
- Alpaca Live Trading integration
- Advanced risk management (VaR, CVaR, drawdown protection)
- Portfolio optimization (Black-Litterman, Markowitz)
- QuantStats comprehensive reporting
- Production monitoring, alerting, and disaster recovery

**Success Criteria**: System handles live trading with comprehensive risk controls and monitoring

## Configuration Management

### Centralized Configuration

All system behavior is controlled through a single YAML configuration file:

```yaml
# config/config.yaml

# Execution Mode
execution:
  mode: "backtest"  # Options: backtest, paper, live
  provider: "alpaca"

# Data Provider
data:
  provider: "yfinance"  # Options: yfinance, alpaca, ib
  storage: "sqlite"
  db_path: "data/market_data.db"

# Strategy
strategy:
  type: "ma_crossover"
  parameters:
    fast_period: 50
    slow_period: 200
    universe: ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"]

# Portfolio Management
portfolio:
  allocator: "heuristic"
  max_positions: 10
  cash_reserve: 0.05  # 5% cash reserve

# Risk Management
risk:
  max_position_size: 0.20  # 20% max per position
  max_total_exposure: 0.95  # 95% max total exposure
  stop_loss_pct: 0.10  # 10% stop-loss

# Scheduling
scheduling:
  data_update_time: "16:30"  # Daily post-market
  rebalance_frequency: "weekly"  # Options: daily, weekly, monthly
```

**Benefits**:
- Single source of truth
- Environment-specific configs (dev, staging, prod)
- No code changes for parameter tuning
- Easy A/B testing of strategies

## Technology Stack Summary

| Layer | Component | Technology |
|-------|-----------|------------|
| **Data** | Market Data | yfinance → Alpaca → IB |
| **Data** | Storage | SQLite + Pandas |
| **Strategy** | Indicators | TA-Lib (primary), pandas-ta (supplement) |
| **Strategy** | Framework | Multi-Factor Portfolio Strategy |
| **Portfolio** | Allocation | Custom (Phase 1) → PyPortfolioOpt (Phase 2-3) |
| **Risk** | Validation | Custom Rules |
| **Risk** | Analytics | QuantStats (Phase 3) |
| **Execution** | Backtesting | VectorBT |
| **Execution** | Paper Trading | Alpaca Paper API |
| **Execution** | Live Trading | Alpaca Live API |
| **Orchestration** | Scheduling | APScheduler |

## Design Principles

1. **Separation of Concerns**: Each layer has a single, well-defined responsibility
2. **Interface Abstraction**: All external dependencies are abstracted behind interfaces
3. **Configuration over Code**: Behavior controlled through configuration files
4. **Progressive Enhancement**: Start simple (Phase 1), add complexity as validated
5. **Data Integrity**: All trades, signals, and results are logged to SQLite
6. **Testability**: Each layer can be tested independently with mocks
7. **Performance**: Leverage compiled libraries (TA-Lib, NumPy, VectorBT) for speed

## Key Architectural Decisions

### 1. Why Layered Architecture?

- **Testability**: Each layer can be unit tested independently
- **Replaceability**: Swap implementations without affecting other layers
- **Clear Ownership**: Each layer has a single responsibility
- **Progressive Development**: Build and validate layer by layer

### 2. Why SQLite for Phase 1?

- Zero configuration, immediate productivity
- Sufficient for daily data (millions of rows)
- Audit trail for all trading decisions
- Easy migration to PostgreSQL if needed

### 3. Why VectorBT for Backtesting?

- 100-1000x faster than event-driven frameworks
- Multi-factor strategies require testing many parameter combinations
- Modern Python, excellent Pandas integration

### 4. Why Configuration-Driven Execution?

- Switch between backtest/paper/live without code changes
- Environment-specific configurations (dev/staging/prod)
- Easy parameter tuning and A/B testing

### 5. Why Independent Risk Layer?

- Strategy Layer focuses on signal generation (what to buy/sell)
- Risk Layer enforces limits (how much, when to exit)
- Separation prevents strategies from bypassing risk controls

## Error Handling and Resilience

### Error Handling Strategy

```mermaid
graph TD
    Error[Error Detected]

    Error -->|Data Error| D[Data Layer]
    Error -->|Strategy Error| S[Strategy Layer]
    Error -->|Execution Error| E[Execution Layer]

    D -->|API Failure| D1[Retry with backoff]
    D -->|Data Quality Issue| D2[Log and skip bar]

    S -->|Calculation Error| S1[Log and use previous signal]
    S -->|Invalid Signal| S2[Default to neutral 0.0]

    E -->|Order Rejected| E1[Log and notify]
    E -->|Partial Fill| E2[Accept or cancel remainder]
    E -->|Broker Outage| E3[Circuit breaker: halt trading]

    D1 --> Log[Centralized Logging]
    D2 --> Log
    S1 --> Log
    S2 --> Log
    E1 --> Log
    E2 --> Log
    E3 --> Alert[Alert System]
```

### Circuit Breakers

- **Data Layer**: Max 3 retries with exponential backoff
- **Execution Layer**: Halt trading after 5 consecutive order rejections
- **Risk Layer**: Emergency liquidation if drawdown > 20%

### System Safety and Fail-Safe Mechanisms

The system employs a "Fail-Safe" philosophy to protect capital during anomalies:

1.  **Fail-Safe Defaults**: If data is missing or invalid, the system defaults to **Hold/Do Nothing**. It never guesses.
2.  **Harm Minimization**: Prioritize preventing new bad trades over forcing exits on uncertain data.
3.  **Data Validation (Gatekeeper)**: Strict validation (calendar check, price integrity) blocks invalid data from entering the Strategy Layer.
4.  **Operational Safety**: Automated alerts and manual kill-switches for critical system failures.

See [system-safety-design.md](system-safety-design.md) for detailed protocols.

## Monitoring and Observability

### Key Metrics (Phase 3)

- **Performance**: Sharpe Ratio, Sortino Ratio, Max Drawdown
- **System Health**: API latency, order fill rate, data freshness
- **Risk Metrics**: VaR, CVaR, position concentration
- **Trading Activity**: Daily PnL, trade count, turnover

### Logging Strategy

```python
# Structured logging for all layers
logger.info("signal_generated", extra={
    "symbol": "AAPL",
    "signal": 0.75,
    "strategy": "ma_crossover",
    "timestamp": datetime.now().isoformat()
})
```

## Related Documents

- [tech-stack.md](tech-stack.md) - Technology decisions and rationale
- [development-plan.md](development-plan.md) - Project timeline, milestones, and progress tracking
- [data-layer-design.md](data-layer-design.md) - Data acquisition and storage
- [strategy-layer-design.md](strategy-layer-design.md) - Strategy framework
- [portfolio-management-design.md](portfolio-management-design.md) - Portfolio allocation
- [risk-management-design.md](risk-management-design.md) - Risk control
- [execution-layer-design.md](execution-layer-design.md) - Order execution
- [user-interface-design.md](user-interface-design.md) - Python APIs, CLI tools, Jupyter integration
- [development-guidelines.md](development-guidelines.md) - Coding standards
- [system-safety-design.md](system-safety-design.md) - System safety and fail-safe protocols
