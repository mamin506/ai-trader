#!/usr/bin/env python3
"""
Run Phase 2 Integration Tests

This script runs all Phase 2 integration tests and generates a comprehensive report.

Usage:
    python scripts/run_integration_tests.py
    python scripts/run_integration_tests.py --verbose
    python scripts/run_integration_tests.py --module scheduler  # Test specific module
"""

import sys
import os
from pathlib import Path
import subprocess
import argparse
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

console = Console()


def run_pytest(test_path: str, verbose: bool = False) -> dict:
    """Run pytest and capture results."""
    args = ["pytest", test_path, "-v", "--tb=short", "--color=yes"]

    if verbose:
        args.append("-vv")

    # Add markers for integration tests
    args.extend(["-m", "integration or not integration"])

    # Generate JSON report
    report_file = "/tmp/pytest_report.json"
    args.extend(["--json-report", f"--json-report-file={report_file}"])

    console.print(f"\n[cyan]Running: {' '.join(args)}[/cyan]\n")

    result = subprocess.run(args, capture_output=True, text=True)

    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def display_test_summary(result: dict):
    """Display test summary with Rich formatting."""
    console.print("\n" + "=" * 80 + "\n")

    # Parse output for test results
    output = result["stdout"]

    if result["returncode"] == 0:
        console.print(Panel("[green]✅ ALL TESTS PASSED[/green]", box=box.DOUBLE))
    else:
        console.print(Panel("[red]❌ SOME TESTS FAILED[/red]", box=box.DOUBLE))

    # Display output
    console.print("\n[bold]Test Output:[/bold]")
    console.print(output)

    if result["stderr"]:
        console.print("\n[bold yellow]Warnings/Errors:[/bold yellow]")
        console.print(result["stderr"])


def test_module(module_name: str, verbose: bool = False) -> bool:
    """Test a specific module."""
    test_map = {
        "alpaca": "tests/integration/test_phase2_integration.py::TestModule1_AlpacaIntegration",
        "scheduler": "tests/integration/test_phase2_integration.py::TestModule2_SchedulerIntegration",
        "risk": "tests/integration/test_phase2_integration.py::TestModule3_RiskManagement",
        "monitoring": "tests/integration/test_phase2_integration.py::TestModule4_Monitoring",
        "e2e": "tests/integration/test_phase2_integration.py::TestEndToEndIntegration",
        "interfaces": "tests/integration/test_phase2_integration.py::TestInterfaceCompatibility",
    }

    if module_name not in test_map:
        console.print(
            f"[red]Unknown module: {module_name}[/red]", f"Available modules: {', '.join(test_map.keys())}"
        )
        return False

    console.print(
        Panel(
            f"[cyan]Testing Module: {module_name.upper()}[/cyan]",
            box=box.ROUNDED,
        )
    )

    result = run_pytest(test_map[module_name], verbose)
    display_test_summary(result)

    return result["returncode"] == 0


def test_all_modules(verbose: bool = False) -> dict:
    """Run all integration tests."""
    console.print(
        Panel(
            "[bold cyan]Phase 2 Integration Test Suite[/bold cyan]\n"
            f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            box=box.DOUBLE,
        )
    )

    modules = [
        ("Module 1", "Alpaca Integration", "alpaca"),
        ("Module 2", "Scheduler & Workflows", "scheduler"),
        ("Module 3", "Dynamic Risk Management", "risk"),
        ("Module 4", "Monitoring & CLI Tools", "monitoring"),
        ("Interface", "Interface Compatibility", "interfaces"),
        ("E2E", "End-to-End Integration", "e2e"),
    ]

    results = {}

    for module_id, module_name, module_key in modules:
        console.print(f"\n[bold]Testing {module_id}: {module_name}[/bold]")
        console.print("-" * 80)

        success = test_module(module_key, verbose)
        results[module_key] = success

        if success:
            console.print(f"[green]✅ {module_id} PASSED[/green]\n")
        else:
            console.print(f"[red]❌ {module_id} FAILED[/red]\n")

    return results


def display_final_report(results: dict):
    """Display final test report."""
    console.print("\n" + "=" * 80 + "\n")

    # Create summary table
    table = Table(title="Integration Test Summary", box=box.ROUNDED)
    table.add_column("Module", style="cyan")
    table.add_column("Status", justify="center")

    module_names = {
        "alpaca": "Module 1: Alpaca Integration",
        "scheduler": "Module 2: Scheduler & Workflows",
        "risk": "Module 3: Dynamic Risk Management",
        "monitoring": "Module 4: Monitoring & CLI Tools",
        "interfaces": "Interface Compatibility",
        "e2e": "End-to-End Integration",
    }

    for module, success in results.items():
        status = "[green]✅ PASS[/green]" if success else "[red]❌ FAIL[/red]"
        table.add_row(module_names[module], status)

    console.print(table)

    # Overall result
    all_passed = all(results.values())
    if all_passed:
        console.print(
            Panel(
                "[bold green]🎉 ALL INTEGRATION TESTS PASSED[/bold green]\n"
                "Phase 2 modules are ready for paper trading!",
                box=box.DOUBLE,
            )
        )
    else:
        failed_modules = [k for k, v in results.items() if not v]
        console.print(
            Panel(
                f"[bold red]⚠️  INTEGRATION TESTS FAILED[/bold red]\n"
                f"Failed modules: {', '.join(failed_modules)}\n"
                "Please fix issues before proceeding to paper trading.",
                box=box.DOUBLE,
            )
        )

    return all_passed


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run Phase 2 Integration Tests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/run_integration_tests.py              # Run all tests
  python scripts/run_integration_tests.py --verbose    # Verbose output
  python scripts/run_integration_tests.py --module alpaca    # Test Alpaca module
  python scripts/run_integration_tests.py --module e2e       # Test end-to-end
        """,
    )

    parser.add_argument(
        "--module",
        "-m",
        choices=["alpaca", "scheduler", "risk", "monitoring", "interfaces", "e2e"],
        help="Test specific module only",
    )

    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Verbose output"
    )

    args = parser.parse_args()

    # Check if pytest-json-report is installed
    try:
        import pytest_jsonreport
    except ImportError:
        console.print(
            "[yellow]Warning: pytest-json-report not installed. "
            "Install with: pip install pytest-json-report[/yellow]\n"
        )

    if args.module:
        # Test specific module
        success = test_module(args.module, args.verbose)
        return 0 if success else 1
    else:
        # Test all modules
        results = test_all_modules(args.verbose)
        all_passed = display_final_report(results)
        return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
