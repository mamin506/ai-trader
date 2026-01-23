# VectorBT Integration Plan

**Date**: 2026-01-23
**Status**: In Progress
**Goal**: Add high-performance vectorized backtesting for parameter optimization

---

## Overview

VectorBT is a vectorized backtesting library that provides 100-1000x speedup over event-driven backtesting. This integration adds fast parameter optimization and batch backtesting capabilities while preserving the existing detailed simulation framework.

## Architecture Decision

### Approach: Complementary Tool (Not Replacement)

**Why not replace BacktestExecutor?**
- Current architecture provides detailed order-by-order simulation
- VectorBT excels at different use cases (optimization, screening)
- Both tools serve different purposes

**Integration Strategy**:
```
┌─────────────────────────────────────────────────┐
│  Existing Architecture (Detailed Simulation)    │
│  BacktestOrchestrator → BacktestExecutor        │
│  Use for: Final validation, detailed analysis   │
└─────────────────────────────────────────────────┘
                    ↓
                 Signals
                    ↓
┌─────────────────────────────────────────────────┐
│  New VectorBT Module (Fast Optimization)        │
│  VectorBTBacktest → Vectorized Engine           │
│  Use for: Parameter tuning, bulk screening      │
└─────────────────────────────────────────────────┘
```

## Use Cases

### 1. Parameter Optimization (Primary Use Case)
**Problem**: Testing 1000+ parameter combinations takes hours with event-driven backtest
**Solution**: VectorBT tests all combinations in minutes

Example:
```python
# Test 100 MA crossover combinations
fast_periods = range(5, 50, 5)  # 10 values
slow_periods = range(50, 200, 10)  # 15 values
# Total: 150 combinations

# Event-driven: 150 × 30 seconds = 75 minutes
# VectorBT: ~30 seconds (150x faster)
```

### 2. Strategy Screening
**Problem**: Screening strategy performance across 100+ symbols
**Solution**: VectorBT runs all symbols simultaneously

### 3. Walk-Forward Optimization
**Problem**: Rolling window optimization for adaptive strategies
**Solution**: VectorBT's built-in walk-forward analysis

## Implementation Plan

### Phase 1: Core VectorBT Integration

**Module Structure**:
```
src/execution/
  └── vectorbt_backtest.py      # Core VectorBT integration

src/api/
  └── vectorbt_api.py            # User-friendly API

scripts/
  └── optimize_strategy.py       # CLI for optimization

tests/unit/
  └── test_vectorbt_backtest.py  # Unit tests
```

### Phase 2: Key Features

**1. Signal-Based Backtesting**
- Convert strategy signals to VectorBT portfolio
- Support long-only (Phase 1) and long-short (Phase 2+)
- Apply slippage and commission

**2. Parameter Optimization**
- Grid search over parameter ranges
- Return sorted results by metric (Sharpe, return, etc.)
- Support multi-objective optimization

**3. Performance Metrics**
- Total return and annualized return
- Sharpe ratio and Sortino ratio
- Max drawdown and calmar ratio
- Win rate and average trade
- Equity curve and drawdown series

**4. Walk-Forward Analysis**
- Train/test split optimization
- Rolling window validation
- Out-of-sample performance tracking

### Phase 3: API Design

**Simple API Example**:
```python
from src.api.vectorbt_api import VectorBTAPI

api = VectorBTAPI()

# 1. Fast backtest with current strategy
result = api.backtest(
    data=price_data,
    signals=signal_series,
    initial_cash=100000,
    commission=0.001
)
print(f"Return: {result.total_return:.2%}")
print(f"Sharpe: {result.sharpe_ratio:.2f}")

# 2. Parameter optimization
results = api.optimize_parameters(
    strategy_class=MACrossoverStrategy,
    data=price_data,
    param_grid={
        'fast_period': range(10, 50, 5),
        'slow_period': range(50, 200, 10)
    },
    metric='sharpe_ratio'
)
print(f"Best params: {results.best_params}")
print(f"Best Sharpe: {results.best_sharpe:.2f}")

# 3. Batch backtest across symbols
results = api.batch_backtest(
    strategy=strategy,
    symbols=['AAPL', 'MSFT', 'GOOGL', ...],
    start_date='2023-01-01',
    end_date='2024-01-01'
)
results.sort_by('sharpe_ratio')
```

## Technical Details

### Dependencies
```txt
vectorbt>=0.26.0  # Core library
numba>=0.58.0     # JIT compilation for speed
```

### Key VectorBT Components

**1. Portfolio Class**
```python
import vectorbt as vbt

# Create portfolio from signals
pf = vbt.Portfolio.from_signals(
    close=prices,
    entries=buy_signals,
    exits=sell_signals,
    init_cash=100000,
    fees=0.001  # 0.1% commission
)

# Access metrics
print(pf.total_return())
print(pf.sharpe_ratio())
print(pf.max_drawdown())
```

**2. Parameter Optimization**
```python
# Grid search
results = vbt.Portfolio.from_signals(
    close=prices,
    entries=buy_signals_grid,  # 3D array: params × time × assets
    exits=sell_signals_grid,
    init_cash=100000
)

# Find best parameters
best_idx = results.sharpe_ratio().idxmax()
```

**3. Walk-Forward Analysis**
```python
# Split into train/test windows
windows = vbt.WFO.from_splits(
    data=prices,
    split_every='180D',  # 6 months
    lookahead='90D'      # 3 months test
)

# Optimize on each window
results = windows.optimize(...)
```

## Integration with Existing Code

### 1. Strategy Layer Integration
```python
# Existing strategy generates signals
from src.strategy.ma_crossover import MACrossoverStrategy

strategy = MACrossoverStrategy({'fast_period': 20, 'slow_period': 50})
signals = strategy.generate_signals(price_data)

# VectorBT uses these signals
from src.api.vectorbt_api import VectorBTAPI

api = VectorBTAPI()
result = api.backtest(price_data, signals)
```

### 2. Comparison with BacktestOrchestrator
```python
# Detailed simulation (slow, accurate)
from src.api.backtest_api import BacktestAPI

detailed_result = BacktestAPI.run_backtest(
    strategy=strategy,
    symbols=['AAPL'],
    start_date='2023-01-01',
    end_date='2024-01-01'
)

# Fast vectorized (quick screening)
from src.api.vectorbt_api import VectorBTAPI

fast_result = VectorBTAPI().backtest(
    data=price_data,
    signals=signals
)

# Compare results
print(f"Detailed: {detailed_result.total_return_pct:.2f}%")
print(f"VectorBT: {fast_result.total_return:.2%}")
```

## Testing Strategy

### Unit Tests
- Test signal conversion to VectorBT format
- Test parameter grid generation
- Test metric calculations
- Test walk-forward splits

### Integration Tests
- Compare VectorBT results with BacktestExecutor (should be close)
- Test parameter optimization on real data
- Test batch backtesting

### Validation
- Verify performance speedup (target: 100x+ faster)
- Verify result accuracy (within 1% of detailed backtest)
- Test edge cases (no signals, insufficient data, etc.)

## Performance Benchmarks

**Target Performance**:
- Single backtest: <1 second (vs 30 seconds event-driven)
- 100 parameter combinations: <10 seconds (vs 50 minutes)
- 100 symbols batch: <30 seconds (vs hours)

## Documentation

**Files to Create**:
1. `docs/VECTORBT_GUIDE.md` - Usage guide and examples
2. `scripts/README.md` - Update with optimize_strategy.py usage
3. `notebooks/02_parameter_optimization.ipynb` - Tutorial notebook

**Key Sections**:
- When to use VectorBT vs BacktestOrchestrator
- Parameter optimization tutorial
- Walk-forward analysis guide
- Performance comparison

## Rollout Plan

### Step 1: Core Implementation (Today)
- Install VectorBT
- Create `vectorbt_backtest.py` module
- Implement basic signal-based backtesting
- Add unit tests

### Step 2: API Layer (Today)
- Create `VectorBTAPI` class
- Implement `backtest()` method
- Implement `optimize_parameters()` method
- Add integration tests

### Step 3: CLI Tool (Optional)
- Create `optimize_strategy.py` script
- Add command-line interface for parameter tuning
- Add example usage to README

### Step 4: Documentation (Optional)
- Create VECTORBT_GUIDE.md
- Create optimization tutorial notebook
- Update development-plan.md

## Success Criteria

Phase 1 VectorBT integration is complete when:
- ✅ VectorBT installed and integrated
- ✅ Basic backtesting working (signal → portfolio → metrics)
- ✅ Parameter optimization functional
- ✅ Results match BacktestExecutor (within 1-2%)
- ✅ 100x+ performance improvement demonstrated
- ✅ Unit tests passing
- ✅ API documentation complete

## Future Enhancements (Phase 2+)

**Advanced Features**:
- Multi-asset portfolio optimization
- Risk-adjusted position sizing
- Custom indicator optimization
- Machine learning hyperparameter tuning
- Live strategy adaptation

**Performance**:
- GPU acceleration for massive parameter grids
- Distributed optimization across multiple cores
- Caching for repeated backtests

## Related Documents

- [architecture-overview.md](architecture-overview.md) - System architecture
- [development-plan.md](development-plan.md) - Overall project plan
- [execution-layer-design.md](execution-layer-design.md) - Execution layer design

---

**Author**: Claude Sonnet 4.5
**Last Updated**: 2026-01-23
