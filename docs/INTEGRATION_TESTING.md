# Phase 2 Integration Testing Guide

## Overview

Integration tests verify that all Phase 2 modules work together correctly:
- **Module 1**: Alpaca API Integration
- **Module 2**: Scheduler & Workflows
- **Module 3**: Dynamic Risk Management
- **Module 4**: Monitoring & CLI Tools

## Prerequisites

### 1. Environment Setup

Ensure your `.env` file is configured:
```bash
ALPACA_API_KEY=your_key_here
ALPACA_SECRET_KEY=your_secret_here
ALPACA_BASE_URL=https://paper-api.alpaca.markets
ALPACA_DATA_URL=https://data.alpaca.markets
```

### 2. Dependencies

Install all required packages:
```bash
pip install -r requirements.txt
```

### 3. Verify Alpaca Connection

```bash
python scripts/verify_alpaca.py
```

Expected output:
- ✅ Trading API connection successful
- ✅ Account status: ACTIVE

## Running Integration Tests

### Option 1: Quick Test (Recommended)

```bash
bash scripts/quick_integration_test.sh
```

This runs all integration tests in sequence and provides a clear pass/fail report.

### Option 2: Python Test Runner

```bash
python scripts/run_integration_tests.py
```

**Options**:
- `--verbose, -v`: Detailed output
- `--module <name>`: Test specific module only

**Examples**:
```bash
# Test all modules
python scripts/run_integration_tests.py

# Test Alpaca integration only
python scripts/run_integration_tests.py --module alpaca

# Test end-to-end workflow
python scripts/run_integration_tests.py --module e2e

# Verbose output
python scripts/run_integration_tests.py --verbose
```

### Option 3: Direct pytest

```bash
# All integration tests
pytest tests/integration/test_phase2_integration.py -v -m integration

# Specific module
pytest tests/integration/test_phase2_integration.py::TestModule1_AlpacaIntegration -v

# With coverage
pytest tests/integration/ --cov=src --cov-report=html
```

## Test Modules

### Module 1: Alpaca Integration

**What it tests**:
- AlpacaProvider can connect to API
- Historical data fetching works
- AlpacaExecutor can query account info
- Position retrieval works

**Key tests**:
- `test_alpaca_provider_connection`
- `test_alpaca_provider_historical_data`
- `test_alpaca_executor_account_info`

### Module 2: Scheduler & Workflows

**What it tests**:
- TradingScheduler initialization
- DailyWorkflow setup with real components
- Task scheduling functionality

**Key tests**:
- `test_scheduler_initialization`
- `test_daily_workflow_initialization`

### Module 3: Dynamic Risk Management

**What it tests**:
- Position monitoring for stop-loss
- Take-profit triggering
- Circuit breaker activation
- Risk threshold validation

**Key tests**:
- `test_risk_manager_position_monitoring`
- `test_risk_manager_circuit_breaker`

### Module 4: Monitoring & CLI Tools

**What it tests**:
- PerformanceTracker initialization
- Portfolio value tracking
- Metrics calculation

**Key tests**:
- `test_performance_tracker_initialization`
- `test_performance_tracker_update`

### Interface Compatibility Tests

**What it tests**:
- AlpacaProvider implements DataProvider interface
- AlpacaExecutor implements OrderExecutor interface
- DynamicRiskManager implements RiskManager interface

### End-to-End Integration

**What it tests**:
- Complete workflow: data → execution
- Risk manager with live account data
- Full daily workflow (dry run, no real trades)

**Key tests**:
- `test_data_to_execution_flow`
- `test_complete_workflow_dry_run`

## Expected Results

### All Tests Pass ✅

```
================================
🎉 ALL INTEGRATION TESTS PASSED
================================

Phase 2 is ready for paper trading validation!
```

**Next steps**:
1. Review test output for any warnings
2. Proceed to paper trading validation (starting 2026-02-01)

### Some Tests Fail ❌

**Common issues**:

1. **Connection errors**:
   - Check internet connection
   - Verify API credentials in `.env`
   - Check Alpaca API status: https://status.alpaca.markets

2. **Import errors**:
   - Run `pip install -r requirements.txt`
   - Verify all modules exist in correct locations

3. **Data fetching fails**:
   - Alpaca free tier has rate limits
   - Some symbols may be unavailable
   - Try different date ranges

4. **Account status issues**:
   - Ensure Paper Trading account is active
   - Check if account is blocked (shouldn't be for paper)

## Debugging Failed Tests

### View detailed output

```bash
pytest tests/integration/test_phase2_integration.py -v --tb=long
```

### Run single test

```bash
pytest tests/integration/test_phase2_integration.py::TestModule1_AlpacaIntegration::test_alpaca_provider_connection -v
```

### Check logs

```bash
# Trading logs (once paper trading starts)
tail -f logs/trading.log

# Pytest output
pytest tests/integration/ -v --log-cli-level=DEBUG
```

## Test Markers

Tests use pytest markers to categorize:

- `@pytest.mark.integration`: Requires live API connection
- No marker: Unit test, works offline

**Run only integration tests**:
```bash
pytest -m integration
```

**Skip integration tests**:
```bash
pytest -m "not integration"
```

## Continuous Integration

Integration tests should run:
- **Before paper trading**: Verify all modules work together
- **After code changes**: Ensure nothing broke
- **Before production**: Final validation

## Test Coverage

Check code coverage:
```bash
pytest tests/integration/ --cov=src --cov-report=html
open htmlcov/index.html
```

Target: >80% coverage for Phase 2 modules

## Next Steps After Integration Tests

1. ✅ All integration tests pass
2. 📋 Update PHASE2_PLAN.md with test results
3. 🚀 Start paper trading validation (2026-02-01)
4. 📊 Monitor performance for 2 weeks
5. 🎯 Validate risk management in real-time
6. ✅ Phase 2 complete!

## Support

If tests fail consistently:
1. Check [PHASE2_PLAN.md](PHASE2_PLAN.md) for known issues
2. Review module implementation in `src/`
3. Verify Alpaca account status
4. Check API rate limits

## Test Maintenance

Update tests when:
- Adding new features to Phase 2
- Changing module interfaces
- Updating risk thresholds
- Modifying workflows

**Test file location**: `tests/integration/test_phase2_integration.py`
