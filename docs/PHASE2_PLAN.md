# Phase 2: Paper Trading Implementation Plan

**Status**: 🚀 Ready to Start
**Timeline**: 3-4 weeks (estimated)
**Agents**: 2 parallel agents (Agent A: Integration, Agent B: Core Logic)
**Started**: 2026-01-31
**Target Completion**: 2026-02-28

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Technical Decisions](#technical-decisions)
3. [Module Breakdown](#module-breakdown)
4. [Agent Task Assignment](#agent-task-assignment)
5. [Interface Contracts](#interface-contracts)
6. [Git Workflow](#git-workflow)
7. [Dependencies](#dependencies)
8. [Acceptance Criteria](#acceptance-criteria)
9. [Timeline](#timeline)
10. [Progress Tracking](#progress-tracking)

---

## Overview

### Phase 2 Goal
Transform the backtesting system into a live paper trading system with:
- Alpaca Paper Trading API integration
- Daily rebalancing workflow
- Intraday risk monitoring (no intraday trading)
- Real-time position and performance tracking
- CLI monitoring tools

### Key Principles
- **Daily Rebalancing**: Execute portfolio rebalancing once per day (3:45 PM ET)
- **Intraday Monitoring**: Monitor positions for stop-loss/take-profit triggers during market hours
- **No Intraday Trading**: Signals generated only once per day (keep it simple)
- **CLI First**: Build CLI tools, leverage Alpaca's web dashboard for visualization
- **Test-Driven**: Maintain >80% test coverage
- **YAGNI**: Implement only what's needed for paper trading

### Success Criteria
Phase 2 is complete when:
- ✅ System can execute daily paper trades via Alpaca
- ✅ Intraday risk monitoring detects and executes stop-loss/take-profit
- ✅ APScheduler runs daily workflow reliably
- ✅ CLI tools provide real-time monitoring
- ✅ 1-2 weeks of paper trading validation successful
- ✅ Unit test coverage >80%
- ✅ Documentation complete

---

## Technical Decisions

### 1. Trading Frequency
**Decision**: Daily Rebalancing + Intraday Risk Monitoring

**Rationale**:
- **Daily Rebalancing**:
  - Aligns with Phase 1 backtesting (already validated)
  - Lower transaction costs
  - Simpler implementation
  - Suitable for trend-following strategies (MA Crossover)

- **Intraday Risk Monitoring**:
  - Protects against large losses (stop-loss triggers)
  - Captures profit targets (take-profit triggers)
  - No active signal generation (monitoring only)
  - Minimal complexity increase

**Alternative Considered**: Full intraday trading (rejected - too complex for Phase 2)

### 2. Real-time Data Strategy
**Decision**: REST API polling (no WebSocket streaming)

**Rationale**:
- Daily rebalancing only needs EOD prices
- Intraday monitoring can poll every 1-5 minutes (sufficient for stop-loss)
- Simpler implementation (no WebSocket complexity)
- Alpaca free tier supports REST API well

**Note**: WebSocket streaming deferred to Phase 3 (if needed for true intraday trading)

### 3. Scheduler Architecture
**Decision**: APScheduler with explicit task dependency chains

**Rationale**:
- Same design as Phase 1 architecture
- Cron-based scheduling for market hours
- Task dependencies prevent race conditions
- Built-in retry and error handling

### 4. Configuration Management
**Decision**: Environment variables (.env) + YAML config files

**Rationale**:
- Sensitive data (API keys) in `.env` (not committed)
- Non-sensitive config in `config/alpaca.yaml` (committed)
- Consistent with Phase 1 approach

---

## Module Breakdown

### Module 0: Configuration & Setup (Agent B)
**Purpose**: Set up configuration infrastructure for Alpaca integration

**Components**:
- `.env` credentials (✅ already created by user)
- `config/alpaca.yaml` - Alpaca-specific config
- `.env.example` - Template for other developers
- Update `requirements.txt` - Add Alpaca SDK

**Deliverables**:
- [x] `.env` file created and configured
- [ ] `config/alpaca.yaml` created
- [ ] `.env.example` template created
- [ ] `requirements.txt` updated with Alpaca SDK
- [ ] Configuration loader updated to read Alpaca config

**Estimated Time**: 1 day
**Dependencies**: None
**Branch**: `phase2/agent-b/config-setup`

---

### Module 1: Alpaca API Integration (Agent A)
**Purpose**: Implement Alpaca data provider and order executor

**Components**:
1. **AlpacaProvider** (`src/data/providers/alpaca_provider.py`)
   - Extends `DataProvider` interface
   - Fetch historical daily bars via REST API
   - Fetch latest quotes for current prices
   - Trading calendar integration

2. **AlpacaExecutor** (`src/execution/alpaca_executor.py`)
   - Extends `OrderExecutor` interface
   - Submit market orders via Paper Trading API
   - Query account info and positions
   - Track order status and fills

3. **Alpaca API Client** (`src/utils/alpaca_client.py`)
   - Authentication and connection management
   - Rate limiting and error handling
   - Retry logic for API failures

**Deliverables**:
- [ ] `AlpacaProvider` implementation
- [ ] `AlpacaExecutor` implementation
- [ ] `AlpacaClient` utility class
- [ ] Unit tests (mock API responses)
- [ ] Integration tests (use Paper Trading account)

**Estimated Time**: 3-4 days
**Dependencies**: Module 0 (config setup)
**Branch**: `phase2/agent-a/alpaca-integration`

**Interface Contract**: See [Interface Contracts](#interface-contracts) section

---

### Module 2: APScheduler Orchestration (Agent A)
**Purpose**: Implement daily workflow scheduling and task coordination

**Components**:
1. **Scheduler** (`src/orchestration/scheduler.py`)
   - APScheduler integration
   - Market hours awareness (9:30 AM - 4:00 PM ET)
   - Task registration and dependency management
   - Error handling and circuit breakers

2. **Daily Workflow** (`src/orchestration/workflows.py`)
   - **Market Open Workflow** (9:30 AM):
     - Health check (API connection, account status)
     - Fetch overnight news/events (future)

   - **Rebalancing Workflow** (3:45 PM):
     - Fetch latest daily data
     - Generate signals (Strategy Layer)
     - Calculate allocations (Portfolio Layer)
     - Validate risk (Risk Layer)
     - Submit orders (Execution Layer)
     - Log results

   - **Market Close Workflow** (4:05 PM):
     - Confirm all orders filled
     - Update position tracking
     - Generate daily performance report

3. **Task Dependency Chain**:
   ```
   Data Fetch → Signal Generation → Portfolio Allocation → Risk Validation → Order Execution
   ```

**Deliverables**:
- [ ] `Scheduler` implementation with APScheduler
- [ ] `DailyWorkflow` orchestrator
- [ ] Market hours detection (NYSE calendar)
- [ ] Task dependency chain implementation
- [ ] Unit tests (time-mocked)
- [ ] Integration tests (dry-run workflow)

**Estimated Time**: 4-5 days
**Dependencies**: Module 1 (AlpacaProvider, AlpacaExecutor)
**Branch**: `phase2/agent-a/scheduler`

---

### Module 3: Dynamic Risk Management (Agent B)
**Purpose**: Real-time position monitoring and risk protection

**Components**:
1. **DynamicRiskManager** (`src/risk/dynamic_risk_manager.py`)
   - Extends `RiskManager` interface
   - Real-time stop-loss monitoring
   - Take-profit target monitoring
   - Trailing stop-loss (optional)
   - Drawdown circuit breaker

2. **Position Monitor** (`src/risk/monitors.py`)
   - **PositionMonitor**: Track individual positions
     - Entry price, current price, P&L
     - Stop-loss threshold (e.g., -3%)
     - Take-profit threshold (e.g., +10%)
     - Check interval: 1-5 minutes

   - **PortfolioMonitor**: Track portfolio-level risk
     - Total portfolio drawdown (e.g., -5% from peak)
     - Daily loss limit (e.g., -2% per day)
     - Exposure limits

3. **Risk Actions**:
   - Trigger exit signal when stop-loss hit
   - Submit market order to close position
   - Log risk event for analysis

**Deliverables**:
- [ ] `DynamicRiskManager` implementation
- [ ] `PositionMonitor` class
- [ ] `PortfolioMonitor` class
- [ ] Stop-loss/take-profit logic
- [ ] Circuit breaker logic
- [ ] Unit tests (price simulation)
- [ ] Integration tests (historical replay)

**Estimated Time**: 3-4 days
**Dependencies**: Module 1 (AlpacaProvider for real-time prices)
**Branch**: `phase2/agent-b/dynamic-risk`

---

### Module 4: Monitoring & CLI Tools (Agent B)
**Purpose**: Real-time monitoring and operational tools

**Components**:
1. **Performance Tracker** (`src/monitoring/performance_tracker.py`)
   - Track daily P&L
   - Calculate cumulative returns
   - Update equity curve
   - Compare to benchmark (SPY)

2. **CLI Monitoring Tool** (`scripts/monitor_trading.py`)
   - **Commands**:
     - `monitor status`: Show account info, positions, P&L
     - `monitor positions`: Detailed position breakdown
     - `monitor performance`: Performance metrics (Sharpe, drawdown, returns)
     - `monitor logs`: Tail recent trading logs
     - `monitor orders`: Show recent orders and fills

   - **Features**:
     - Auto-refresh mode (watch mode)
     - Color-coded output (green = profit, red = loss)
     - Alerts for risk events

3. **Log Aggregation** (`src/utils/logging_enhanced.py`)
   - Structured logging for trading events
   - Log levels: INFO (trades), WARNING (risk events), ERROR (failures)
   - Log rotation and archiving

**Deliverables**:
- [ ] `PerformanceTracker` implementation
- [ ] `monitor_trading.py` CLI tool
- [ ] Enhanced logging utilities
- [ ] Unit tests
- [ ] CLI usage documentation

**Estimated Time**: 2-3 days
**Dependencies**: Module 1 (AlpacaExecutor), Module 3 (RiskManager)
**Branch**: `phase2/agent-b/monitoring`

---

## Agent Task Assignment

### Agent A: Integration Specialist
**Focus**: External system integration and workflow orchestration

**Responsibilities**:
1. **Week 1-2**: Module 1 (Alpaca Integration)
   - Implement AlpacaProvider
   - Implement AlpacaExecutor
   - Write integration tests with Paper Trading account

2. **Week 2-3**: Module 2 (Scheduler & Workflows)
   - Implement APScheduler integration
   - Build daily workflow (open, rebalance, close)
   - Test task dependency chains

3. **Week 4**: Integration & Testing
   - End-to-end testing with Agent B's modules
   - Bug fixes and refinements

**Git Branches**:
- `phase2/agent-a/alpaca-integration`
- `phase2/agent-a/scheduler`

**Merge Target**: `phase2/dev` (integration branch)

---

### Agent B: Core Logic Specialist
**Focus**: Internal logic enhancement and developer tools

**Responsibilities**:
1. **Week 1**: Module 0 (Configuration Setup)
   - Create `config/alpaca.yaml`
   - Create `.env.example`
   - Update `requirements.txt`
   - Update config loader

2. **Week 2-3**: Module 3 (Dynamic Risk Management)
   - Implement DynamicRiskManager
   - Build position and portfolio monitors
   - Implement stop-loss/take-profit logic

3. **Week 3-4**: Module 4 (Monitoring & CLI Tools)
   - Build PerformanceTracker
   - Create CLI monitoring tool
   - Enhanced logging

4. **Week 4**: Integration & Testing
   - End-to-end testing with Agent A's modules
   - Documentation updates

**Git Branches**:
- `phase2/agent-b/config-setup`
- `phase2/agent-b/dynamic-risk`
- `phase2/agent-b/monitoring`

**Merge Target**: `phase2/dev` (integration branch)

---

## Interface Contracts

**CRITICAL**: Both agents must follow these interface definitions to ensure compatibility.

### 1. AlpacaProvider Interface

```python
# src/data/providers/alpaca_provider.py
from src.data.base import DataProvider
from typing import List, Optional
import pandas as pd
from datetime import date

class AlpacaProvider(DataProvider):
    """Alpaca data provider for historical and real-time data."""

    def __init__(
        self,
        api_key: str,
        secret_key: str,
        base_url: str,
        data_url: str,
    ):
        """Initialize Alpaca provider with credentials."""
        pass

    def get_daily_bars(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        """
        Fetch historical daily bars.

        Returns:
            DataFrame with columns: date, open, high, low, close, volume
            Index: DatetimeIndex
        """
        pass

    def get_latest_quote(self, symbol: str) -> dict:
        """
        Get latest quote (real-time price).

        Returns:
            {
                'symbol': str,
                'bid': float,
                'ask': float,
                'last': float,
                'timestamp': datetime,
            }
        """
        pass

    def get_trading_days(
        self,
        start_date: date,
        end_date: date,
    ) -> List[date]:
        """Get list of trading days (market open days)."""
        pass
```

### 2. AlpacaExecutor Interface

```python
# src/execution/alpaca_executor.py
from src.execution.base import OrderExecutor, ExecutionOrder, AccountInfo, Position
from src.portfolio.base import Order
from typing import List, Optional

class AlpacaExecutor(OrderExecutor):
    """Alpaca Paper Trading executor."""

    def __init__(
        self,
        api_key: str,
        secret_key: str,
        base_url: str,
    ):
        """Initialize Alpaca executor with credentials."""
        pass

    def submit_orders(
        self,
        orders: List[Order],
        execution_date: date,
    ) -> List[ExecutionOrder]:
        """
        Submit orders to Alpaca Paper Trading API.

        Args:
            orders: List of Order objects (from Portfolio Layer)
            execution_date: Date of execution (for logging)

        Returns:
            List of ExecutionOrder with fill details
        """
        pass

    def get_positions(self) -> List[Position]:
        """Get current positions from Alpaca account."""
        pass

    def get_account_info(self) -> AccountInfo:
        """Get account balance and buying power."""
        pass

    def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order."""
        pass
```

### 3. DynamicRiskManager Interface

```python
# src/risk/dynamic_risk_manager.py
from src.risk.base import RiskManager, ExitSignal
from src.execution.base import Position
from typing import List

class DynamicRiskManager(RiskManager):
    """Real-time risk monitoring and position protection."""

    def __init__(
        self,
        stop_loss_pct: float = 0.03,  # 3% stop-loss
        take_profit_pct: float = 0.10,  # 10% take-profit
        daily_loss_limit: float = 0.02,  # 2% daily loss limit
        max_drawdown: float = 0.05,  # 5% max drawdown
    ):
        """Initialize risk manager with thresholds."""
        pass

    def monitor_positions(
        self,
        positions: List[Position],
        current_prices: dict,  # {symbol: price}
    ) -> List[ExitSignal]:
        """
        Check positions for risk triggers.

        Returns:
            List of ExitSignal for positions that should be closed
        """
        pass

    def check_circuit_breaker(
        self,
        portfolio_value: float,
        peak_value: float,
        daily_start_value: float,
    ) -> bool:
        """
        Check if circuit breaker should trigger.

        Returns:
            True if trading should stop (drawdown limit exceeded)
        """
        pass
```

### 4. Scheduler Interface

```python
# src/orchestration/scheduler.py
from apscheduler.schedulers.blocking import BlockingScheduler
from typing import Callable

class TradingScheduler:
    """APScheduler wrapper for trading workflows."""

    def __init__(self, config: dict):
        """Initialize scheduler with configuration."""
        pass

    def register_task(
        self,
        name: str,
        func: Callable,
        trigger: str,  # 'cron', 'interval', 'date'
        trigger_args: dict,
        dependencies: List[str] = None,
    ):
        """Register a scheduled task with optional dependencies."""
        pass

    def start(self):
        """Start the scheduler (blocking)."""
        pass

    def shutdown(self):
        """Gracefully shutdown scheduler."""
        pass
```

### 5. Configuration Structure

```yaml
# config/alpaca.yaml
alpaca:
  # API credentials (loaded from .env)
  api_key: ${ALPACA_API_KEY}
  secret_key: ${ALPACA_SECRET_KEY}
  base_url: ${ALPACA_BASE_URL}
  data_url: ${ALPACA_DATA_URL}

  # Trading configuration
  trading:
    enabled: true
    mode: paper  # paper or live

  # Rebalancing schedule (NYSE time)
  schedule:
    market_open: "09:30"
    rebalance_time: "15:45"  # 3:45 PM ET
    market_close: "16:00"

  # Risk monitoring
  risk_monitoring:
    enabled: true
    check_interval_minutes: 5
    stop_loss_pct: 0.03  # 3%
    take_profit_pct: 0.10  # 10%
    daily_loss_limit: 0.02  # 2%
    max_drawdown: 0.05  # 5%

  # Order execution
  execution:
    order_type: market  # market or limit
    time_in_force: day  # day or gtc

  # Rate limiting
  rate_limits:
    max_requests_per_minute: 200
    max_orders_per_minute: 60
```

---

## Git Workflow

### Branch Structure
```
main (protected - production-ready code)
 └─ phase2/dev (integration branch - for Phase 2 development)
     ├─ phase2/agent-a/alpaca-integration
     ├─ phase2/agent-a/scheduler
     ├─ phase2/agent-b/config-setup
     ├─ phase2/agent-b/dynamic-risk
     └─ phase2/agent-b/monitoring
```

### Workflow Steps

1. **Feature Development**:
   ```bash
   # Agent A creates feature branch from phase2/dev
   git checkout phase2/dev
   git pull origin phase2/dev
   git checkout -b phase2/agent-a/alpaca-integration

   # Work on feature...
   git add .
   git commit -m "feat(alpaca): implement AlpacaProvider with REST API"
   git push origin phase2/agent-a/alpaca-integration
   ```

2. **Merge to Integration Branch**:
   ```bash
   # Create PR: phase2/agent-a/alpaca-integration → phase2/dev
   # After review (can be reviewed by Agent B or user)
   git checkout phase2/dev
   git merge phase2/agent-a/alpaca-integration
   git push origin phase2/dev
   ```

3. **Sync Between Agents**:
   ```bash
   # Agent B pulls latest changes from phase2/dev
   git checkout phase2/dev
   git pull origin phase2/dev

   # Rebase feature branch if needed
   git checkout phase2/agent-b/dynamic-risk
   git rebase phase2/dev
   ```

4. **Merge to Main** (end of Phase 2):
   ```bash
   # After all modules complete and tested
   git checkout main
   git merge phase2/dev
   git push origin main
   git tag v0.2.0-phase2-complete
   ```

### Commit Message Convention
Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(alpaca): add AlpacaProvider for historical data
fix(scheduler): resolve timezone handling in market hours
test(risk): add unit tests for stop-loss monitoring
docs(phase2): update PHASE2_PLAN with progress
refactor(execution): simplify order submission logic
```

### Code Review Guidelines
- Each agent can review the other's PRs
- Check for:
  - Interface contract compliance
  - Test coverage (>80%)
  - Documentation (docstrings)
  - No hardcoded credentials
  - Error handling

---

## Dependencies

### New Python Packages

Update `requirements.txt`:

```txt
# Alpaca Trading API
alpaca-py>=0.9.0

# Task scheduling
APScheduler>=3.10.0

# Environment variables
python-dotenv>=1.0.0

# Enhanced CLI
rich>=13.0.0  # for colored CLI output
```

### Installation
```bash
pip install -r requirements.txt
```

### API Dependencies
- Alpaca Paper Trading Account (already set up ✅)
- NYSE Trading Calendar (via `exchange_calendars` - already installed ✅)

---

## Acceptance Criteria

### Module 0: Configuration & Setup
- [x] `.env` file created with Alpaca credentials
- [ ] `config/alpaca.yaml` created and validated
- [ ] `.env.example` template created
- [ ] `requirements.txt` updated
- [ ] Config loader reads Alpaca config successfully

### Module 1: Alpaca Integration
- [ ] AlpacaProvider fetches historical daily bars correctly
- [ ] AlpacaProvider gets latest quotes correctly
- [ ] AlpacaExecutor submits market orders successfully
- [ ] AlpacaExecutor queries positions and account info
- [ ] Unit tests coverage >80%
- [ ] Integration tests pass with Paper Trading account

### Module 2: Scheduler & Workflows
- [ ] APScheduler starts and runs tasks on schedule
- [ ] Market hours detection works correctly (NYSE calendar)
- [ ] Daily workflow executes all steps in correct order
- [ ] Task dependencies prevent race conditions
- [ ] Error handling and retry logic works
- [ ] Unit tests coverage >80%

### Module 3: Dynamic Risk Management
- [ ] Stop-loss triggers work correctly (position closed when threshold hit)
- [ ] Take-profit triggers work correctly
- [ ] Circuit breaker stops trading on drawdown limit
- [ ] Position monitoring runs every 5 minutes
- [ ] Unit tests coverage >80%
- [ ] Historical replay tests validate logic

### Module 4: Monitoring & CLI Tools
- [ ] `monitor_trading.py status` shows real-time account info
- [ ] `monitor_trading.py positions` shows position details
- [ ] `monitor_trading.py performance` calculates metrics correctly
- [ ] Auto-refresh mode works (watch mode)
- [ ] Logging captures all trading events
- [ ] CLI documentation complete

### Phase 2 Completion
- [ ] All modules integrated and tested together
- [ ] 1 week of paper trading simulation successful
- [ ] No critical bugs or data quality issues
- [ ] Documentation updated (README, usage guides)
- [ ] Code coverage >80% overall
- [ ] Phase 2 retrospective complete

---

## Timeline

### Week 1 (2026-01-31 to 2026-02-06)
**Agent A**:
- Days 1-2: Set up development environment, review interfaces
- Days 3-7: Implement AlpacaProvider and AlpacaExecutor

**Agent B**:
- Days 1-2: Create config files, update requirements.txt
- Days 3-7: Start DynamicRiskManager implementation

**Milestones**:
- [ ] AlpacaProvider can fetch data from Paper Trading account
- [ ] Config infrastructure complete

### Week 2 (2026-02-07 to 2026-02-13)
**Agent A**:
- Days 1-5: Complete AlpacaExecutor
- Days 6-7: Start Scheduler implementation

**Agent B**:
- Days 1-7: Complete DynamicRiskManager and monitors

**Milestones**:
- [ ] AlpacaExecutor can submit orders to Paper Trading
- [ ] DynamicRiskManager monitors positions correctly

### Week 3 (2026-02-14 to 2026-02-20)
**Agent A**:
- Days 1-7: Complete Scheduler and daily workflows

**Agent B**:
- Days 1-5: Implement monitoring and CLI tools
- Days 6-7: Integration testing

**Milestones**:
- [ ] Daily workflow runs end-to-end successfully
- [ ] CLI monitoring tool functional

### Week 4 (2026-02-21 to 2026-02-28)
**Both Agents**:
- Days 1-3: Integration testing, bug fixes
- Days 4-7: Paper trading simulation (monitor daily)

**Milestones**:
- [ ] Phase 2 complete and validated
- [ ] Ready for extended paper trading (2-4 weeks)

---

## Progress Tracking

### Module Status

| Module | Agent | Status | Progress | Completed |
|--------|-------|--------|----------|-----------|
| Module 0: Config Setup | B | 🟡 In Progress | 50% | - |
| Module 1: Alpaca Integration | A | ⚪ Not Started | 0% | - |
| Module 2: Scheduler & Workflows | A | ⚪ Not Started | 0% | - |
| Module 3: Dynamic Risk | B | ⚪ Not Started | 0% | - |
| Module 4: Monitoring & CLI | B | ⚪ Not Started | 0% | - |
| Integration Testing | Both | ⚪ Not Started | 0% | - |
| Paper Trading Validation | Both | ⚪ Not Started | 0% | - |

**Legend**:
- ⚪ Not Started
- 🟡 In Progress
- ✅ Complete
- ❌ Blocked

### Daily Progress Log

#### 2026-01-31
**Agent B**:
- [x] User created `.env` with Alpaca credentials
- [ ] Created `config/alpaca.yaml` (next task)
- [ ] Created `.env.example` (next task)

**Agent A**:
- [ ] Waiting for config setup to complete

**Blockers**: None

---

## Notes and Decisions

### 2026-01-31: Phase 2 Kickoff
**Decision**: Use Daily Rebalancing + Intraday Risk Monitoring (no active intraday trading)

**Rationale**:
- Aligns with validated Phase 1 backtesting approach
- Lower complexity and transaction costs
- Intraday monitoring provides downside protection without trading complexity

**Alternative Rejected**: Full intraday trading (too complex, deferred to Phase 3)

---

## Communication Between Agents

### Synchronization Points

**Daily Sync** (recommended):
1. Each agent updates this document's Progress Tracking section
2. Note any blockers or dependencies
3. Review other agent's commits to stay aligned

**Weekly Sync** (required):
1. Review integration progress
2. Test modules together
3. Adjust timeline if needed

### Conflict Resolution
If agents encounter conflicts or unclear requirements:
1. Document the issue in this file (add to Notes section)
2. Propose solutions for user review
3. Wait for user decision before proceeding

---

## Success Metrics

Phase 2 will be validated by:
1. **Technical Metrics**:
   - Test coverage >80%
   - No critical bugs in 1 week of paper trading
   - All acceptance criteria met

2. **Trading Metrics** (1-week validation):
   - System executes daily rebalancing successfully
   - Stop-loss triggers correctly (test with simulated scenarios)
   - No missed trades or execution failures
   - Performance tracking matches Alpaca dashboard

3. **Operational Metrics**:
   - Scheduler runs reliably (no crashes)
   - CLI tools provide useful real-time info
   - Logs capture all important events

---

## References

- [Phase 1 Summary](PHASE1_SUMMARY.md)
- [Architecture Overview](../agent/architecture-overview.md)
- [Development Guidelines](../agent/development-guidelines.md)
- [Alpaca API Documentation](https://alpaca.markets/docs/)
- [APScheduler Documentation](https://apscheduler.readthedocs.io/)

---

**Last Updated**: 2026-01-31
**Next Review**: 2026-02-07 (end of Week 1)
