#!/usr/bin/env python
"""Paper Trading CLI - Manual daily trading workflow trigger.

This script provides manual control over paper trading operations:
- check: Health check (market status, account info)
- rebalance: Execute daily rebalancing workflow
- report: Generate performance report
- status: Quick portfolio status

Usage:
    python scripts/paper_trading.py check
    python scripts/paper_trading.py rebalance
    python scripts/paper_trading.py report
    python scripts/paper_trading.py status
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

import yaml

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.strategy.ma_crossover import MACrossoverStrategy
from src.strategy.rsi_strategy import RSIStrategy
from src.strategy.macd_strategy import MACDStrategy
from src.strategy.ensemble import MultiStrategyEnsemble
from src.orchestration.workflows import DailyWorkflow, WorkflowConfig
from src.utils.alpaca_client import AlpacaClient
from src.utils.logging import get_logger
from src.monitoring.performance_tracker import PerformanceTracker

logger = get_logger(__name__)


def load_config(config_path: str = "config/paper_trading.yaml") -> dict:
    """Load paper trading configuration from YAML file.

    Args:
        config_path: Path to configuration file

    Returns:
        Configuration dictionary

    Raises:
        FileNotFoundError: If config file doesn't exist
    """
    config_file = project_root / config_path
    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_file}")

    with open(config_file) as f:
        config = yaml.safe_load(f)

    logger.info("Loaded configuration from %s", config_file)
    return config


def create_ensemble(config: dict) -> MultiStrategyEnsemble:
    """Create multi-strategy ensemble from configuration.

    Args:
        config: Configuration dictionary

    Returns:
        MultiStrategyEnsemble instance
    """
    strategies = []
    weights = []

    strategy_configs = config.get("strategies", {})

    # Strategy 1: MA Crossover
    if strategy_configs.get("ma_crossover", {}).get("enabled", False):
        params = strategy_configs["ma_crossover"]["params"]
        strategies.append(MACrossoverStrategy(params))
        weights.append(strategy_configs["ma_crossover"]["weight"])
        logger.info("Enabled MA Crossover strategy (weight: %.1f)", weights[-1])

    # Strategy 2: RSI
    if strategy_configs.get("rsi", {}).get("enabled", False):
        params = strategy_configs["rsi"]["params"]
        strategies.append(RSIStrategy(params))
        weights.append(strategy_configs["rsi"]["weight"])
        logger.info("Enabled RSI strategy (weight: %.1f)", weights[-1])

    # Strategy 3: MACD
    if strategy_configs.get("macd", {}).get("enabled", False):
        params = strategy_configs["macd"]["params"]
        strategies.append(MACDStrategy(params))
        weights.append(strategy_configs["macd"]["weight"])
        logger.info("Enabled MACD strategy (weight: %.1f)", weights[-1])

    if not strategies:
        raise ValueError("No strategies enabled in configuration")

    ensemble = MultiStrategyEnsemble(strategies, weights)
    logger.info("Created ensemble with %d strategies", len(strategies))

    return ensemble


def create_workflow(config: dict) -> DailyWorkflow:
    """Create DailyWorkflow from configuration.

    Args:
        config: Configuration dictionary

    Returns:
        DailyWorkflow instance
    """
    # Create AlpacaClient
    alpaca_client = AlpacaClient.from_env()

    # Create ensemble
    ensemble = create_ensemble(config)

    # Create workflow config
    portfolio_config = config.get("portfolio", {})
    risk_config = config.get("risk", {})

    workflow_config = WorkflowConfig(
        symbols=config["paper_trading"]["universe"],
        strategy=ensemble,
        initial_capital=portfolio_config.get("initial_capital", 100000.0),
        min_signal_threshold=portfolio_config.get("min_signal_threshold", 0.3),
        max_positions=portfolio_config.get("max_positions", 10),
        max_position_size=portfolio_config.get("max_position_size", 0.20),
        cash_buffer=portfolio_config.get("cash_buffer", 0.05),
    )

    # Create workflow
    workflow = DailyWorkflow(alpaca_client, workflow_config)

    logger.info("Created DailyWorkflow with %d symbols", len(workflow_config.symbols))

    return workflow


def check_command(config: dict):
    """Execute health check command.

    Runs market open workflow to verify:
    - API connection
    - Account status
    - Current positions
    """
    print("\n" + "=" * 60)
    print("PAPER TRADING HEALTH CHECK")
    print("=" * 60)

    workflow = create_workflow(config)

    try:
        result = workflow.market_open_workflow()

        print(f"\n✅ Health Check PASSED")
        print(f"\nAccount Status:")
        account = result["account_info"]
        print(f"  Cash: ${account.cash:,.2f}")
        print(f"  Buying Power: ${account.buying_power:,.2f}")
        print(f"  Portfolio Value: ${account.portfolio_value:,.2f}")

        print(f"\nPositions: {len(result['positions'])}")
        if result["positions"]:
            for symbol, position in result["positions"].items():
                print(f"  {symbol}: {position.shares} shares @ ${position.avg_cost:.2f}")

        print(f"\nTimestamp: {result['timestamp']}")

    except Exception as e:
        print(f"\n❌ Health Check FAILED: {e}")
        logger.error("Health check failed", exc_info=True)
        return 1

    return 0


def rebalance_command(config: dict):
    """Execute rebalancing command.

    Runs full rebalancing workflow:
    1. Fetch latest market data
    2. Generate signals
    3. Calculate target weights
    4. Validate risk
    5. Submit orders
    """
    print("\n" + "=" * 60)
    print("PAPER TRADING REBALANCE")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    workflow = create_workflow(config)

    try:
        result = workflow.rebalancing_workflow()

        print(f"\n✅ Rebalancing COMPLETED")

        print(f"\nSignals Generated:")
        for symbol, signal in result.get("signals", {}).items():
            emoji = "📈" if signal > 0.3 else "📉" if signal < -0.3 else "➡️"
            print(f"  {emoji} {symbol}: {signal:+.3f}")

        print(f"\nTarget Weights:")
        for symbol, weight in result.get("target_weights", {}).items():
            if symbol != "Cash":
                print(f"  {symbol}: {weight:.1%}")
        cash_weight = result.get("target_weights", {}).get("Cash", 0)
        print(f"  Cash: {cash_weight:.1%}")

        print(f"\nOrders:")
        print(f"  Submitted: {result.get('orders_submitted', 0)}")
        print(f"  Successful: {result.get('orders_successful', 0)}")
        print(f"  Rejected: {result.get('orders_rejected', 0)}")

        if result.get("execution_results"):
            print(f"\nOrder Details:")
            for order in result["execution_results"]:
                action_emoji = "🟢" if order.status == "filled" else "⚠️"
                print(f"  {action_emoji} {order.symbol}: {order.filled_qty} shares")

        print(f"\nTimestamp: {result['timestamp']}")

    except Exception as e:
        print(f"\n❌ Rebalancing FAILED: {e}")
        logger.error("Rebalancing failed", exc_info=True)
        return 1

    return 0


def report_command(config: dict):
    """Execute report command.

    Runs market close workflow:
    - Confirm orders filled
    - Update position tracking
    - Generate performance report
    """
    print("\n" + "=" * 60)
    print("PAPER TRADING END-OF-DAY REPORT")
    print("=" * 60)

    workflow = create_workflow(config)

    try:
        result = workflow.market_close_workflow()

        print(f"\n✅ Market Close Report")

        print(f"\nPortfolio Summary:")
        print(f"  Total Value: ${result['portfolio_value']:,.2f}")
        print(f"  Positions Value: ${result['positions_value']:,.2f}")
        print(f"  Cash: ${result['cash']:,.2f}")
        print(f"  Unrealized P&L: ${result['total_unrealized_pnl']:,.2f}")

        print(f"\nPositions ({result['positions_count']}):")
        for symbol, position in result.get("positions", {}).items():
            pnl = position.unrealized_pl
            pnl_emoji = "🟢" if pnl >= 0 else "🔴"
            print(f"  {pnl_emoji} {symbol}: {position.shares} shares, P&L: ${pnl:,.2f}")

        if result["open_orders"] > 0:
            print(f"\n⚠️ Warning: {result['open_orders']} open orders still pending")

        print(f"\nTimestamp: {result['timestamp']}")

    except Exception as e:
        print(f"\n❌ Report generation FAILED: {e}")
        logger.error("Report generation failed", exc_info=True)
        return 1

    return 0


def status_command(config: dict):
    """Execute quick status command.

    Shows quick portfolio snapshot without triggering workflows.
    """
    print("\n" + "=" * 60)
    print("PAPER TRADING STATUS")
    print("=" * 60)

    try:
        client = AlpacaClient.from_env()
        trading_client = client.get_trading_client()

        account = client.with_retry(trading_client.get_account)
        positions = client.with_retry(trading_client.get_all_positions)

        print(f"\n📊 Portfolio:")
        print(f"  Value: ${float(account.portfolio_value):,.2f}")
        print(f"  Cash: ${float(account.cash):,.2f}")
        print(f"  Positions: {len(positions)}")

        if positions:
            print(f"\n📈 Positions:")
            for pos in positions:
                pnl = float(pos.unrealized_pl)
                pnl_emoji = "🟢" if pnl >= 0 else "🔴"
                print(f"  {pnl_emoji} {pos.symbol}: {pos.qty} @ ${float(pos.current_price):.2f} (P&L: ${pnl:,.2f})")

    except Exception as e:
        print(f"\n❌ Status check FAILED: {e}")
        logger.error("Status check failed", exc_info=True)
        return 1

    return 0


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Paper Trading CLI - Manual daily workflow control",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  check      Health check (market status, account info)
  rebalance  Execute daily rebalancing workflow
  report     Generate end-of-day performance report
  status     Quick portfolio status snapshot

Examples:
  python scripts/paper_trading.py check
  python scripts/paper_trading.py rebalance
  python scripts/paper_trading.py report
  python scripts/paper_trading.py status
        """,
    )

    parser.add_argument(
        "command",
        choices=["check", "rebalance", "report", "status"],
        help="Command to execute",
    )

    parser.add_argument(
        "--config",
        default="config/paper_trading.yaml",
        help="Path to configuration file (default: config/paper_trading.yaml)",
    )

    args = parser.parse_args()

    # Load configuration
    try:
        config = load_config(args.config)
    except Exception as e:
        print(f"Error loading configuration: {e}")
        return 1

    # Execute command
    commands = {
        "check": check_command,
        "rebalance": rebalance_command,
        "report": report_command,
        "status": status_command,
    }

    return commands[args.command](config)


if __name__ == "__main__":
    sys.exit(main())
