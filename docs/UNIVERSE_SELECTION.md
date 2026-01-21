# Universe Selection Layer

## Overview

The Universe Selection Layer filters and ranks stocks to create a focused trading universe before applying strategies. This reduces data costs and improves strategy focus.

## Why Universe Selection?

**Problem**: Analyzing all 8,000+ US stocks is expensive and unnecessary.

**Solution**: Pre-filter to 50-100 high-quality stocks based on:
- Liquidity (avg daily volume)
- Price range (avoid penny stocks)
- Market cap (size preference)
- Exchange (NASDAQ, NYSE, etc.)

**Benefits**:
- ✅ Reduced data fetching costs
- ✅ Faster backtests
- ✅ Focus on tradeable stocks
- ✅ Realistic portfolio constraints

## Architecture

```
UniverseAPI
    ├── StaticUniverseSelector
    │   ├── AlphaVantageProvider (fetch all US stocks)
    │   └── YFinanceProvider (get price/volume data)
    └── DatabaseManager (save/load universes)
```

## Quick Start

### 1. Select Universe

```python
from src.api.universe_api import UniverseAPI

api = UniverseAPI()

# Select top 50 most liquid stocks
symbols = api.select_universe(
    name='liquid_50',
    top_n=50,
    min_price=10.0,
    min_avg_volume=2_000_000,
    save=True,
)

print(f"Selected {len(symbols)} stocks: {symbols[:10]}...")
```

### 2. Load Saved Universe

```python
# Load most recent selection
symbols = api.load_universe('liquid_50')

# Load specific date
symbols = api.load_universe('liquid_50', date='2024-01-15')
```

### 3. Use in Backtest

```python
from src.api.backtest_api import BacktestAPI

backtest_api = BacktestAPI()

# Run strategy on selected universe
result = backtest_api.run_ma_crossover(
    symbols=symbols,
    start_date='2024-01-01',
    end_date='2024-12-31',
)
```

## CLI Tool

### Basic Usage

```bash
# Select top 50 liquid stocks
python scripts/select_universe.py --name liquid_50 --top-n 50 --save

# Load saved universe
python scripts/select_universe.py --load liquid_50

# Refresh listings cache
python scripts/select_universe.py --refresh-cache
```

### Advanced Filters

```bash
# Mid-price stocks ($20-$200)
python scripts/select_universe.py \
    --name mid_price \
    --min-price 20 \
    --max-price 200 \
    --min-volume 5000000 \
    --top-n 100 \
    --save

# NASDAQ only
python scripts/select_universe.py \
    --name nasdaq_liquid \
    --exchange NASDAQ \
    --top-n 50 \
    --save
```

## Configuration

### Default Filters

```python
StaticUniverseSelector(
    exchanges=['NASDAQ', 'NYSE', 'NYSE ARCA'],
    min_price=5.0,                # Avoid penny stocks
    max_price=None,               # No upper limit
    min_avg_volume=1_000_000,     # 1M shares/day minimum
    min_market_cap=None,          # Not filtered (requires fundamental data)
    max_market_cap=None,
)
```

### Customization

```python
# Custom filters
selector = StaticUniverseSelector(
    exchanges=['NASDAQ'],
    min_price=20.0,
    max_price=500.0,
    min_avg_volume=5_000_000,
)

symbols = selector.select(top_n=50)
```

## Data Sources

### AlphaVantage

**What**: Complete list of US-listed stocks and ETFs

**API Endpoint**: `https://www.alphavantage.co/query?function=LISTING_STATUS&apikey=demo`

**Update Frequency**: Daily

**Columns**:
- symbol: Ticker symbol
- name: Company name
- exchange: NASDAQ, NYSE, NYSE ARCA, etc.
- assetType: Stock or ETF
- ipoDate: IPO date
- status: Active or Delisted

**Caching**: Cached in `data/universe/alphavantage_listings.csv`

### YFinance

**What**: Price and volume data for filtering

**Usage**: Fetches last 30 days of price data to calculate:
- Current price
- Average daily volume

**Note**: Market cap requires shares outstanding (not available in daily bars). Planned for Phase 2 with fundamental data.

## Database Schema

```sql
CREATE TABLE universes (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,           -- Universe name
    symbol TEXT NOT NULL,         -- Stock symbol
    date TEXT NOT NULL,           -- Selection date
    rank INTEGER,                 -- Ranking (1 = best)
    metadata TEXT,                -- JSON metadata
    created_at TEXT NOT NULL,
    UNIQUE(name, symbol, date)
);
```

## Workflow

### 1. Fetch Listings (Daily)

```python
api = UniverseAPI()

# Refresh listings cache (once per day)
count = api.refresh_listings_cache()
print(f"Fetched {count} listings")
```

### 2. Select Universe (On-Demand or Scheduled)

```python
# Select universe for today
symbols = api.select_universe(
    name='default',
    top_n=100,
    save=True,
)
```

### 3. Use in Strategy

```python
# Backtest on universe
from src.api.backtest_api import BacktestAPI

backtest_api = BacktestAPI()
result = backtest_api.run_ma_crossover(
    symbols=symbols,
    start_date='2024-01-01',
    end_date='2024-12-31',
)
```

## Examples

### Example 1: Top 50 Liquid Stocks

```python
api = UniverseAPI()

symbols = api.select_universe(
    name='liquid_50',
    top_n=50,
    min_price=10.0,
    min_avg_volume=2_000_000,
    save=True,
)

print(f"Selected: {symbols[:10]}...")
# Output: Selected: ['AAPL', 'MSFT', 'NVDA', 'TSLA', ...]
```

### Example 2: Mid-Cap Growth Stocks

```python
symbols = api.select_universe(
    name='mid_cap_growth',
    top_n=100,
    min_price=20.0,
    max_price=200.0,
    min_avg_volume=1_000_000,
    # min_market_cap=5e9,    # $5B (Phase 2)
    # max_market_cap=50e9,   # $50B (Phase 2)
    save=True,
)
```

### Example 3: NASDAQ Tech Stocks

```python
symbols = api.select_universe(
    name='nasdaq_tech',
    top_n=50,
    exchanges=['NASDAQ'],
    min_price=15.0,
    min_avg_volume=3_000_000,
    save=True,
)
```

### Example 4: Historical Backtest with Universe

```python
from datetime import datetime
from src.api.backtest_api import BacktestAPI

# Select universe for backtest period
symbols = api.select_universe(
    name='backtest_universe',
    date=datetime(2024, 1, 1),
    top_n=50,
    save=True,
)

# Run backtest
backtest_api = BacktestAPI()
result = backtest_api.run_ma_crossover(
    symbols=symbols,
    start_date='2024-01-01',
    end_date='2024-12-31',
)

print(f"Total Return: {result.total_return_pct:.2f}%")
```

## Ranking Methods

### Phase 1.5: Liquidity-Based

Current implementation ranks by average volume (higher = better).

**Pros**:
- Simple
- Ensures tradeable stocks
- Low slippage

**Cons**:
- No fundamental or technical factors

### Phase 2+: Advanced Ranking

Future enhancements:
- **Momentum**: Price momentum over 3/6/12 months
- **Value**: P/E ratio, P/B ratio
- **Quality**: ROE, profit margins, debt ratios
- **Technical**: RSI, moving average trends
- **Composite Score**: Weighted combination

## Best Practices

### 1. Refresh Listings Regularly

```bash
# Add to cron (daily at 8 AM)
0 8 * * * cd /path/to/ai-trader && python scripts/select_universe.py --refresh-cache
```

### 2. Rebalance Universe Periodically

```python
# Monthly rebalancing
from datetime import datetime

# First day of month
if datetime.now().day == 1:
    symbols = api.select_universe(
        name='default',
        top_n=100,
        save=True,
    )
```

### 3. Avoid Survivorship Bias

When backtesting historical periods:
- Save universe snapshots for each rebalance date
- Don't use current listings for historical backtests
- AlphaVantage includes delisted stocks (use `status` filter)

### 4. Filter for Liquidity

Always set minimum volume to avoid:
- High slippage
- Wide bid-ask spreads
- Difficulty exiting positions

Recommended: `min_avg_volume >= 1_000_000` (1M shares/day)

### 5. Consider Transaction Costs

More stocks = more trades = higher costs

Balance:
- **Too many stocks (500+)**: High transaction costs
- **Too few stocks (10-20)**: High concentration risk
- **Sweet spot (50-100)**: Good diversification, manageable costs

## Limitations (Phase 1.5)

1. **Market Cap Filtering**: Not implemented (requires fundamental data)
   - Workaround: Use price as rough proxy (higher price often = higher market cap)

2. **Static Universe**: Same stocks until manually updated
   - Phase 2: Automatic rebalancing

3. **No Fundamental Factors**: Only price/volume filtering
   - Phase 2: Add P/E, revenue growth, etc.

4. **No Sector Filtering**: Can't filter by industry
   - Phase 2: Add sector/industry metadata

## Troubleshooting

### Issue: "No universe found"

```python
# Check available universes
dates = api.get_universe_dates('my_universe')
print(f"Available dates: {dates}")
```

### Issue: "API rate limit exceeded"

AlphaVantage free tier has no rate limits for LISTING_STATUS endpoint.

If using paid tier or hitting limits:
```python
# Use cache (default)
provider.fetch_listings(use_cache=True, max_cache_age_days=1)
```

### Issue: "Too few stocks selected"

Filters may be too strict. Relax them:
```python
symbols = api.select_universe(
    min_price=3.0,        # Lower (was 5.0)
    min_avg_volume=500_000,  # Lower (was 1M)
    top_n=100,
)
```

## API Reference

### UniverseAPI

```python
class UniverseAPI:
    def select_universe(
        name: str = "default",
        date: Optional[str] = None,
        top_n: int = 100,
        exchanges: Optional[list[str]] = None,
        min_price: float = 5.0,
        max_price: Optional[float] = None,
        min_avg_volume: float = 1_000_000,
        min_market_cap: Optional[float] = None,
        max_market_cap: Optional[float] = None,
        save: bool = False,
    ) -> list[str]:
        """Select stocks for universe."""

    def load_universe(
        name: str,
        date: Optional[str] = None,
    ) -> list[str]:
        """Load saved universe."""

    def get_universe_dates(name: str) -> list[str]:
        """Get dates for which universe exists."""

    def refresh_listings_cache() -> int:
        """Refresh stock listings from AlphaVantage."""
```

## Next Steps (Phase 2)

1. **Fundamental Filters**: Market cap, P/E ratio, revenue growth
2. **Advanced Ranking**: Momentum, value, quality scores
3. **Sector Filters**: Technology, healthcare, financials, etc.
4. **Automatic Rebalancing**: Scheduled universe updates
5. **Backtesting Integration**: Universe snapshots at each rebalance date
6. **Multiple Providers**: Polygon.io, EDGAR, Yahoo Finance screener

## Summary

**Universe Selection Layer provides:**
- ✅ Filter 8000+ stocks → 50-100 focused universe
- ✅ Save/load universes from database
- ✅ CLI tool for manual selection
- ✅ Integration with BacktestAPI
- ✅ Liquidity-based ranking (Phase 1.5)
- 🔜 Advanced ranking and filters (Phase 2)

**Key Workflow**:
1. Refresh listings (daily)
2. Select universe with filters
3. Save to database
4. Use in backtest/live trading
