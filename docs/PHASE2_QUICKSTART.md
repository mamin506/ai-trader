# Phase 2: Quick Start Guide

**For Multi-Agent Collaboration**

---

## 🚀 Getting Started

### 1. Install Dependencies

```bash
# Activate virtual environment (should already be active in DevContainer)
source /home/ubuntu/.venv/bin/activate

# Install Phase 2 dependencies
pip install -r requirements.txt
```

### 2. Verify Configuration

Check that your `.env` file is set up correctly:

```bash
# Should output your Alpaca API key (first few characters)
grep ALPACA_API_KEY .env | cut -c1-25
```

### 3. Verify Alpaca Connection

```bash
# Test Alpaca API connection (create this test script later)
python -c "
import os
from dotenv import load_dotenv
load_dotenv()

api_key = os.getenv('ALPACA_API_KEY')
base_url = os.getenv('ALPACA_BASE_URL')

print(f'API Key: {api_key[:8]}...')
print(f'Base URL: {base_url}')
print('✅ Configuration loaded successfully!')
"
```

---

## 👥 For Agent A (Integration Specialist)

### Your Responsibilities
- Module 1: Alpaca API Integration
- Module 2: APScheduler & Workflows

### Start Here

**Week 1: Alpaca Integration**

1. **Read the plan**:
   ```bash
   # Review your tasks in detail
   cat docs/PHASE2_PLAN.md | grep -A 50 "Module 1: Alpaca API Integration"
   ```

2. **Create your branch**:
   ```bash
   git checkout -b phase2/dev  # Create integration branch from main
   git push -u origin phase2/dev

   git checkout -b phase2/agent-a/alpaca-integration
   ```

3. **Study the interface contracts**:
   - Read `docs/PHASE2_PLAN.md` section: "Interface Contracts"
   - Study existing `src/data/base.py` (DataProvider interface)
   - Study existing `src/execution/base.py` (OrderExecutor interface)

4. **Install and explore Alpaca SDK**:
   ```bash
   # Read Alpaca SDK documentation
   python -c "import alpaca; help(alpaca)"
   ```

5. **Start implementing**:
   - Create `src/data/providers/alpaca_provider.py`
   - Create `src/execution/alpaca_executor.py`
   - Create `src/utils/alpaca_client.py`
   - Write tests as you go!

6. **Testing**:
   ```bash
   # Run your tests
   pytest tests/data/providers/test_alpaca_provider.py -v
   pytest tests/execution/test_alpaca_executor.py -v
   ```

7. **Commit frequently**:
   ```bash
   git add .
   git commit -m "feat(alpaca): implement AlpacaProvider get_daily_bars"
   git push origin phase2/agent-a/alpaca-integration
   ```

---

## 👥 For Agent B (Core Logic Specialist)

### Your Responsibilities
- Module 0: Configuration Setup (✅ partially done)
- Module 3: Dynamic Risk Management
- Module 4: Monitoring & CLI Tools

### Start Here

**Week 1: Configuration Setup**

1. **Read the plan**:
   ```bash
   # Review your tasks in detail
   cat docs/PHASE2_PLAN.md | grep -A 30 "Module 0: Configuration"
   ```

2. **Create your branch**:
   ```bash
   git checkout phase2/dev
   git checkout -b phase2/agent-b/config-setup
   ```

3. **Complete configuration tasks**:
   - [x] `.env` file (already created ✅)
   - [x] `config/alpaca.yaml` (already created ✅)
   - [x] `.env.example` (already created ✅)
   - [x] `requirements.txt` updated (already done ✅)
   - [ ] Update `src/utils/config.py` to load Alpaca config
   - [ ] Create config validation tests

4. **Update configuration loader**:
   ```bash
   # Edit src/utils/config.py to add Alpaca config loading
   # Add python-dotenv support for .env file
   ```

5. **Test configuration**:
   ```bash
   # Create a test script to validate config loading
   python -c "
   from src.utils.config import load_config
   config = load_config('config/alpaca.yaml')
   print(config.alpaca.mode)  # Should print 'paper'
   "
   ```

6. **Commit and merge**:
   ```bash
   git add .
   git commit -m "feat(config): add Alpaca configuration support"
   git push origin phase2/agent-b/config-setup

   # Merge to phase2/dev
   git checkout phase2/dev
   git merge phase2/agent-b/config-setup
   git push origin phase2/dev
   ```

**Week 2-3: Dynamic Risk Management**

1. **Create new branch**:
   ```bash
   git checkout phase2/dev
   git pull origin phase2/dev  # Get latest changes
   git checkout -b phase2/agent-b/dynamic-risk
   ```

2. **Study existing risk management**:
   ```bash
   # Review Phase 1 risk management
   cat src/risk/base.py
   cat src/risk/basic_risk_manager.py
   ```

3. **Implement dynamic risk manager**:
   - Create `src/risk/dynamic_risk_manager.py`
   - Create `src/risk/monitors.py`
   - Write comprehensive tests

4. **Test with historical data**:
   ```bash
   # Create a replay test that simulates position monitoring
   pytest tests/risk/test_dynamic_risk_manager.py -v
   ```

---

## 🔄 Coordination Between Agents

### Daily Sync (Recommended)

**Each agent should**:
1. Pull latest changes from `phase2/dev`:
   ```bash
   git checkout phase2/dev
   git pull origin phase2/dev
   ```

2. Update progress in `docs/PHASE2_PLAN.md`:
   ```bash
   # Edit the "Progress Tracking" section
   # Mark tasks as complete, note any blockers
   ```

3. Push updates:
   ```bash
   git add docs/PHASE2_PLAN.md
   git commit -m "docs(phase2): update progress for [date]"
   git push origin phase2/dev
   ```

### Handling Dependencies

**Agent B depends on Agent A for**:
- AlpacaProvider interface (for real-time price data)
- AlpacaExecutor interface (for position queries)

**Workaround while waiting**:
- Use mock implementations for testing
- Define interface contracts clearly (see PHASE2_PLAN.md)
- Test with Phase 1 components (YFinanceProvider, BacktestExecutor)

**Agent A depends on Agent B for**:
- Configuration loading (alpaca.yaml)
- Risk management integration

**Workaround while waiting**:
- Hard-code config values temporarily
- Use Phase 1 BasicRiskManager for testing

---

## 📊 Progress Tracking

### Check Module Status

```bash
# View current progress
cat docs/PHASE2_PLAN.md | grep -A 10 "Module Status"
```

### Update Your Progress

```bash
# Edit PHASE2_PLAN.md
# Find your module and update:
# - Status: ⚪ Not Started → 🟡 In Progress → ✅ Complete
# - Progress: 0% → 50% → 100%
# - Completed: Add completion date
```

---

## 🧪 Testing Strategy

### Unit Tests
```bash
# Run all tests
pytest

# Run tests for specific module
pytest tests/data/providers/test_alpaca_provider.py -v
pytest tests/risk/test_dynamic_risk_manager.py -v

# Check coverage
pytest --cov=src --cov-report=html
open htmlcov/index.html  # View coverage report
```

### Integration Tests
```bash
# Run integration tests (requires Alpaca API connection)
pytest tests/integration/test_alpaca_integration.py -v --integration
```

### Manual Testing
```bash
# Test AlpacaProvider
python -c "
from src.data.providers.alpaca_provider import AlpacaProvider
provider = AlpacaProvider()
bars = provider.get_daily_bars('AAPL', '2024-01-01', '2024-01-31')
print(bars.head())
"

# Test AlpacaExecutor
python -c "
from src.execution.alpaca_executor import AlpacaExecutor
executor = AlpacaExecutor()
positions = executor.get_positions()
print(positions)
"
```

---

## 🔍 Debugging Tips

### Check Alpaca API Connection
```python
from alpaca.trading.client import TradingClient
from dotenv import load_dotenv
import os

load_dotenv()

client = TradingClient(
    api_key=os.getenv('ALPACA_API_KEY'),
    secret_key=os.getenv('ALPACA_SECRET_KEY'),
    paper=True
)

# Test connection
account = client.get_account()
print(f"Account Status: {account.status}")
print(f"Buying Power: ${account.buying_power}")
```

### Check Configuration Loading
```python
from src.utils.config import load_config

config = load_config('config/alpaca.yaml')
print(f"Mode: {config.alpaca.mode}")
print(f"Rebalance Time: {config.alpaca.schedule.rebalance_time}")
```

### View Logs
```bash
# Tail trading logs (once logging is set up)
tail -f logs/trading.log

# Search for errors
grep ERROR logs/trading.log

# Search for specific symbol
grep AAPL logs/trading.log
```

---

## 📚 Useful Resources

### Alpaca API Documentation
- [Getting Started](https://alpaca.markets/docs/trading/)
- [Paper Trading](https://alpaca.markets/docs/trading/paper-trading/)
- [Python SDK](https://github.com/alpacahq/alpaca-py)
- [API Reference](https://alpaca.markets/docs/api-references/trading-api/)

### APScheduler Documentation
- [User Guide](https://apscheduler.readthedocs.io/en/3.x/userguide.html)
- [Cron Triggers](https://apscheduler.readthedocs.io/en/3.x/modules/triggers/cron.html)

### Project Documentation
- [PHASE2_PLAN.md](PHASE2_PLAN.md) - Detailed implementation plan
- [architecture-overview.md](../agent/architecture-overview.md) - System architecture
- [development-guidelines.md](../agent/development-guidelines.md) - Coding standards

---

## ⚠️ Common Pitfalls

1. **Don't hardcode credentials**:
   - ❌ `api_key = "PKMP63B5..."`
   - ✅ `api_key = os.getenv('ALPACA_API_KEY')`

2. **Always test with Paper Trading**:
   - ❌ `paper=False` (NEVER do this in Phase 2!)
   - ✅ `paper=True`

3. **Handle API rate limits**:
   - Implement retry logic
   - Use exponential backoff
   - Respect Alpaca's rate limits (200 req/min)

4. **Don't forget timezones**:
   - Market hours are in US/Eastern timezone
   - Convert to UTC when needed
   - Use `exchange_calendars` for trading days

5. **Test error cases**:
   - API connection failures
   - Invalid symbols
   - Insufficient buying power
   - Market closed scenarios

---

## 🎯 Success Checklist

Before marking a module complete:
- [ ] All code implemented according to interface contracts
- [ ] Unit tests written and passing (>80% coverage)
- [ ] Integration tests passing (if applicable)
- [ ] Documentation updated (docstrings, README)
- [ ] No hardcoded credentials or config values
- [ ] Error handling implemented
- [ ] Code reviewed by other agent (optional but recommended)
- [ ] Merged to `phase2/dev` branch

---

## 🆘 Getting Help

If you encounter issues or blockers:

1. **Update PHASE2_PLAN.md**:
   - Add to "Progress Tracking" → "Blockers" section
   - Describe the issue clearly

2. **Review existing code**:
   - Check Phase 1 implementations for reference
   - Read similar modules for patterns

3. **Check documentation**:
   - Read Alpaca API docs
   - Review Python SDK examples

4. **Ask for clarification**:
   - Document questions in PHASE2_PLAN.md
   - Wait for user feedback

---

**Happy Coding! 🚀**

Remember: Communication and coordination are key to successful multi-agent collaboration.
Update PHASE2_PLAN.md frequently and pull changes from phase2/dev regularly!
