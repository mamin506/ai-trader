# Source Code Directory Structure

This directory contains the main source code for the AI Trader project.

## Directory Layout

```
src/
├── data/           # Data layer: providers, storage, APIs
├── strategy/       # Strategy layer: signals, indicators
├── portfolio/      # Portfolio management: allocation, rebalancing
├── risk/           # Risk management: validation, limits
├── execution/      # Order execution: backtest, paper, live
├── orchestration/  # Task scheduling and workflow coordination
└── utils/          # Shared utilities: config, logging, exceptions
```

## Layer Responsibilities

### Data Layer (`data/`)
- Abstract data provider interface
- Concrete implementations (YFinance, Alpaca)
- Database management (SQLite, future PostgreSQL)
- Data quality validation
- User-facing DataAPI

### Strategy Layer (`strategy/`)
- Abstract strategy interface
- Technical indicator calculations (TA-Lib wrapper)
- Signal generation logic
- Strategy implementations (MA Crossover, etc.)
- User-facing StrategyAPI

### Portfolio Management Layer (`portfolio/`)
- Abstract portfolio manager interface
- Allocation algorithms (heuristic, risk-parity, optimization)
- Rebalancing logic
- Position tracking
- User-facing PortfolioAPI

### Risk Management Layer (`risk/`)
- Abstract risk manager interface
- Position size validation
- Cash reserve checks
- Stop-loss/take-profit rules
- Risk metrics calculation (VaR, CVaR in Phase 3)

### Execution Layer (`execution/`)
- Abstract order executor interface
- Backtest executor (historical simulation)
- Paper trading executor (Alpaca Paper API)
- Live trading executor (Alpaca Live API)
- Trade logging and history

### Orchestration Layer (`orchestration/`)
- APScheduler integration
- Task dependency chains (Data → Signal → Portfolio)
- Daily/intraday workflow coordination
- Error handling and circuit breakers

### Utilities (`utils/`)
- Configuration management (YAML loader)
- Logging framework (structured logging)
- Exception hierarchy (AITraderError and subclasses)
- Common helper functions

## Development Guidelines

See [development-guidelines.md](../agent/development-guidelines.md) for:
- Coding standards (type hints, docstrings, line length)
- Testing requirements (unit tests, integration tests)
- Documentation expectations
- Git workflow
