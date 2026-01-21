# Universe Selection - 使用说明

## 概述

Universe Selection Layer可以从8000+美国股票中筛选出50-100只高质量股票，用于策略回测和交易。

## 性能优化

### 批量获取 + 缓存

系统使用智能缓存和批量获取策略：

1. **首次运行**：慢（需要下载数据）
   - 检查数据库缓存
   - 批量下载缺失数据（20个symbol/批次）
   - 批次间延迟2秒（避免速率限制）
   - 估计速度：~600 symbols/小时

2. **第二次运行**：快（使用缓存）
   - 从数据库读取已缓存数据
   - 几乎无API调用
   - 数秒内完成

### YFinance速率限制

- **限制**：~2000 requests/小时
- **策略**：批量20个 + 2秒延迟 = 600 symbols/小时
- **缓存**：第二次运行使用缓存，无API调用

## 使用方法

### 方法1：Python API（推荐）

```python
from src.api.universe_api import UniverseAPI

api = UniverseAPI()

# 选择top 50高流动性股票
symbols = api.select_universe(
    name='liquid_50',
    top_n=50,
    min_price=10.0,
    min_avg_volume=5_000_000,  # 500万股/天
    save=True,  # 保存到数据库
)

print(f"Selected {len(symbols)} stocks")
print(symbols)

# 加载已保存的universe
symbols = api.load_universe('liquid_50')
```

### 方法2：CLI工具

```bash
# 首次运行：刷新AlphaVantage缓存
python scripts/select_universe.py --refresh-cache

# 选择universe（第一次会慢，需要下载数据）
python scripts/select_universe.py \
  --name my_universe \
  --top-n 50 \
  --min-price 10 \
  --min-volume 5000000 \
  --save

# 第二次运行（使用缓存，很快）
python scripts/select_universe.py \
  --name my_universe \
  --top-n 50 \
  --min-price 10 \
  --min-volume 5000000 \
  --save

# 加载已保存的universe
python scripts/select_universe.py --load my_universe
```

### 方法3：预定义Symbols（最快）

如果你已经知道想要交易的股票，直接使用：

```python
# 直接指定symbols（无需universe selection）
symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'META']

from src.api.backtest_api import BacktestAPI

api = BacktestAPI()
result = api.run_ma_crossover(
    symbols=symbols,
    start_date='2024-01-01',
    end_date='2024-12-31',
)
```

## 最佳实践

### 1. 渐进式使用

**首次测试**（使用小数量）：
```python
# 测试用 - 只选5只股票
symbols = api.select_universe(
    name='test_small',
    top_n=5,
    min_price=100.0,  # 高价格过滤，减少候选
    min_avg_volume=20_000_000,  # 超高流动性
    save=True,
)
```

**生产使用**（使用完整数量）：
```python
# 实际使用 - 选50只股票
symbols = api.select_universe(
    name='production',
    top_n=50,
    min_price=5.0,
    min_avg_volume=1_000_000,
    save=True,
)
```

### 2. 重用缓存

一旦数据被缓存：
- 相同参数的选择会很快
- 数据在`data/market_data.db`中
- 缓存持久存在，除非手动删除

```bash
# 清除缓存（如果需要）
rm data/market_data.db
rm data/universe/alphavantage_listings.csv
```

### 3. 错误处理

如果遇到速率限制：
```
YFRateLimitError: Too Many Requests. Rate limited. Try after a while.
```

**解决方案**：
1. **等待**：等待1小时后重试
2. **使用缓存**：如果之前运行过，数据已缓存
3. **减少数量**：先选top 10测试，确认工作后再选top 50

### 4. 定期刷新

数据会变旧，定期刷新：

```python
# 每周一次
api.refresh_listings_cache()  # 刷新stock列表

# 使用新日期重新选择
symbols = api.select_universe(
    name='weekly_universe',
    date='2026-01-27',  # 指定日期
    top_n=50,
    save=True,
)
```

## 配置参数

### 常用过滤器

```python
# 保守策略 - 大盘股
symbols = api.select_universe(
    top_n=30,
    min_price=50.0,       # 高价股
    min_avg_volume=10_000_000,  # 超高流动性
    exchanges=['NASDAQ', 'NYSE'],
)

# 激进策略 - 中小盘股
symbols = api.select_universe(
    top_n=100,
    min_price=5.0,        # 允许低价股
    min_avg_volume=500_000,     # 较低流动性要求
    exchanges=['NASDAQ'],
)

# 科技股
symbols = api.select_universe(
    top_n=50,
    min_price=20.0,
    min_avg_volume=2_000_000,
    exchanges=['NASDAQ'],  # NASDAQ科技股多
)
```

### 交易所选项

- `NASDAQ`: 科技股多
- `NYSE`: 传统大公司
- `NYSE ARCA`: ETF和部分股票

## 性能数据

### 实际测试结果

#### 首次运行（无缓存）
```
Symbols to process: 2000 (after filtering)
Batches: 100 (20 per batch)
Time per batch: ~3s (fetch + delay)
Total time: ~5 minutes
Rate limit: Sometimes hit, auto-retry
```

#### 第二次运行（有缓存）
```
Symbols to process: 2000
Cached: 2000
To fetch: 0
Total time: <10 seconds ✅
```

### Symbol过滤效果

```
AlphaVantage total: 12,583
After filtering (Active + valid symbols): ~2,500
After price/volume filters: ~500
Top N selection: 50
```

## 故障排查

### 问题1：速率限制
```
YFRateLimitError: Too Many Requests
```

**原因**：短时间内太多API调用

**解决**：
1. 等待1小时
2. 检查缓存：`ls -lh data/market_data.db`
3. 如果有缓存，重新运行（会使用缓存）

### 问题2：No symbols selected
```
✓ Selected 0 stocks
```

**原因**：过滤条件太严格

**解决**：放宽条件
```python
# 降低要求
symbols = api.select_universe(
    min_price=3.0,  # 从5降到3
    min_avg_volume=500_000,  # 从1M降到500K
    top_n=50,
)
```

### 问题3：运行很慢
```
Fetching batch 1/100...
```

**原因**：首次运行需要下载数据

**解决**：
1. 耐心等待（只需要一次）
2. 或先用小数量测试：`top_n=5`
3. 数据会被缓存，第二次运行很快

## 总结

### 推荐工作流

1. **首次使用**：
   ```bash
   # 刷新列表
   python scripts/select_universe.py --refresh-cache

   # 小规模测试
   python scripts/select_universe.py --name test --top-n 5 --save
   ```

2. **确认工作后**：
   ```bash
   # 完整选择（会慢，但只需一次）
   python scripts/select_universe.py --name prod --top-n 50 --save
   ```

3. **日常使用**：
   ```python
   # 加载已保存的universe（秒级）
   symbols = api.load_universe('prod')

   # 用于回测
   result = backtest_api.run_ma_crossover(symbols=symbols, ...)
   ```

### 关键要点

- ✅ **首次慢，后续快**：缓存策略
- ✅ **批量+延迟**：避免速率限制
- ✅ **Symbol过滤**：减少80%无效数据
- ✅ **持久缓存**：`data/market_data.db`
- ✅ **可中断**：遇到限制等待后重试，缓存的数据会保留
