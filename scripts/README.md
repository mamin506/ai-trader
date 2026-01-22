# CLI Scripts Documentation

This directory contains command-line tools for the AI Trader backtesting system.

**Quick Links**:
- [Validation Plan](#phase-1-validation-plan) - Step-by-step validation checklist
- [CLI Tools Reference](#cli-tools-reference) - Complete usage guide
- [Common Workflows](#common-workflows) - Real-world usage examples
- [Troubleshooting](#troubleshooting) - Common issues and solutions

---

## Phase 1 Validation Plan

### Overview

This plan validates the entire backtesting system with real market data before moving to Phase 2 (Paper Trading).

**Goals**:
- ✅ Verify data fetching and caching works correctly
- ✅ Confirm strategy signal generation is accurate
- ✅ Validate portfolio allocation and rebalancing
- ✅ Test risk management limits and adjustments
- ✅ Verify performance metrics calculation
- ✅ Ensure system handles edge cases properly

**Timeline**: 1-2 days

---

### Step 1: Environment Setup (5 minutes)

**Checklist**:
```bash
# 1. Verify Python environment
python --version  # Should be 3.12+

# 2. Check dependencies
pip list | grep -E "(yfinance|pandas|ta-lib|click)"

# 3. Verify database directory
ls -lh data/

# 4. Test imports
python -c "from src.api.backtest_api import BacktestAPI; print('✓ Imports OK')"
```

**Expected Result**: All commands succeed without errors.

---

### Step 2: Data Layer Validation (10-15 minutes)

**Purpose**: Verify market data fetching, caching, and incremental updates.

#### Test 2.1: Basic Data Fetching
```bash
# Fetch 1 year of data for a single symbol
python scripts/view_data.py prices AAPL --start 2024-01-01 --end 2024-12-31

# Expected: ~252 trading days, no errors
```

**Validation Checklist**:
- [ ] Data fetched successfully from YFinance
- [ ] Approximately 252 rows (trading days in 2024)
- [ ] All OHLCV columns present
- [ ] No NaN values in critical columns
- [ ] Data saved to `data/market_data.db`

#### Test 2.2: Database Caching
```bash
# Run same command again - should be instant (from cache)
time python scripts/view_data.py prices AAPL --start 2024-01-01 --end 2024-12-31

# Expected: <1 second, "Loading from cache" message
```

**Validation Checklist**:
- [ ] Second run completes in <1 second
- [ ] Cache hit message displayed
- [ ] Identical data returned

#### Test 2.3: Incremental Fetching
```bash
# Extend date range (should only fetch new data)
python scripts/view_data.py update AAPL --start 2023-01-01 --end 2024-12-31

# Expected: Only 2023 data fetched (2024 from cache)
```

**Validation Checklist**:
- [ ] Only missing date range fetched
- [ ] Total ~504 trading days (2023 + 2024)
- [ ] No duplicate data

#### Test 2.4: Multiple Symbols
```bash
# Fetch data for portfolio of symbols
python scripts/view_data.py update AAPL MSFT GOOGL NVDA META

# Expected: All 5 symbols fetched and cached
```

**Validation Checklist**:
- [ ] All symbols fetched successfully
- [ ] Data cached for each symbol
- [ ] Database size increased appropriately

**Check Database**:
```bash
# Verify database contents
sqlite3 data/market_data.db "SELECT symbol, COUNT(*) as rows, MIN(date), MAX(date) FROM price_data GROUP BY symbol;"

# Expected: Each symbol has ~252 rows for 2024
```

---

### Step 3: Strategy Layer Validation (15-20 minutes)

**Purpose**: Verify signal generation and indicator calculation.

#### Test 3.1: MA Crossover Strategy - Single Symbol
```bash
# Test default MA(20/50) on AAPL
python scripts/test_strategy.py ma-crossover AAPL \
  --start 2024-01-01 --end 2024-12-31 \
  --show-data

# Expected: Signals generated, buy/sell crossovers identified
```

**Validation Checklist**:
- [ ] Fast MA (20-day) calculated correctly
- [ ] Slow MA (50-day) calculated correctly
- [ ] Buy signals when fast crosses above slow
- [ ] Sell signals when fast crosses below slow
- [ ] Signal counts reasonable (5-15 signals for 1 year)

#### Test 3.2: Different MA Periods
```bash
# Test aggressive MA(10/30)
python scripts/test_strategy.py ma-crossover AAPL \
  -p fast_period=10 -p slow_period=30 \
  --start 2024-01-01 --end 2024-12-31

# Test conservative MA(50/200)
python scripts/test_strategy.py ma-crossover AAPL \
  -p fast_period=50 -p slow_period=200 \
  --start 2024-01-01 --end 2024-12-31
```

**Validation Checklist**:
- [ ] Shorter periods generate more signals
- [ ] Longer periods generate fewer signals
- [ ] No invalid signals (NaN, out-of-bounds)

#### Test 3.3: Signal Quality Check
```bash
# Get detailed signal data
python scripts/test_strategy.py ma-crossover AAPL \
  --start 2024-01-01 --end 2024-12-31 \
  --signals-only

# Manually verify a few crossovers
```

**Manual Verification**:
- [ ] Pick 2-3 buy signals, verify fast MA > slow MA after signal
- [ ] Pick 2-3 sell signals, verify fast MA < slow MA after signal
- [ ] No false signals at boundaries

---

### Step 4: Portfolio Layer Validation (20-30 minutes)

**Purpose**: Test portfolio allocation, rebalancing, and multi-symbol trading.

#### Test 4.1: Basic Portfolio Backtest
```bash
# Run portfolio backtest with 5 symbols
python scripts/view_portfolio.py backtest \
  AAPL MSFT GOOGL NVDA META \
  --start 2024-01-01 --end 2024-12-31 \
  --capital 100000 \
  --show-trades --show-equity

# Expected: Trades across multiple symbols, portfolio value tracked
```

**Validation Checklist**:
- [ ] Initial capital: $100,000
- [ ] Trades executed for multiple symbols
- [ ] Final portfolio value displayed
- [ ] Total return % calculated
- [ ] Sharpe ratio reasonable (-1 to 3)
- [ ] Max drawdown % shown
- [ ] Trade history shows buy/sell pairs

#### Test 4.2: Allocation Logic
```bash
# Test with max 3 positions (forces prioritization)
python scripts/view_portfolio.py backtest \
  AAPL MSFT GOOGL NVDA META TSLA \
  --start 2024-01-01 --end 2024-12-31 \
  --max-positions 3 \
  --show-trades
```

**Validation Checklist**:
- [ ] Never more than 3 positions at once
- [ ] Stronger signals prioritized
- [ ] Rebalancing reduces/exits weak positions
- [ ] Cash buffer maintained

#### Test 4.3: Rebalancing Frequencies
```bash
# Daily rebalancing
python scripts/view_portfolio.py backtest AAPL MSFT GOOGL \
  --rebalance daily --show-trades | head -50

# Weekly rebalancing
python scripts/view_portfolio.py backtest AAPL MSFT GOOGL \
  --rebalance weekly --show-trades | head -50

# Monthly rebalancing
python scripts/view_portfolio.py backtest AAPL MSFT GOOGL \
  --rebalance monthly --show-trades | head -50
```

**Validation Checklist**:
- [ ] Daily: Most trades (rebalance every day)
- [ ] Weekly: Moderate trades (rebalance Mondays)
- [ ] Monthly: Fewest trades (rebalance 1st of month)
- [ ] Trade counts align with expectations

#### Test 4.4: Strategy Comparison
```bash
# Compare MA(10/30), MA(20/50), MA(50/200)
python scripts/view_portfolio.py compare \
  AAPL MSFT GOOGL NVDA META \
  --start 2024-01-01 --end 2024-12-31

# Expected: Comparison table with all 3 strategies
```

**Validation Checklist**:
- [ ] All 3 strategies tested
- [ ] Comparison table displayed
- [ ] Key metrics: Return, Sharpe, Drawdown, Trades
- [ ] Best strategy highlighted

---

### Step 5: Risk Management Validation (15-20 minutes)

**Purpose**: Verify position limits, cash reserves, and risk adjustments.

#### Test 5.1: Position Size Limits
```bash
# Small portfolio, large position limit (should hit limit)
python scripts/view_portfolio.py backtest AAPL \
  --capital 10000 \
  --max-positions 1 \
  --show-trades

# Check: Position size should not exceed 20% of portfolio (default)
# Verify in trade output: "shares" * "price" / 10000 <= 0.20
```

**Validation Checklist**:
- [ ] No single position exceeds max size limit
- [ ] Risk manager adjusts order sizes when needed
- [ ] Warning messages for adjusted orders (check logs)

#### Test 5.2: Cash Reserve Requirements
```bash
# High allocation scenario - verify cash reserve maintained
python scripts/view_portfolio.py backtest \
  AAPL MSFT GOOGL NVDA META TSLA AMD INTC \
  --capital 100000 \
  --max-positions 8 \
  --show-equity

# Check final state: Should have ~5% cash reserve
```

**Validation Checklist**:
- [ ] Cash reserve never drops below minimum (5% default)
- [ ] Orders rejected if cash insufficient
- [ ] Portfolio not over-leveraged

#### Test 5.3: Exposure Limits
```bash
# Try to max out exposure (95% default limit)
python scripts/view_portfolio.py backtest \
  AAPL MSFT GOOGL NVDA META TSLA AMD INTC QCOM MU \
  --capital 100000 \
  --max-positions 10 \
  --show-trades

# Check: Total exposure should not exceed 95% of capital
```

**Validation Checklist**:
- [ ] Total position value ≤ 95% of portfolio value
- [ ] Risk manager blocks orders exceeding limit
- [ ] System remains stable with max positions

---

### Step 6: Execution Layer Validation (15-20 minutes)

**Purpose**: Verify trade execution, slippage, commissions, and P&L tracking.

#### Test 6.1: Trade Execution Accuracy
```bash
# Run backtest with detailed trade output
python scripts/view_portfolio.py backtest AAPL MSFT \
  --start 2024-01-01 --end 2024-12-31 \
  --show-trades > /tmp/trades.txt

# Manually verify first few trades
cat /tmp/trades.txt | head -30
```

**Manual Validation**:
- [ ] Pick 1 buy trade: shares × price ≈ capital allocated
- [ ] Check commission: reasonable (e.g., $1-10 per trade)
- [ ] Verify slippage: execution price slightly worse than close
- [ ] Confirm P&L calculation: (sell_price - buy_price) × shares - commissions

#### Test 6.2: Slippage and Commission Impact
```bash
# Compare with/without costs (modify config or code)
# Default: 0.1% slippage, $1 + $0.005/share commission

python scripts/view_portfolio.py backtest AAPL MSFT GOOGL \
  --start 2024-01-01 --end 2024-12-31

# Note final return, then re-run with zero slippage/commission
# Difference shows cost impact (~1-3% typically)
```

**Validation Checklist**:
- [ ] Returns lower with slippage/commissions enabled
- [ ] Cost impact reasonable (1-3% for 1 year)
- [ ] High-frequency strategies more impacted

#### Test 6.3: Position Tracking
```bash
# Verify position tracking accuracy
python scripts/view_portfolio.py backtest AAPL \
  --start 2024-01-01 --end 2024-12-31 \
  --show-trades --show-equity

# Check equity curve: Should match portfolio value over time
```

**Validation Checklist**:
- [ ] Equity curve starts at initial capital
- [ ] Equity increases on winning trades
- [ ] Equity decreases on losing trades
- [ ] Final equity = initial capital + total P&L

---

### Step 7: Performance Metrics Validation (20-30 minutes)

**Purpose**: Verify accuracy of Sharpe ratio, drawdown, and other metrics.

#### Test 7.1: Returns Calculation
```bash
# Run 1-year backtest
python scripts/view_portfolio.py backtest \
  AAPL MSFT GOOGL NVDA META \
  --start 2024-01-01 --end 2024-12-31

# Note: Total Return %, Annualized Return %
```

**Manual Verification**:
```python
# Verify total return calculation:
# Total Return % = (Final Value - Initial Capital) / Initial Capital × 100

# Verify annualized return:
# If 1 year: Annualized Return = Total Return
# If <1 year: Annualized = (1 + Total Return) ^ (365/days) - 1
```

**Validation Checklist**:
- [ ] Total return matches manual calculation
- [ ] Annualized return correct for time period
- [ ] Returns reasonable given market conditions

#### Test 7.2: Sharpe Ratio
```bash
# Get Sharpe ratio for multiple strategies
python scripts/view_portfolio.py compare \
  AAPL MSFT GOOGL \
  --start 2024-01-01 --end 2024-12-31
```

**Validation Checklist**:
- [ ] Sharpe ratio in reasonable range (-1 to 3)
- [ ] Higher return strategies have higher Sharpe (usually)
- [ ] Sharpe accounts for risk-adjusted returns

**Manual Calculation** (optional):
```python
# Sharpe Ratio = (Mean Daily Return - Risk Free Rate) / Std Dev of Returns
# Risk Free Rate ≈ 0% for daily returns (or 4.5% annual / 252)
# Typical values: <1 (poor), 1-2 (good), >2 (excellent)
```

#### Test 7.3: Maximum Drawdown
```bash
# Run backtest with equity curve
python scripts/view_portfolio.py backtest \
  AAPL MSFT GOOGL NVDA \
  --start 2024-01-01 --end 2024-12-31 \
  --show-equity

# Note max drawdown %
```

**Validation Checklist**:
- [ ] Max drawdown shown as percentage
- [ ] Drawdown reasonable (10-30% typical for stocks)
- [ ] Drawdown date shown (when it occurred)

**Manual Verification**:
- [ ] Find peak equity in curve
- [ ] Find lowest point after peak
- [ ] Calculate: (Peak - Trough) / Peak × 100 = Drawdown %

#### Test 7.4: Benchmark Comparison
```bash
# Compare strategy vs SPY buy-and-hold
python scripts/compare_benchmark.py \
  --symbols AAPL MSFT GOOGL NVDA META \
  --benchmark SPY \
  --start 2024-01-01 --end 2024-12-31

# Expected: Both strategy and benchmark returns shown
```

**Validation Checklist**:
- [ ] Strategy return calculated
- [ ] Benchmark (SPY) return calculated
- [ ] Comparison shows outperformance/underperformance
- [ ] Metrics include: Returns, Sharpe, Drawdown, Trades

---

### Step 8: Universe Selection Validation (20-30 minutes)

**Purpose**: Test stock universe selection and filtering.

#### Test 8.1: Basic Universe Selection
```bash
# Select top 10 high-liquidity stocks
python scripts/select_universe.py \
  --name validation_test \
  --top-n 10 \
  --min-price 50 \
  --min-volume 10000000 \
  --save

# Expected: ~10 symbols selected (AAPL, MSFT, NVDA, etc.)
```

**Validation Checklist**:
- [ ] Seed list used (fast, <10 seconds)
- [ ] 10 symbols returned
- [ ] All symbols are valid tickers
- [ ] Saved to database

#### Test 8.2: Load Saved Universe
```bash
# Load previously saved universe
python scripts/select_universe.py --load validation_test

# Expected: Same 10 symbols loaded instantly
```

**Validation Checklist**:
- [ ] Symbols loaded from database
- [ ] Instant retrieval (<1 second)
- [ ] Symbols match saved list

#### Test 8.3: Different Filter Configurations
```bash
# Conservative (large-cap only)
python scripts/select_universe.py \
  --name large_cap \
  --top-n 20 \
  --min-price 100 \
  --min-volume 20000000 \
  --save

# Moderate
python scripts/select_universe.py \
  --name moderate \
  --top-n 50 \
  --min-price 20 \
  --min-volume 5000000 \
  --save
```

**Validation Checklist**:
- [ ] Conservative: Fewer symbols, higher quality
- [ ] Moderate: More symbols, broader coverage
- [ ] No invalid symbols (warrants, delisted, etc.)

#### Test 8.4: Universe in Backtest
```bash
# Load universe and run backtest
SYMBOLS=$(python scripts/select_universe.py --load large_cap | grep -E '^[A-Z]{1,5}$' | head -20 | tr '\n' ' ')

python scripts/view_portfolio.py backtest $SYMBOLS \
  --start 2024-01-01 --end 2024-12-31 \
  --capital 100000 \
  --max-positions 10

# Expected: Backtest runs on universe symbols
```

**Validation Checklist**:
- [ ] Universe loaded successfully
- [ ] Backtest runs on selected symbols
- [ ] Performance metrics calculated

---

### Step 9: Edge Cases and Error Handling (15-20 minutes)

**Purpose**: Test system robustness with edge cases.

#### Test 9.1: Invalid Symbols
```bash
# Try invalid symbols
python scripts/view_portfolio.py backtest INVALID_SYMBOL FAKE_STOCK \
  --start 2024-01-01 --end 2024-12-31

# Expected: Graceful error, no crash
```

**Validation Checklist**:
- [ ] Clear error message
- [ ] No stack trace (or user-friendly message)
- [ ] System doesn't crash

#### Test 9.2: Weekend/Holiday Dates
```bash
# Saturday as end date (non-trading day)
python scripts/view_data.py prices AAPL \
  --start 2024-01-01 --end 2024-01-06

# Expected: Last trading day used (Friday 2024-01-05)
```

**Validation Checklist**:
- [ ] System handles non-trading days gracefully
- [ ] Last valid trading day used
- [ ] No errors or warnings

#### Test 9.3: Empty Date Ranges
```bash
# Start date after end date
python scripts/view_data.py prices AAPL \
  --start 2024-12-31 --end 2024-01-01

# Expected: Clear error message
```

**Validation Checklist**:
- [ ] Validation error caught
- [ ] User-friendly error message
- [ ] No crash

#### Test 9.4: Insufficient Data
```bash
# Very short date range (< 50 days for MA50)
python scripts/test_strategy.py ma-crossover AAPL \
  -p fast_period=20 -p slow_period=50 \
  --start 2024-12-01 --end 2024-12-31

# Expected: Warning about insufficient data for indicators
```

**Validation Checklist**:
- [ ] Warning message displayed
- [ ] Partial results shown (or graceful skip)
- [ ] No crash

#### Test 9.5: Very Large Portfolios
```bash
# Load many symbols (stress test)
python scripts/select_universe.py --name stress_test --top-n 50 --save
SYMBOLS=$(python scripts/select_universe.py --load stress_test | grep -E '^[A-Z]{1,5}$' | head -50 | tr '\n' ' ')

python scripts/view_portfolio.py backtest $SYMBOLS \
  --start 2024-06-01 --end 2024-12-31 \
  --max-positions 20

# Expected: Slower but completes without errors
```

**Validation Checklist**:
- [ ] Handles large symbol list
- [ ] Performance acceptable (<5 min for 50 symbols)
- [ ] No memory errors

---

### Step 10: Integration and End-to-End Testing (30-40 minutes)

**Purpose**: Full system test simulating real-world usage.

#### Test 10.1: Complete Workflow
```bash
# 1. Select universe
python scripts/select_universe.py \
  --name e2e_test \
  --top-n 15 \
  --min-price 30 \
  --min-volume 5000000 \
  --save

# 2. Load universe
SYMBOLS=$(python scripts/select_universe.py --load e2e_test | grep -E '^[A-Z]{1,5}$' | head -15 | tr '\n' ' ')

# 3. Compare strategies
python scripts/view_portfolio.py compare $SYMBOLS \
  --start 2024-01-01 --end 2024-12-31

# 4. Run best strategy with details
python scripts/view_portfolio.py backtest $SYMBOLS \
  -p fast_period=10 -p slow_period=30 \
  --start 2024-01-01 --end 2024-12-31 \
  --capital 100000 \
  --max-positions 10 \
  --show-trades --show-equity

# 5. Benchmark comparison
python scripts/compare_benchmark.py \
  --symbols $SYMBOLS \
  --benchmark SPY \
  --start 2024-01-01 --end 2024-12-31
```

**Validation Checklist**:
- [ ] All steps complete without errors
- [ ] Data flows between steps correctly
- [ ] Performance metrics consistent across tools
- [ ] Results make sense and are reproducible

#### Test 10.2: Long-Term Backtest (2+ years)
```bash
# Multi-year backtest
python scripts/view_portfolio.py backtest \
  AAPL MSFT GOOGL NVDA META \
  --start 2022-01-01 --end 2024-12-31 \
  --capital 100000 \
  --show-equity

# Expected: ~3 years of data, more trades, longer-term performance
```

**Validation Checklist**:
- [ ] Data fetched for full period
- [ ] Trades span entire period
- [ ] Metrics reflect long-term performance
- [ ] Database size increased appropriately

#### Test 10.3: Reproducibility Test
```bash
# Run same backtest twice - should get identical results
python scripts/view_portfolio.py backtest AAPL MSFT GOOGL \
  --start 2024-01-01 --end 2024-12-31 \
  --capital 100000 > /tmp/run1.txt

python scripts/view_portfolio.py backtest AAPL MSFT GOOGL \
  --start 2024-01-01 --end 2024-12-31 \
  --capital 100000 > /tmp/run2.txt

diff /tmp/run1.txt /tmp/run2.txt
# Expected: No differences (identical output)
```

**Validation Checklist**:
- [ ] Results are deterministic
- [ ] Identical output on repeated runs
- [ ] No randomness in execution

---

## Validation Summary Checklist

After completing all tests, verify:

### Data Layer ✅
- [x] Data fetching works
- [x] Caching reduces API calls
- [x] Incremental updates work
- [x] Multiple symbols supported

### Strategy Layer ✅
- [x] Signals generated correctly
- [x] Indicators calculated accurately
- [x] Different parameters work
- [x] Signal quality verified

### Portfolio Layer ✅
- [x] Multi-symbol backtesting works
- [x] Allocation logic correct
- [x] Rebalancing frequencies supported
- [x] Strategy comparison works

### Risk Layer ✅
- [x] Position size limits enforced
- [x] Cash reserves maintained
- [x] Exposure limits working

### Execution Layer ✅
- [x] Trades executed correctly
- [x] Slippage applied
- [x] Commissions calculated
- [x] P&L tracking accurate

### Performance Metrics ✅
- [x] Returns calculated correctly
- [x] Sharpe ratio reasonable
- [x] Max drawdown accurate
- [x] Benchmark comparison works

### Universe Selection ✅
- [x] Selection filters work
- [x] Saved universes loadable
- [x] Different configs supported

### Edge Cases ✅
- [x] Invalid inputs handled
- [x] Non-trading days handled
- [x] Empty ranges caught
- [x] Large portfolios supported

### Integration ✅
- [x] End-to-end workflow works
- [x] Long-term backtests work
- [x] Results reproducible

---

## CLI Tools Reference

### 1. select_universe.py

Select stocks from universe of 8000+ US stocks based on filters.

**Command**: `python scripts/select_universe.py [OPTIONS]`

**Main Options**:
```bash
--name TEXT              Universe name (default: "default")
--top-n INTEGER          Number of stocks to select (default: 100)
--min-price FLOAT        Minimum stock price (default: 5.0)
--max-price FLOAT        Maximum stock price (optional)
--min-volume INTEGER     Minimum avg daily volume (default: 1,000,000)
--exchange TEXT          Exchange filter (NASDAQ, NYSE, NYSE ARCA)
--save                   Save universe to database
--load TEXT              Load saved universe by name
--refresh-cache          Refresh AlphaVantage listings cache
```

**Examples**:
```bash
# Select top 50 liquid stocks
python scripts/select_universe.py --name liquid_50 --top-n 50 --save

# High-price, high-volume only
python scripts/select_universe.py \
  --name premium \
  --min-price 100 \
  --min-volume 20000000 \
  --top-n 20 \
  --save

# Load saved universe
python scripts/select_universe.py --load liquid_50

# Refresh stock listings
python scripts/select_universe.py --refresh-cache
```

**Performance**:
- High filters (price≥50 or volume≥5M): Uses seed list, <10 seconds
- Low filters: Full scan, 2-5 minutes first run, <10 seconds cached

---

### 2. view_portfolio.py

Portfolio backtesting and strategy comparison.

**Commands**:
- `backtest`: Run backtest on portfolio
- `compare`: Compare multiple MA configurations

#### backtest Command

**Usage**: `python scripts/view_portfolio.py backtest SYMBOL [SYMBOL...] [OPTIONS]`

**Options**:
```bash
--strategy TEXT          Strategy name (default: "ma-crossover")
--start DATE             Start date YYYY-MM-DD (default: 1 year ago)
--end DATE               End date YYYY-MM-DD (default: today)
--capital FLOAT          Initial capital (default: 100000)
-p, --param KEY=VALUE    Strategy parameter (can repeat)
--rebalance TEXT         Frequency: daily/weekly/monthly (default: daily)
--max-positions INTEGER  Max concurrent positions (default: 10)
--show-trades            Display all trades
--show-equity            Display equity curve
```

**Examples**:
```bash
# Basic backtest
python scripts/view_portfolio.py backtest AAPL MSFT GOOGL

# With custom parameters
python scripts/view_portfolio.py backtest AAPL MSFT GOOGL NVDA META \
  -p fast_period=10 -p slow_period=30 \
  --capital 50000 \
  --rebalance weekly \
  --max-positions 3 \
  --show-trades

# Show equity curve
python scripts/view_portfolio.py backtest AAPL MSFT \
  --start 2024-01-01 --end 2024-12-31 \
  --show-equity
```

#### compare Command

**Usage**: `python scripts/view_portfolio.py compare SYMBOL [SYMBOL...] [OPTIONS]`

**Options**: Same as backtest (except --param, --strategy)

**Example**:
```bash
# Compare MA(10/30), MA(20/50), MA(50/200)
python scripts/view_portfolio.py compare AAPL MSFT GOOGL NVDA META \
  --start 2024-01-01 --end 2024-12-31 \
  --capital 100000
```

**Output**: Comparison table with returns, Sharpe, drawdown, trades for each config.

---

### 3. compare_benchmark.py

Compare strategy performance against buy-and-hold benchmark.

**Usage**: `python scripts/compare_benchmark.py [OPTIONS]`

**Options**:
```bash
--symbols TEXT           Space-separated symbols (required)
--benchmark TEXT         Benchmark symbol (default: "SPY")
--start DATE             Start date YYYY-MM-DD (default: 1 year ago)
--end DATE               End date YYYY-MM-DD (default: today)
--strategy TEXT          Strategy name (default: "ma_crossover")
-p, --param KEY=VALUE    Strategy parameter (can repeat)
--capital FLOAT          Initial capital (default: 100000)
```

**Examples**:
```bash
# Compare vs SPY
python scripts/compare_benchmark.py \
  --symbols "AAPL MSFT GOOGL NVDA META" \
  --benchmark SPY \
  --start 2024-01-01 --end 2024-12-31

# Compare vs QQQ with custom params
python scripts/compare_benchmark.py \
  --symbols "AAPL MSFT GOOGL NVDA" \
  --benchmark QQQ \
  -p fast_period=10 -p slow_period=30 \
  --capital 50000
```

**Output**: Side-by-side comparison of strategy vs benchmark with key metrics.

---

### 4. test_strategy.py

Test single-symbol strategies with detailed signal analysis.

**Usage**: `python scripts/test_strategy.py STRATEGY SYMBOL [OPTIONS]`

**Strategies**: `ma-crossover` (or `ma_crossover`, `mac`)

**Options**:
```bash
--start DATE             Start date YYYY-MM-DD (default: 1 year ago)
--end DATE               End date YYYY-MM-DD (default: today)
-p, --param KEY=VALUE    Strategy parameter (can repeat)
--capital FLOAT          Initial capital (default: 10000)
--signals-only           Only show signals, skip backtest
--show-data              Show data with indicators
```

**Examples**:
```bash
# Test MA Crossover on AAPL
python scripts/test_strategy.py ma-crossover AAPL

# With custom parameters
python scripts/test_strategy.py ma-crossover AAPL \
  -p fast_period=10 -p slow_period=30 \
  --start 2024-01-01 --end 2024-12-31

# Show signals only
python scripts/test_strategy.py ma-crossover AAPL --signals-only

# Show data with indicators
python scripts/test_strategy.py ma-crossover AAPL --show-data
```

---

### 5. view_data.py

View and manage market data.

**Commands**:
- `prices`: View price data
- `update`: Update/fetch market data

#### prices Command

**Usage**: `python scripts/view_data.py prices SYMBOL [SYMBOL...] [OPTIONS]`

**Options**:
```bash
--start DATE             Start date YYYY-MM-DD
--end DATE               End date YYYY-MM-DD
--days INTEGER           Last N days (alternative to start/end)
```

**Examples**:
```bash
# View last 30 days
python scripts/view_data.py prices AAPL --days 30

# View specific date range
python scripts/view_data.py prices AAPL MSFT \
  --start 2024-01-01 --end 2024-12-31

# Multiple symbols
python scripts/view_data.py prices AAPL MSFT GOOGL --days 10
```

#### update Command

**Usage**: `python scripts/view_data.py update SYMBOL [SYMBOL...] [OPTIONS]`

**Options**: Same as prices

**Example**:
```bash
# Update data for symbols
python scripts/view_data.py update AAPL MSFT GOOGL

# Update specific date range
python scripts/view_data.py update AAPL \
  --start 2022-01-01 --end 2024-12-31
```

---

## Common Workflows

### Workflow 1: Quick Strategy Test

```bash
# 1. Test strategy on single symbol
python scripts/test_strategy.py ma-crossover AAPL \
  --start 2024-01-01 --end 2024-12-31 \
  --show-data

# 2. If promising, test on portfolio
python scripts/view_portfolio.py backtest AAPL MSFT GOOGL \
  --start 2024-01-01 --end 2024-12-31 \
  --show-trades
```

### Workflow 2: Universe-Based Backtesting

```bash
# 1. Select universe
python scripts/select_universe.py \
  --name my_universe \
  --top-n 20 \
  --min-price 50 \
  --min-volume 10000000 \
  --save

# 2. Load and backtest
SYMBOLS=$(python scripts/select_universe.py --load my_universe | grep -E '^[A-Z]{1,5}$' | head -20 | tr '\n' ' ')

python scripts/view_portfolio.py backtest $SYMBOLS \
  --start 2024-01-01 --end 2024-12-31 \
  --capital 100000 \
  --max-positions 10 \
  --show-equity
```

### Workflow 3: Strategy Optimization

```bash
# 1. Compare different MA periods
python scripts/view_portfolio.py compare AAPL MSFT GOOGL \
  --start 2024-01-01 --end 2024-12-31

# 2. Test best config vs benchmark
python scripts/compare_benchmark.py \
  --symbols "AAPL MSFT GOOGL" \
  --benchmark SPY \
  -p fast_period=10 -p slow_period=30 \
  --start 2024-01-01 --end 2024-12-31

# 3. Run detailed backtest
python scripts/view_portfolio.py backtest AAPL MSFT GOOGL \
  -p fast_period=10 -p slow_period=30 \
  --start 2024-01-01 --end 2024-12-31 \
  --show-trades --show-equity
```

### Workflow 4: Long-Term Validation

```bash
# Multi-year backtest
python scripts/view_portfolio.py backtest \
  AAPL MSFT GOOGL NVDA META \
  --start 2022-01-01 --end 2024-12-31 \
  --capital 100000 \
  --show-equity > results_2022-2024.txt

# Review results
cat results_2022-2024.txt
```

---

## Troubleshooting

### Issue: "No data returned for symbol"

**Cause**: Symbol invalid, delisted, or data not available for date range.

**Solution**:
```bash
# Verify symbol exists
python -c "import yfinance as yf; print(yf.Ticker('SYMBOL').info)"

# Try different date range
python scripts/view_data.py prices SYMBOL --days 30
```

### Issue: "Rate limit exceeded"

**Cause**: Too many API calls to YFinance in short time.

**Solution**:
```bash
# Wait 1 hour, or use cached data
# Check cache:
sqlite3 data/market_data.db "SELECT symbol, COUNT(*) FROM price_data GROUP BY symbol;"

# Use cached data by running same command again
```

### Issue: "Insufficient data for indicators"

**Cause**: Date range shorter than longest MA period.

**Solution**:
```bash
# For MA(50/200), need at least 200 trading days (~10 months)
# Extend date range or use shorter MA periods

python scripts/test_strategy.py ma-crossover AAPL \
  -p fast_period=10 -p slow_period=30 \  # Shorter periods
  --start 2024-01-01 --end 2024-12-31
```

### Issue: "Import errors"

**Cause**: Missing dependencies.

**Solution**:
```bash
# Reinstall dependencies
pip install -r requirements.txt

# Verify TA-Lib
python -c "import talib; print('TA-Lib OK')"
```

### Issue: Database locked

**Cause**: Multiple processes accessing database simultaneously.

**Solution**:
```bash
# Wait for other process to finish, or:
rm data/market_data.db  # Delete and rebuild (loses cache)
```

### Issue: Slow performance

**Cause**: Large symbol list or long date range on first run.

**Solution**:
```bash
# Use smaller test first
python scripts/view_portfolio.py backtest AAPL MSFT \
  --start 2024-06-01 --end 2024-12-31  # 6 months instead of years

# Enable caching for future runs
# Second run will be much faster
```

---

## Database Management

### View Database Contents
```bash
# List all symbols
sqlite3 data/market_data.db "SELECT DISTINCT symbol FROM price_data ORDER BY symbol;"

# Count rows per symbol
sqlite3 data/market_data.db "SELECT symbol, COUNT(*) as rows FROM price_data GROUP BY symbol ORDER BY rows DESC;"

# View universes
sqlite3 data/market_data.db "SELECT DISTINCT name, date FROM universes ORDER BY date DESC;"
```

### Clean Database
```bash
# Delete all data
rm data/market_data.db

# Delete specific symbol
sqlite3 data/market_data.db "DELETE FROM price_data WHERE symbol = 'AAPL';"

# Vacuum (reclaim space)
sqlite3 data/market_data.db "VACUUM;"
```

---

## Next Steps After Validation

Once all validation tests pass:

1. **Document Results**: Update `PHASE1_SUMMARY.md` with validation results
2. **Fix Issues**: Address any bugs or edge cases found
3. **Decide Next Phase**:
   - **Option A**: Move to Phase 2 (Paper Trading)
   - **Option B**: Add more strategies or features to Phase 1
4. **Update Development Plan**: Mark Phase 1 as complete

---

## Contributing

When adding new CLI tools:

1. Use `click` for argument parsing
2. Add comprehensive `--help` documentation
3. Include examples in this README
4. Add to validation plan if testing critical functionality
5. Make executable: `chmod +x scripts/your_tool.py`

---

**Last Updated**: 2026-01-22
**Version**: Phase 1.5 (Universe Selection Complete)
