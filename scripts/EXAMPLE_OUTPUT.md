# test_strategy.py - Example Output

This document shows example usage of the strategy testing CLI tool.

## Basic Usage

```bash
python scripts/test_strategy.py ma-crossover AAPL --start 2023-01-03 --end 2023-12-28
```

### Expected Output:

```
======================================================================
AI Trader - Strategy Testing Tool
======================================================================
Strategy:      ma-crossover
Symbol:        AAPL
Period:        2023-01-03 to 2023-12-28
Initial Cap:   $10,000.00
======================================================================

Initializing APIs...
Loading strategy: ma-crossover...
✓ Strategy loaded with params: {'fast_period': 20, 'slow_period': 50, 'min_required_rows': 60}

Fetching historical data for AAPL...
✓ Fetched 249 trading days

Generating trading signals...
✓ Generated 249 signals:
  - Buy signals:  2
  - Sell signals: 1
  - Hold signals: 246

Signal Timeline:
  2023-04-12 - BUY
  2023-07-19 - SELL
  2023-11-15 - BUY

----------------------------------------------------------------------
Running Backtest...
----------------------------------------------------------------------

BACKTEST RESULTS
======================================================================
Initial Capital:        $   10,000.00
Final Value:            $   11,234.56

Strategy Return:            12.35%
Buy & Hold Return:          48.20%

Alpha (vs Buy & Hold):     -35.85%

Total Trades:                    3
Buy Signals:                     2
Sell Signals:                    1
Round Trips:                     1
======================================================================

✗ Strategy UNDERPERFORMED buy-and-hold
```

## Custom Strategy Parameters

```bash
python scripts/test_strategy.py ma-crossover AAPL \\
    --start 2023-01-03 --end 2023-12-28 \\
    -p fast_period=10 -p slow_period=30
```

This tests a faster MA crossover strategy (10/30 instead of default 20/50).

## Show Data with Indicators

```bash
python scripts/test_strategy.py ma-crossover AAPL \\
    --start 2023-01-03 --end 2023-12-28 \\
    --show-data
```

Adds indicator values at the end:

```
----------------------------------------------------------------------
Strategy Data (last 10 rows)
----------------------------------------------------------------------
             close    fast_ma    slow_ma  signal     volume
date
2023-12-14  197.96  191.47525  187.82900     0.0   70404200
2023-12-15  197.57  192.09300  188.25340     0.0   83622100
2023-12-18  195.89  192.43750  188.66920     0.0   55751900
2023-12-19  196.94  192.87600  189.10480     0.0   40714100
2023-12-20  194.83  193.09800  189.48520     0.0   52242800
2023-12-21  194.68  193.28550  189.85800     0.0   46480500
2023-12-22  193.60  193.36450  190.17620     0.0   37122800
2023-12-26  193.05  193.40100  190.47140     0.0   28919300
2023-12-27  193.15  193.45875  190.76900     0.0   48087700
2023-12-28  193.58  193.56125  191.07940     0.0   34049900
```

## Signals Only (Skip Backtest)

```bash
python scripts/test_strategy.py ma-crossover AAPL \\
    --start 2023-01-03 --end 2023-12-28 \\
    --signals-only
```

Shows only the signal generation without running the backtest:

```
...
✓ Generated 249 signals:
  - Buy signals:  2
  - Sell signals: 1
  - Hold signals: 246

Signal Timeline:
  2023-04-12 - BUY
  2023-07-19 - SELL
  2023-11-15 - BUY

(Skipping backtest as --signals-only was specified)
```

## Custom Initial Capital

```bash
python scripts/test_strategy.py ma-crossover AAPL \\
    --start 2023-01-03 --end 2023-12-28 \\
    --capital 50000
```

Tests with $50,000 initial capital instead of the default $10,000.

## Help

```bash
python scripts/test_strategy.py --help
```

Shows all available options and examples.

## Notes

- Default date range is last 365 days if not specified
- Strategy parameters can be specified multiple times with `-p key=value`
- The tool automatically detects parameter types (int, float, or string)
- All data is cached in the database for faster subsequent runs

