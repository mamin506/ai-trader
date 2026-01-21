# Jupyter Notebooks

This directory contains interactive Jupyter notebooks for exploring and analyzing the AI Trader system.

## Available Notebooks

### 01_backtesting_tutorial.ipynb

Comprehensive tutorial covering the entire backtesting workflow.

**Topics Covered**:
1. **Data Layer**: Fetching and caching historical market data
2. **Strategy Layer**: Testing trading strategies with signals and indicators
3. **Portfolio Backtesting**: Multi-symbol portfolio backtests
4. **Performance Analysis**: Equity curves, returns, and risk metrics
5. **Strategy Comparison**: Comparing multiple strategy configurations

**What You'll Learn**:
- How to use `DataAPI` to fetch and cache market data
- How to test strategies with `StrategyAPI`
- How to run comprehensive backtests with `BacktestAPI`
- How to visualize signals, equity curves, and returns
- How to compare different strategy parameters

**Prerequisites**:
```bash
pip install -r requirements.txt
```

**Quick Start**:
```bash
# Launch Jupyter
jupyter notebook

# Or use JupyterLab
jupyter lab

# Navigate to notebooks/01_backtesting_tutorial.ipynb
```

## Running Notebooks in DevContainer

The project's DevContainer includes Jupyter support:

1. Open the notebook in VS Code
2. Select the Python kernel: `/home/ubuntu/.venv/bin/python`
3. Run cells interactively

## Creating New Notebooks

When creating analysis notebooks:

1. **Import path setup**:
   ```python
   import sys
   sys.path.append('..')

   from src.api.data_api import DataAPI
   from src.api.backtest_api import BacktestAPI
   ```

2. **Use relative paths** for data files and outputs

3. **Add clear documentation** with markdown cells

4. **Include visualizations** using matplotlib or plotly

5. **Show both code and results** for educational value

## Recommended Structure

```python
# 1. Setup and imports
import sys
sys.path.append('..')
import pandas as pd
import matplotlib.pyplot as plt
from src.api import *

# 2. Configuration
symbols = ['AAPL', 'MSFT', 'GOOGL']
start_date = '2024-01-01'
end_date = '2024-12-31'

# 3. Data fetching
data_api = DataAPI()
# ... fetch data ...

# 4. Analysis
# ... run strategies, backtests, etc ...

# 5. Visualization
# ... plot results ...

# 6. Conclusions
# ... summary and insights ...
```

## Tips

- **Use `%matplotlib inline`** for inline plots
- **Set figure size** appropriately: `plt.figure(figsize=(14, 6))`
- **Clear outputs** before committing to git
- **Document assumptions** and parameters clearly
- **Show intermediate results** to aid understanding

## Future Notebooks

Planned notebooks for Phase 2 and beyond:

- **02_custom_strategies.ipynb**: Building custom trading strategies
- **03_risk_analysis.ipynb**: Advanced risk metrics and analysis
- **04_parameter_optimization.ipynb**: Optimizing strategy parameters
- **05_live_trading_setup.ipynb**: Setting up paper/live trading

## Resources

- [Jupyter Documentation](https://jupyter.org/documentation)
- [Pandas Documentation](https://pandas.pydata.org/docs/)
- [Matplotlib Documentation](https://matplotlib.org/stable/contents.html)
