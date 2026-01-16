# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI Trader is a traditional algorithmic trading bot focused on the U.S. Stock market. This is a personal trading project that emphasizes systematic trading strategies rather than AI-powered decision making.

## Development Environment

This project uses VS Code DevContainers for consistent cross-platform development.

**Container specifications:**
- Base: Ubuntu 24.04
- Python: 3.12 (system default)
- Virtual environment: `/home/ubuntu/.venv` (automatically activated)
- User: ubuntu (non-root with passwordless sudo)

**Key environment settings:**
- Code formatting: Black (format on save enabled)
- Editor rulers: 88, 120 characters
- Python interpreter: `/home/ubuntu/.venv/bin/python`
- `PYTHONUNBUFFERED=1` set by default

## Development Setup

The DevContainer automatically:
1. Creates and activates a Python virtual environment at `/home/ubuntu/.venv`
2. Upgrades pip on container creation
3. Configures Python development tools (Pylance, Black, Pylint, debugpy)

When adding dependencies, use:
```bash
pip install <package>
# Or for development
python -m pip install <package>
```

## Code Style

- Primary line length: 88 characters (Black default)
- Maximum line length: 120 characters
- Format on save is enabled
- Trailing whitespace is trimmed automatically
- Final newline is inserted automatically

## Project Structure

This is an early-stage project. The codebase architecture will be documented here as the project develops. Expected future components:
- Trading strategy implementations
- Market data ingestion
- Order execution system
- Backtesting framework
- Risk management

## Git Workflow

- Main branch: `main`
- Repository includes standard Python .gitignore covering common patterns
