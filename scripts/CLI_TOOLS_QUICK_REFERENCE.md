# CLI Tools Quick Reference

**Updated**: 2026-01-26 (Post-Refactoring)

## Quick Command Guide

### Universe Management
```bash
# Update seed list (every 2 weeks)
python scripts/update_seed_list.py

# Select universe
python scripts/select_universe.py --name liquid_50 --top-n 50 --save

# Load universe
python scripts/select_universe.py --load liquid_50
```

### Run Single Strategy
```bash
# List strategies
python scripts/run_strategy.py --list

# Run on symbols
python scripts/run_strategy.py --strategy rsi --symbols AAPL MSFT --start 2023-01-01 --end 2024-01-01

# Run on universe
python scripts/run_strategy.py --strategy ma_crossover --universe liquid_50 --start 2023-01-01 --end 2024-01-01
```

### Compare Strategies
```bash
python scripts/compare_strategies.py --symbols AAPL MSFT GOOGL --start 2023-01-01 --end 2024-01-01
```

### Other Tools
```bash
# View data
python scripts/view_data.py AAPL --days 30

# Compare vs benchmark
python scripts/compare_benchmark.py --symbols "AAPL MSFT" --benchmark SPY --start 2023-01-01 --end 2024-01-01

# View portfolio
python scripts/view_portfolio.py
```

## Available Tools

| Script | Purpose | Key Options |
|--------|---------|-------------|
| `update_seed_list.py` | Update seed list biweekly | None (interactive) |
| `select_universe.py` | Select universe from seed list | `--top-n`, `--min-price`, `--min-volume`, `--save` |
| `run_strategy.py` | Run single strategy backtest | `--strategy`, `--symbols`, `--universe`, `--start`, `--end` |
| `compare_strategies.py` | Compare multiple strategies | `--strategies`, `--symbols`, `--start`, `--end`, `--output` |
| `compare_benchmark.py` | Compare vs buy-and-hold | `--symbols`, `--benchmark`, `--start`, `--end` |
| `optimize_strategy.py` | Optimize strategy parameters | `--strategy`, `--symbol`, `--start`, `--end` |
| `view_data.py` | View/update market data | `--days`, `--start`, `--end` |
| `view_portfolio.py` | View portfolio status | None or `backtest`/`compare` subcommands |

## Available Strategies

Run `python scripts/run_strategy.py --list` to see full list.

**Common strategies:**
- `ma_crossover` - MA Cross (20/50)
- `ma_crossover_fast` - MA Cross (10/30)
- `ma_crossover_slow` - MA Cross (50/200)
- `rsi` - RSI (14, 30/70)
- `rsi_aggressive` - RSI (14, 40/60)
- `macd` - MACD (12/26/9)
- `bollinger_bands` - Bollinger Bands (20, 2.0)
- `bollinger_bands_tight` - Bollinger Bands (20, 1.5)

## Typical Workflow

```bash
# 1. Update seed list (every 2 weeks)
python scripts/update_seed_list.py

# 2. Select universe
python scripts/select_universe.py --name liquid_50 --top-n 50 --save

# 3. Test single strategy
python scripts/run_strategy.py \\
    --strategy rsi \\
    --universe liquid_50 \\
    --start 2023-01-01 --end 2024-01-01

# 4. Compare strategies
python scripts/compare_strategies.py \\
    --symbols AAPL MSFT GOOGL \\
    --start 2023-01-01 --end 2024-01-01 \\
    --output results.csv

# 5. Optimize best strategy
python scripts/optimize_strategy.py \\
    --strategy rsi \\
    --symbol AAPL \\
    --start 2023-01-01 --end 2024-01-01
```

## Important Notes

- **Seed list**: Stored in `data/seed_list.json`, update biweekly
- **Data cache**: Market data cached in `data/market_data.db`
- **Universes**: Saved universes stored in database
- **Run from project root**: All scripts should be run from `/workspaces/ai-trader`

## Post-Refactoring Changes (2026-01-26)

### What Changed
- ❌ **Removed**: AlphaVantage provider (full market scans)
- ❌ **Removed**: `--refresh-cache` and `--exchange` options
- ✅ **Added**: `update_seed_list.py` for biweekly updates
- ✅ **Added**: `run_strategy.py` for single strategy backtests
- ✅ **Changed**: `select_universe.py` now uses seed list only

### Migration Guide

**Old way (no longer works):**
```bash
# This will error
python scripts/select_universe.py --refresh-cache
python scripts/select_universe.py --exchange NASDAQ NYSE
```

**New way:**
```bash
# Update seed list instead
python scripts/update_seed_list.py

# No need for --exchange (always uses seed list)
python scripts/select_universe.py --name my_universe --top-n 50 --save
```

## Getting Help

For detailed help on any script:
```bash
python scripts/SCRIPT_NAME.py --help
```

For complete documentation, see [README.md](README.md) in this directory.
