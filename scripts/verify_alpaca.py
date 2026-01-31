#!/usr/bin/env python3
"""
Verify Alpaca Paper Trading API Connection

This script tests the connection to Alpaca Paper Trading API
and displays account information.

Usage:
    python scripts/verify_alpaca.py
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.data.historical import StockHistoricalDataClient
from rich.console import Console
from rich.table import Table

# Load environment variables
load_dotenv()

console = Console()


def verify_credentials():
    """Verify that all required credentials are present."""
    required_vars = [
        "ALPACA_API_KEY",
        "ALPACA_SECRET_KEY",
        "ALPACA_BASE_URL",
        "ALPACA_DATA_URL",
    ]

    missing = [var for var in required_vars if not os.getenv(var)]

    if missing:
        console.print(
            f"[red]❌ Missing environment variables: {', '.join(missing)}[/red]"
        )
        console.print("\n[yellow]Please check your .env file[/yellow]")
        return False

    console.print("[green]✅ All credentials found in .env[/green]")
    return True


def test_trading_api():
    """Test connection to Alpaca Trading API."""
    console.print("\n[bold]Testing Trading API Connection...[/bold]")

    try:
        client = TradingClient(
            api_key=os.getenv("ALPACA_API_KEY"),
            secret_key=os.getenv("ALPACA_SECRET_KEY"),
            paper=True,  # Use paper trading
        )

        # Get account information
        account = client.get_account()

        # Create table
        table = Table(title="Alpaca Account Information")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Account Status", account.status)
        table.add_row("Account Number", account.account_number)
        table.add_row("Cash", f"${float(account.cash):,.2f}")
        table.add_row("Buying Power", f"${float(account.buying_power):,.2f}")
        table.add_row("Portfolio Value", f"${float(account.portfolio_value):,.2f}")
        table.add_row("Pattern Day Trader", str(account.pattern_day_trader))
        table.add_row("Trading Blocked", str(account.trading_blocked))
        table.add_row("Account Blocked", str(account.account_blocked))

        console.print(table)
        console.print("[green]✅ Trading API connection successful![/green]")

        # Test positions
        positions = client.get_all_positions()
        console.print(f"\n[cyan]Current Positions: {len(positions)}[/cyan]")

        if positions:
            pos_table = Table(title="Current Positions")
            pos_table.add_column("Symbol", style="cyan")
            pos_table.add_column("Qty", style="yellow")
            pos_table.add_column("Market Value", style="green")
            pos_table.add_column("P&L", style="magenta")

            for pos in positions:
                pnl_color = "green" if float(pos.unrealized_pl) >= 0 else "red"
                pos_table.add_row(
                    pos.symbol,
                    str(pos.qty),
                    f"${float(pos.market_value):,.2f}",
                    f"[{pnl_color}]${float(pos.unrealized_pl):,.2f}[/{pnl_color}]",
                )

            console.print(pos_table)

        return True

    except Exception as e:
        console.print(f"[red]❌ Trading API connection failed: {e}[/red]")
        return False


def test_data_api():
    """Test connection to Alpaca Data API."""
    console.print("\n[bold]Testing Data API Connection...[/bold]")

    try:
        client = StockHistoricalDataClient(
            api_key=os.getenv("ALPACA_API_KEY"),
            secret_key=os.getenv("ALPACA_SECRET_KEY"),
        )

        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame
        from datetime import datetime, timedelta

        # Request 5 days of AAPL data
        end = datetime.now()
        start = end - timedelta(days=5)

        request = StockBarsRequest(
            symbol_or_symbols="AAPL",
            timeframe=TimeFrame.Day,
            start=start,
            end=end,
        )

        bars = client.get_stock_bars(request)

        if bars.data and "AAPL" in bars.data:
            aapl_bars = bars.data["AAPL"]
            console.print(
                f"[green]✅ Data API connection successful! "
                f"Retrieved {len(aapl_bars)} bars for AAPL[/green]"
            )

            # Show latest bar
            latest = aapl_bars[-1]
            console.print(
                f"\n[cyan]Latest AAPL Bar:[/cyan] "
                f"Close: ${latest.close:.2f}, "
                f"Volume: {latest.volume:,}"
            )
            return True
        else:
            console.print("[yellow]⚠️  Data API connected but no data returned[/yellow]")
            return False

    except Exception as e:
        error_msg = str(e)
        if "subscription does not permit" in error_msg:
            console.print(
                "[yellow]⚠️  Data API: Free tier detected. "
                "SIP data not available.[/yellow]"
            )
            console.print(
                "[cyan]ℹ️  This is OK! We'll use yfinance for historical data "
                "and Alpaca Trading API for quotes.[/cyan]"
            )
            return True  # Not a critical failure
        else:
            console.print(f"[red]❌ Data API connection failed: {e}[/red]")
            return False


def main():
    """Main verification function."""
    console.print("[bold blue]Alpaca API Verification Tool[/bold blue]")
    console.print("[dim]Phase 2: Paper Trading Setup[/dim]\n")

    # Step 1: Verify credentials
    if not verify_credentials():
        return 1

    # Step 2: Test Trading API
    trading_success = test_trading_api()

    # Step 3: Test Data API
    data_success = test_data_api()

    # Summary
    console.print("\n[bold]Summary:[/bold]")
    if trading_success and data_success:
        console.print("[green]✅ All API connections verified successfully![/green]")
        console.print(
            "\n[bold green]You're ready to start Phase 2 development! 🚀[/bold green]"
        )
        return 0
    else:
        console.print(
            "[yellow]⚠️  Some API connections failed. "
            "Please check your credentials and try again.[/yellow]"
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
