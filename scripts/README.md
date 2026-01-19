# CLI Scripts

This directory contains command-line tools for interacting with the AI Trader system.

## Available Scripts

### test_strategy.py

Test trading strategies on historical data with backtesting.

**Features**:
- Test any implemented strategy on historical stock data
- Customize strategy parameters from the command line
- Run backtests with configurable initial capital
- Compare strategy performance vs buy-and-hold
- View signals, indicators, and performance metrics

**Basic Usage**:
```bash
# Test MA Crossover strategy on AAPL for 2023
python scripts/test_strategy.py ma-crossover AAPL --start 2023-01-03 --end 2023-12-28

# Test with custom parameters
python scripts/test_strategy.py ma-crossover AAPL -p fast_period=10 -p slow_period=30

# Show indicator data
python scripts/test_strategy.py ma-crossover AAPL --show-data

# Use custom initial capital
python scripts/test_strategy.py ma-crossover AAPL --capital 50000
```

**Options**:
- `--start DATE`: Start date (YYYY-MM-DD), default: 1 year ago
- `--end DATE`: End date (YYYY-MM-DD), default: today
- `-p, --param KEY=VALUE`: Strategy parameter (can be used multiple times)
- `--capital FLOAT`: Initial capital for backtest (default: $10,000)
- `--signals-only`: Only show signals, skip backtest
- `--show-data`: Show data with calculated indicators

**Available Strategies**:
- `ma-crossover` (or `ma_crossover`, `mac`): Moving Average Crossover
  - Parameters: `fast_period` (default: 20), `slow_period` (default: 50)

See [EXAMPLE_OUTPUT.md](./EXAMPLE_OUTPUT.md) for detailed examples.

### view_data.py

View and manage market data.

**Basic Usage**:
```bash
# View price data for symbols
python scripts/view_data.py prices AAPL MSFT --days 30

# Update market data
python scripts/view_data.py update AAPL MSFT
```

## Requirements

All scripts require the project dependencies to be installed:

```bash
pip install -r requirements.txt
```

## Database

All data fetched by these scripts is cached in the SQLite database at `data/market_data.db`. Subsequent runs will use cached data when available, making them faster and reducing API calls.

To clear the cache:
```bash
rm data/market_data.db
```

## Known Issues

- The DataAPI incremental fetching has a boundary case issue when the end date is a non-trading day (weekend/holiday). This will be fixed in a future PR.
- Workaround: Use end dates that are known trading days (weekdays that are not holidays)

## Adding New Scripts

When creating new CLI scripts:

1. Add shebang: `#!/usr/bin/env python3`
2. Add docstring explaining the script's purpose
3. Use `click` for argument parsing
4. Make executable: `chmod +x scripts/your_script.py`
5. Add usage examples to this README
6. Add example output to EXAMPLE_OUTPUT.md if applicable

