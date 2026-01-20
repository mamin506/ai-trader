# Technology Stack

This document records the technology selections for the AI Trader project and the rationale behind each choice.

## Guiding Principles

1. **Mature Libraries First**: Use well-established, battle-tested libraries rather than reinventing the wheel
2. **Long-term Focus**: This is a multi-month project with emphasis on building a robust, production-ready system
3. **Interface Abstraction**: Design for replaceability - components should be swappable through well-defined interfaces
4. **Progressive Enhancement**: Start simple, upgrade when needed based on actual requirements

## Technology Decisions

### 1. Universe Selection

**Decision**: Custom rule-based selection (Phase 1), yfinance screening (Phase 2)

**Options Considered**:
- **Custom rule-based**: Liquidity filters, market cap thresholds, sector restrictions
- **yfinance screening**: Use Yahoo Finance's built-in screening capabilities
- **External screening services**: Finnhub, Alpha Vantage, or paid screening APIs
- **Index-based**: Simply track major indices (S&P 500, Russell 2000, etc.)

**Rationale**:
- **Foundation for realistic backtesting**: Real strategies operate on filtered universes, not entire markets
- **Performance optimization**: Reduces data fetching/API calls by 90%+ (from 4000+ US stocks to 50-200)
- **Risk control**: Eliminates low-liquidity stocks that cause slippage issues
- **Progressive enhancement**: Start simple (static rules), add sophistication later
- **Zero additional dependencies**: Can implement with existing libraries (pandas filtering)

**Implementation Approach**:
- Phase 1: Basic filters (min_market_cap: $500M, min_avg_volume: 100K shares, max_price: $1000)
- Phase 2: Enhanced screening using yfinance's screener API for dynamic criteria
- Phase 3: Multi-factor selection (volatility, sector balance, etc.)

**Key Interface Design**:
- `select_universe(criteria: Dict, as_of_date: datetime) -> List[str]`
- Configuration-driven criteria (YAML-based)
- Cached results with refresh intervals

### 2. Market Data Acquisition

**Decision**: Start with yfinance, design for provider abstraction

**Options Considered**:
- **yfinance**: Free, simple, Yahoo Finance data, suitable for daily data
- **Alpaca API**: Free real-time data, supports trading, good documentation
- **Interactive Brokers API**: Professional-grade, complex, requires IB account

**Rationale**:
- Target timeframe is **daily bars** (not intraday or high-frequency)
- yfinance provides sufficient data quality for daily strategies
- Zero setup friction enables rapid strategy prototyping
- Abstract interface allows seamless migration to Alpaca or IB later

**Implementation Approach**:
- Phase 1 (Now): Use yfinance behind a `DataProvider` abstraction
- Phase 2 (Post-validation): Add `AlpacaProvider` implementation
- Phase 3 (Pre-production): Add `IBProvider` if needed

**Key Interface Design**:
- Standardized methods: `get_historical_bars()`, `get_latest_quote()`, etc.
- Unified DataFrame output format across all providers
- Configuration-based provider switching (no code changes needed)

### 2. Backtesting Framework

**Decision**: VectorBT

**Options Considered**:
- **Backtrader**: Feature-rich, mature, extensive documentation
- **Zipline**: Event-driven, pandas integration, Quantopian heritage
- **VectorBT**: Fast vectorized computation, modern design

**Rationale**:
- **Performance critical**: NumPy vectorization provides 100-1000x speedup vs event-driven frameworks
- Multi-factor strategy requires testing large parameter spaces and stock universes
- Modern Python design (type hints, chainable API, Pythonic)
- Excellent Pandas integration (seamless with yfinance data)
- Interactive Plotly visualizations for strategy analysis
- Ideal for rapid prototyping and parameter optimization
- Phase 1 priority: Fast iteration on strategy validation

### 3. Data Storage

**Decision**: SQLite + Pandas

**Options Considered**:
- **SQLite + Pandas**: Lightweight, zero-config, good for local development
- **PostgreSQL + TimescaleDB**: Professional time-series database, scalable
- **Arctic (MongoDB)**: Designed for financial data, version control features

**Rationale**:
- **Zero configuration**: Built into Python standard library (sqlite3 module)
- File-based database (single .db file, easy backup/migration)
- Sufficient performance for daily data (handles millions of rows easily)
- Perfect Pandas integration (`df.to_sql()`, `pd.read_sql()`)
- DevContainer friendly (data persists in local directory)
- Daily timeframe data volume is small (500 stocks × 10 years × 252 days = ~1.2M rows)
- **Low migration cost**: SQL compatible, can upgrade to PostgreSQL if needed in Phase 2-3
- No need for database service management in Phase 1

**Database Schema**:
- `daily_prices`: symbol, date, open, high, low, close, volume, adj_close
- `backtest_results`: strategy performance metrics
- `strategy_signals`: historical signal data

### 4. Strategy Development & Indicators

**Decision**: TA-Lib (primary), pandas-ta (supplementary)

**Options Considered**:
- **TA-Lib + Pandas**: Most comprehensive, C-based performance, industry standard
- **pandas-ta**: Pure Python, easy installation, good pandas integration
- **Custom framework**: Maximum flexibility, higher development cost

**Rationale**:
- TA-Lib provides 150+ battle-tested indicators (30+ years in production)
- C implementation crucial for backtesting performance across large universes
- Easy installation in Ubuntu DevContainer: `apt-get install libta-lib0-dev && pip install TA-Lib`
- Industry-standard algorithms ensure calculation correctness
- pandas-ta available as supplement for indicators not in TA-Lib

**Trading Framework Selected**:
- **Multi-Factor Portfolio Strategy** (Position Trading + Multi-Asset)
- Daily timeframe with weekly/monthly rebalancing
- 5-20 simultaneous positions for diversification
- See [strategy-layer-design.md](strategy-layer-design.md) for detailed rationale

### 5. Order Execution

**Decision**: Alpaca API (primary), abstraction for multi-mode support

**Options Considered**:
- **Alpaca Trading API**: Zero commission, paper trading API, developer-friendly
- **Interactive Brokers API**: Professional, advanced features, complex
- **TD Ameritrade API**: Traditional broker, stable

**Rationale**:
- **Three execution modes**: Backtesting, Paper Trading, Live Trading
- Alpaca provides identical API for paper and live trading (smooth migration)
- Zero commissions reduce cost overhead for frequent rebalancing
- Free paper trading tier with real-time market data
- Simple REST API + Python SDK with excellent documentation
- See [execution-layer-design.md](execution-layer-design.md) for detailed architecture

**Implementation Deferred**:
- Execution layer implementation deferred until after backtesting validation
- Validation workflow: Backtesting (Phase 1) → Paper Trading (Phase 2) → Live Trading (Phase 3)

### 6. Task Scheduling

**Decision**: APScheduler

**Options Considered**:
- **APScheduler**: Lightweight, easy, pure Python
- **Celery + Redis**: Distributed task queue, scalable
- **Airflow**: Visual DAG, powerful, heavyweight

**Rationale**:
- **Zero dependencies**: Pure Python, no Redis/database services required
- Simple API for daily tasks (`@scheduler.scheduled_job(trigger='cron', ...)`)
- Sufficient for daily trading workflow:
  - Daily post-market data update (1x/day)
  - Strategy signal generation (1x/day or week)
  - Rebalancing checks (1x/week or month)
- Supports multiple trigger types (cron, interval, date-based)
- Optional SQLite persistence for task state
- No need for distributed execution (single-machine deployment)
- **Upgrade path**: Can migrate to Celery/Airflow if workflow becomes complex (unlikely for daily strategies)

**Typical Usage**:
```python
from apscheduler.schedulers.blocking import BlockingScheduler

scheduler = BlockingScheduler()

@scheduler.scheduled_job('cron', hour=16, minute=30)  # After US market close
def daily_workflow():
    update_market_data()
    generate_signals()
    check_rebalance()

scheduler.start()
```

### 7. Portfolio Management & Optimization

**Decision**: Custom implementation (Phase 1), PyPortfolioOpt (Phase 2-3 supplement)

**Options Considered**:
- **Custom rule-based allocation**: Simple, transparent, full control
- **PyPortfolioOpt**: Modern portfolio theory algorithms (Markowitz, Black-Litterman, Risk Parity)
- **QuantLib-Python**: Professional library (overkill for equity portfolios)

**Rationale**:
- No comprehensive off-the-shelf solution for portfolio management (signal aggregation, rebalancing, cash management)
- Portfolio Management is algorithmic logic, not library selection
- Phase 1: Simple heuristic allocation (signal strength weighting, position limits)
- Phase 2-3: Use PyPortfolioOpt for sophisticated optimization algorithms
- See [portfolio-management-design.md](portfolio-management-design.md) for detailed theory and implementation plan

**Progressive Plan**:
- Phase 1: Rule-based (signal strength → weights, weekly rebalancing)
- Phase 2: Risk-adjusted (incorporate volatility)
- Phase 3: Optimization (Black-Litterman + Markowitz)

### 8. Risk Management

**Decision**: Custom implementation (Phase 1-2), QuantStats (Phase 3)

**Options Considered**:
- **Custom risk rules**: Position limits, stop-loss, validation logic
- **QuantStats**: Risk metrics calculation (Sharpe, Drawdown, VaR, reports)
- **PyPortfolioOpt constraints**: Optimization constraints (Phase 3 supplement)

**Rationale**:
- No comprehensive risk management library (rules are personalized)
- Phase 1: Basic static checks (position limits, cash reserves)
- Phase 2: Dynamic monitoring (stop-loss, take-profit, trailing stop)
- Phase 3: Portfolio-level (drawdown protection, VaR, circuit breakers)
- QuantStats for professional risk metrics and HTML reports
- See [risk-management-design.md](risk-management-design.md) for detailed design

**Key Decisions**:
- Independent layer between Portfolio and Execution
- Stop-loss managed by Risk Layer (not Strategy Layer)
- Mode B: Auto-adjustment (for backtesting automation)

## Decision Log

| Date | Component | Decision | Status |
|------|-----------|----------|--------|
| 2026-01-20 | Universe Selection | Custom rule-based (Phase 1) + yfinance screening (Phase 2) | ✅ Decided |
| 2026-01-17 | Market Data | yfinance with abstraction layer | ✅ Decided |
| 2026-01-17 | Strategy Framework | Multi-Factor Portfolio Strategy | ✅ Decided |
| 2026-01-17 | Technical Indicators | TA-Lib (primary) + pandas-ta (supplementary) | ✅ Decided |
| 2026-01-17 | Portfolio Management | Custom (Phase 1) + PyPortfolioOpt (Phase 2-3) | ✅ Decided |
| 2026-01-17 | Risk Management | Custom (Phase 1-2) + QuantStats (Phase 3) | ✅ Decided |
| 2026-01-17 | Order Execution | Alpaca API with multi-mode abstraction | ✅ Decided |
| 2026-01-17 | Backtesting | VectorBT | ✅ Decided |
| 2026-01-17 | Data Storage | SQLite + Pandas | ✅ Decided |
| 2026-01-17 | Task Scheduling | APScheduler | ✅ Decided |

## Summary

All core technology stack decisions are now complete. The stack emphasizes:

1. **Rapid Development**: Zero-config tools (SQLite, APScheduler, yfinance)
2. **Performance**: VectorBT for fast backtesting, TA-Lib for indicator calculation
3. **Modern Python**: Type hints, Pandas integration, clean APIs
4. **Progressive Enhancement**: Simple Phase 1 implementations with clear upgrade paths
5. **Proven Libraries**: Battle-tested components (TA-Lib, Pandas, Alpaca)

## Next Steps

1. Complete architecture-overview.md (system integration diagram)
2. Document development guidelines (coding standards, project structure)
3. Begin Phase 1 implementation
