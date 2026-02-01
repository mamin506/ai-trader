#!/usr/bin/env python3
"""CLI tool for monitoring paper trading activity.

This script provides real-time monitoring of account status, positions,
performance metrics, and trading logs.

Usage:
    python scripts/monitor_trading.py status
    python scripts/monitor_trading.py positions
    python scripts/monitor_trading.py performance
    python scripts/monitor_trading.py logs
    python scripts/monitor_trading.py orders
    python scripts/monitor_trading.py status --watch
"""

import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.config import load_alpaca_config
from src.execution.alpaca_executor import AlpacaExecutor
from src.risk.dynamic_risk_manager import DynamicRiskManager
from src.monitoring.performance_tracker import PerformanceTracker


console = Console()


def create_status_table(executor: AlpacaExecutor, risk_manager: DynamicRiskManager) -> Table:
    """Create status summary table.

    Args:
        executor: AlpacaExecutor instance
        risk_manager: DynamicRiskManager instance

    Returns:
        Rich Table with account status
    """
    table = Table(title="📊 Account Status", show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Value", style="green")

    try:
        # Get account info
        account = executor.get_account_info()
        positions = executor.get_positions()

        # Get risk summary
        risk_summary = risk_manager.get_summary()

        # Portfolio metrics
        table.add_row("Portfolio Value", f"${account.portfolio_value:,.2f}")
        table.add_row("Cash", f"${account.cash:,.2f}")
        table.add_row("Positions Value", f"${account.positions_value:,.2f}")
        table.add_row("Buying Power", f"${account.buying_power:,.2f}")

        # Position count
        table.add_row("", "")  # Separator
        table.add_row("Open Positions", str(len(positions)))
        table.add_row("Tracked Positions", str(risk_summary["positions_tracked"]))

        # Risk metrics
        table.add_row("", "")  # Separator
        daily_pnl = risk_summary.get("daily_pnl_pct", 0.0)
        daily_pnl_color = "green" if daily_pnl >= 0 else "red"
        daily_pnl_text = Text(f"{daily_pnl:+.2%}", style=daily_pnl_color)
        table.add_row("Daily P&L", str(daily_pnl_text))

        drawdown = risk_summary.get("drawdown_from_peak", 0.0)
        drawdown_color = "green" if drawdown >= -0.02 else "yellow" if drawdown >= -0.05 else "red"
        drawdown_text = Text(f"{drawdown:.2%}", style=drawdown_color)
        table.add_row("Drawdown from Peak", str(drawdown_text))

        # Circuit breaker status
        cb_active = risk_summary.get("circuit_breaker_active", False)
        cb_status = Text("🔴 ACTIVE" if cb_active else "✅ OK", style="red" if cb_active else "green")
        table.add_row("Circuit Breaker", str(cb_status))

        if cb_active:
            cb_reason = risk_summary.get("circuit_breaker_reason", "Unknown")
            table.add_row("CB Reason", cb_reason)

    except Exception as e:
        table.add_row("Error", str(e), style="red")

    return table


def create_positions_table(executor: AlpacaExecutor) -> Table:
    """Create positions detail table.

    Args:
        executor: AlpacaExecutor instance

    Returns:
        Rich Table with position details
    """
    table = Table(title="📈 Current Positions", show_header=True, header_style="bold magenta")
    table.add_column("Symbol", style="cyan", no_wrap=True)
    table.add_column("Shares", justify="right")
    table.add_column("Avg Cost", justify="right")
    table.add_column("Market Value", justify="right")
    table.add_column("P&L", justify="right")
    table.add_column("P&L %", justify="right")

    try:
        positions = executor.get_positions()

        if not positions:
            table.add_row("No positions", "", "", "", "", "")
            return table

        total_value = 0.0
        total_pnl = 0.0

        for symbol, position in positions.items():
            pnl_pct = (
                position.unrealized_pnl / position.cost_basis * 100
                if position.cost_basis > 0
                else 0.0
            )

            # Color code P&L
            pnl_color = "green" if position.unrealized_pnl >= 0 else "red"
            pnl_text = Text(f"${position.unrealized_pnl:+,.2f}", style=pnl_color)
            pnl_pct_text = Text(f"{pnl_pct:+.2f}%", style=pnl_color)

            table.add_row(
                symbol,
                str(position.shares),
                f"${position.avg_cost:.2f}",
                f"${position.market_value:,.2f}",
                str(pnl_text),
                str(pnl_pct_text),
            )

            total_value += position.market_value
            total_pnl += position.unrealized_pnl

        # Add total row
        table.add_row("", "", "", "", "", "", end_section=True)
        total_pnl_color = "green" if total_pnl >= 0 else "red"
        total_pnl_text = Text(f"${total_pnl:+,.2f}", style=total_pnl_color)

        table.add_row(
            "TOTAL",
            "",
            "",
            f"${total_value:,.2f}",
            str(total_pnl_text),
            "",
            style="bold",
        )

    except Exception as e:
        table.add_row("Error", str(e), "", "", "", "", style="red")

    return table


def create_performance_table(tracker: PerformanceTracker) -> Table:
    """Create performance metrics table.

    Args:
        tracker: PerformanceTracker instance

    Returns:
        Rich Table with performance metrics
    """
    table = Table(title="📊 Performance Metrics", show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Value", style="green")

    try:
        metrics = tracker.get_performance_metrics()
        latest = tracker.get_latest_performance()

        if latest:
            # Returns
            total_return = metrics["total_return"]
            return_color = "green" if total_return >= 0 else "red"
            return_text = Text(f"{total_return:+.2%}", style=return_color)
            table.add_row("Total Return", str(return_text))

            daily_mean = metrics["daily_returns_mean"]
            table.add_row("Avg Daily Return", f"{daily_mean:.4%}")

            # Risk metrics
            table.add_row("", "")  # Separator
            table.add_row("Sharpe Ratio", f"{metrics['sharpe_ratio']:.2f}")

            max_dd = metrics["max_drawdown"]
            dd_color = "green" if max_dd >= -0.05 else "yellow" if max_dd >= -0.10 else "red"
            dd_text = Text(f"{max_dd:.2%}", style=dd_color)
            table.add_row("Max Drawdown", str(dd_text))

            # Win rate
            table.add_row("", "")  # Separator
            win_rate = metrics["win_rate"]
            table.add_row("Win Rate", f"{win_rate:.1%}")

            # P&L
            total_pnl = metrics["total_pnl"]
            pnl_color = "green" if total_pnl >= 0 else "red"
            pnl_text = Text(f"${total_pnl:+,.2f}", style=pnl_color)
            table.add_row("Total P&L", str(pnl_text))

            # Portfolio value
            table.add_row("", "")  # Separator
            table.add_row("Current Value", f"${metrics['current_value']:,.2f}")
            table.add_row("Peak Value", f"${metrics['peak_value']:,.2f}")
            if metrics["peak_date"]:
                table.add_row("Peak Date", metrics["peak_date"])

            # Trading days
            table.add_row("", "")  # Separator
            table.add_row("Trading Days", str(metrics["num_days"]))

        else:
            table.add_row("No performance data", "")

    except Exception as e:
        table.add_row("Error", str(e), style="red")

    return table


@click.group()
def cli():
    """AI Trader - Paper Trading Monitor.

    Real-time monitoring tool for Alpaca paper trading account.
    """
    pass


@cli.command()
@click.option("--watch", "-w", is_flag=True, help="Auto-refresh mode (updates every 10 seconds)")
@click.option("--interval", "-i", default=10, help="Refresh interval in seconds (default: 10)")
def status(watch: bool, interval: int):
    """Show account status and risk metrics."""
    try:
        # Load configuration
        config, creds = load_alpaca_config()

        # Initialize executor and risk manager
        executor = AlpacaExecutor(
            api_key=creds["api_key"],
            secret_key=creds["secret_key"],
            base_url=creds["base_url"],
        )

        risk_manager = DynamicRiskManager.from_config(config.to_dict())

        # Sync positions
        positions = executor.get_positions()
        risk_manager.sync_positions(list(positions.values()))

        # Get account info and update portfolio value
        account = executor.get_account_info()
        risk_manager.update_portfolio_value(account.portfolio_value)

        if watch:
            # Watch mode with auto-refresh
            console.print(f"[bold green]Monitoring account (refresh every {interval}s). Press Ctrl+C to exit.[/bold green]\n")

            try:
                while True:
                    # Clear screen and show status
                    console.clear()
                    console.print(f"[dim]Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/dim]\n")

                    # Refresh data
                    risk_manager.sync_positions(list(executor.get_positions().values()))
                    account = executor.get_account_info()
                    risk_manager.update_portfolio_value(account.portfolio_value())

                    # Display table
                    table = create_status_table(executor, risk_manager)
                    console.print(table)

                    time.sleep(interval)

            except KeyboardInterrupt:
                console.print("\n[yellow]Monitoring stopped.[/yellow]")

        else:
            # Single display
            table = create_status_table(executor, risk_manager)
            console.print(table)

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        sys.exit(1)


@cli.command()
@click.option("--watch", "-w", is_flag=True, help="Auto-refresh mode")
@click.option("--interval", "-i", default=10, help="Refresh interval in seconds")
def positions(watch: bool, interval: int):
    """Show detailed position breakdown."""
    try:
        config, creds = load_alpaca_config()
        executor = AlpacaExecutor(
            api_key=creds["api_key"],
            secret_key=creds["secret_key"],
            base_url=creds["base_url"],
        )

        if watch:
            console.print(f"[bold green]Monitoring positions (refresh every {interval}s). Press Ctrl+C to exit.[/bold green]\n")

            try:
                while True:
                    console.clear()
                    console.print(f"[dim]Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/dim]\n")

                    table = create_positions_table(executor)
                    console.print(table)

                    time.sleep(interval)

            except KeyboardInterrupt:
                console.print("\n[yellow]Monitoring stopped.[/yellow]")

        else:
            table = create_positions_table(executor)
            console.print(table)

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        sys.exit(1)


@cli.command()
def performance():
    """Show performance metrics (Sharpe, drawdown, returns)."""
    try:
        config, creds = load_alpaca_config()

        # Initialize tracker
        initial_capital = config.get("portfolio.initial_capital", 100000.0)
        tracker = PerformanceTracker(initial_capital=initial_capital)

        # TODO: Load historical performance data from database/file

        table = create_performance_table(tracker)
        console.print(table)

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        sys.exit(1)


@cli.command()
@click.option("--lines", "-n", default=20, help="Number of log lines to show")
@click.option("--follow", "-f", is_flag=True, help="Follow log output (like tail -f)")
def logs(lines: int, follow: bool):
    """Tail recent trading logs."""
    try:
        # TODO: Implement log tailing
        console.print("[yellow]Log tailing not yet implemented.[/yellow]")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        sys.exit(1)


@cli.command()
@click.option("--limit", "-l", default=10, help="Number of orders to show")
def orders(limit: int):
    """Show recent orders and fills."""
    try:
        config, creds = load_alpaca_config()
        executor = AlpacaExecutor(
            api_key=creds["api_key"],
            secret_key=creds["secret_key"],
            base_url=creds["base_url"],
        )

        # TODO: Implement order history display
        console.print("[yellow]Order history not yet implemented.[/yellow]")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    cli()
