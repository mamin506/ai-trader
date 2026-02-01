# CLI Monitoring Tool - User Guide

## Overview

The `monitor_trading.py` CLI tool provides real-time monitoring of your Alpaca paper trading account, including positions, performance metrics, and trading logs.

## Installation

The tool is included with the AI Trader project. Ensure all dependencies are installed:

```bash
pip install -r requirements.txt
```

## Usage

### Basic Commands

#### 1. Account Status

Display current account status, positions summary, and risk metrics:

```bash
python scripts/monitor_trading.py status
```

**Output includes**:
- Portfolio value and cash balance
- Number of open positions
- Daily P&L percentage
- Drawdown from peak
- Circuit breaker status

#### 2. Watch Mode (Auto-refresh)

Monitor account status with automatic updates:

```bash
python scripts/monitor_trading.py status --watch
python scripts/monitor_trading.py status -w  # Short form
```

**Options**:
- `--interval, -i`: Refresh interval in seconds (default: 10)

```bash
# Update every 5 seconds
python scripts/monitor_trading.py status --watch --interval 5
```

Press `Ctrl+C` to exit watch mode.

#### 3. Positions Detail

View detailed breakdown of all open positions:

```bash
python scripts/monitor_trading.py positions
```

**Output includes**:
- Symbol, shares, average cost
- Current market value
- Unrealized P&L ($ and %)
- Total portfolio value

**Watch mode**:
```bash
python scripts/monitor_trading.py positions --watch
```

#### 4. Performance Metrics

Display comprehensive performance statistics:

```bash
python scripts/monitor_trading.py performance
```

**Metrics shown**:
- Total return (%)
- Average daily return
- Sharpe ratio
- Maximum drawdown
- Win rate
- Total P&L ($)
- Current vs. peak portfolio value
- Trading days

#### 5. Recent Logs

View recent trading log entries:

```bash
python scripts/monitor_trading.py logs
```

**Options**:
- `--lines, -n`: Number of lines to show (default: 20)
- `--follow, -f`: Follow log output in real-time (like `tail -f`)

```bash
# Show last 50 lines
python scripts/monitor_trading.py logs --lines 50

# Follow logs in real-time
python scripts/monitor_trading.py logs --follow
```

#### 6. Order History

Display recent orders and their fill status:

```bash
python scripts/monitor_trading.py orders
```

**Options**:
- `--limit, -l`: Number of orders to show (default: 10)

```bash
# Show last 25 orders
python scripts/monitor_trading.py orders --limit 25
```

## Color Coding

The CLI uses color-coded output for easy interpretation:

- **Green**: Positive P&L, gains, healthy metrics
- **Red**: Negative P&L, losses, warnings
- **Yellow**: Caution levels (e.g., moderate drawdown)
- **Cyan**: Labels and headers

## Configuration

The monitoring tool automatically loads configuration from:
- `config/alpaca.yaml` - Alpaca settings and risk thresholds
- `.env` - API credentials (never commit this file!)

Ensure your `.env` file is properly configured:

```bash
ALPACA_API_KEY=your_api_key_here
ALPACA_SECRET_KEY=your_secret_key_here
ALPACA_BASE_URL=https://paper-api.alpaca.markets
ALPACA_DATA_URL=https://data.alpaca.markets
```

## Examples

### Monitor trading during market hours

```bash
# Terminal 1: Watch account status
python scripts/monitor_trading.py status --watch --interval 10

# Terminal 2: Watch positions
python scripts/monitor_trading.py positions --watch

# Terminal 3: Follow logs
python scripts/monitor_trading.py logs --follow
```

### Quick status check

```bash
# Check status
python scripts/monitor_trading.py status

# Check if any positions hit stop-loss
python scripts/monitor_trading.py positions

# Review performance
python scripts/monitor_trading.py performance
```

### End-of-day review

```bash
# Check final positions
python scripts/monitor_trading.py positions

# Review performance metrics
python scripts/monitor_trading.py performance

# Check recent orders
python scripts/monitor_trading.py orders --limit 20
```

## Troubleshooting

### Connection Errors

If you see connection errors:
1. Check your internet connection
2. Verify API credentials in `.env` are correct
3. Ensure Alpaca API is accessible (check status.alpaca.markets)

### "No positions" message

This is normal if you haven't made any trades yet or all positions have been closed.

### Circuit Breaker Active

If you see "Circuit Breaker: 🔴 ACTIVE":
- Trading has been halted due to risk limits
- Check the circuit breaker reason in the status output
- Review `config/alpaca.yaml` risk thresholds if needed
- Daily loss limit: 2% (default)
- Max drawdown: 5% (default)

### Performance data not available

Performance metrics require historical trading data. If you just started paper trading, this data will accumulate over time.

## Integration with Trading System

The monitoring tool reads data from:
- **AlpacaExecutor**: Live account data, positions, orders
- **DynamicRiskManager**: Risk metrics, circuit breaker status
- **PerformanceTracker**: Historical performance data

These components are automatically initialized when you run the CLI.

## Tips

1. **Use watch mode during active trading** to monitor real-time changes
2. **Set appropriate refresh intervals** - 5-10 seconds for active monitoring, 30-60 seconds for passive monitoring
3. **Keep logs open** in a separate terminal to catch any errors or warnings
4. **Check performance daily** to track progress and identify issues early
5. **Monitor circuit breaker status** - if triggered frequently, review risk thresholds

## Advanced Usage

### Custom Scripts

You can import the monitoring components in your own scripts:

```python
from src.utils.config import load_alpaca_config
from src.execution.alpaca_executor import AlpacaExecutor
from src.monitoring.performance_tracker import PerformanceTracker

# Load configuration
config, creds = load_alpaca_config()

# Initialize executor
executor = AlpacaExecutor(
    api_key=creds["api_key"],
    secret_key=creds["secret_key"],
    base_url=creds["base_url"],
)

# Get account info
account = executor.get_account_info()
print(f"Portfolio value: ${account.portfolio_value:,.2f}")
```

## Support

For issues or questions:
1. Check the logs: `python scripts/monitor_trading.py logs`
2. Review configuration: `config/alpaca.yaml`
3. Verify credentials: `.env` file
4. Check Alpaca API status: https://status.alpaca.markets

## See Also

- [Phase 2 Plan](PHASE2_PLAN.md) - Full Phase 2 implementation details
- [Alpaca API Documentation](https://alpaca.markets/docs/) - Official Alpaca docs
- `config/alpaca.yaml` - Risk thresholds and configuration
