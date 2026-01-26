# Seed List Management

## Overview

The seed list (`data/seed_list.json`) contains pre-selected stocks that serve as the starting point for universe selection. This list should be updated **biweekly** (every 2 weeks) to ensure it includes actively traded, liquid stocks.

## Seed List Structure

```json
{
  "metadata": {
    "last_updated": "2026-01-26",
    "description": "High-liquidity US stocks for universe selection",
    "screener": "finviz",
    "filters": "cap_mega (>$200B) + cap_large ($10B-$200B), volume > 2M",
    "total_count": 150,
    "update_frequency": "biweekly"
  },
  "seeds": [
    "AAPL", "MSFT", "GOOGL", ...
  ]
}
```

## Update Schedule

**Frequency:** Every 2 weeks (biweekly)

**Recommended days:**
- 1st and 3rd Monday of each month
- Or any consistent schedule that works for you

## Updating the Seed List

### Command

```bash
python scripts/update_seed_list.py
```

### What It Does

1. **Screens stocks using Finviz:**
   - Mega cap stocks ($200B+)
   - Large cap stocks ($10B-$200B)
   - Filters for volume > 2M shares

2. **Compares with current list:**
   - Shows added symbols
   - Shows removed symbols
   - Shows statistics

3. **Asks for confirmation:**
   - You must type "yes" to proceed

4. **Saves updated list:**
   - Updates `data/seed_list.json`
   - Preserves metadata about the update

### Example Output

```
================================================================================
🔄 SEED LIST UPDATE SCRIPT
================================================================================
Date: 2026-01-26 09:30:00
================================================================================

================================================================================
SCREENING STOCKS WITH FINVIZ
================================================================================

[1/2] Fetching mega cap stocks ($200B+)...
✅ Found 63 mega cap stocks
   After volume filter (>2M): 58 stocks

⏳ Waiting 5 seconds to avoid rate limiting...

[2/2] Fetching large cap stocks ($10B-$200B)...
✅ Found 80 large cap stocks
   After volume filter (>2M): 72 stocks

--------------------------------------------------------------------------------
📊 Total unique symbols: 130
--------------------------------------------------------------------------------

================================================================================
COMPARING WITH CURRENT SEED LIST
================================================================================

📈 Added:     25 symbols
   ABNB, COIN, CRWD, DASH, NET, PANW, PLTR, RBLX, SHOP, SNOW, ZS, ...

📉 Removed:   4 symbols
   PARA, PXD, SQ, U

✅ Unchanged: 105 symbols

================================================================================
UPDATE CONFIRMATION
================================================================================
Current seed list: 109 symbols
New seed list:     130 symbols
Net change:        +21 symbols

❓ Update seed list? (yes/no): yes

💾 Saving updated seed list...
✅ Seed list updated successfully!
   Location: data/seed_list.json
   Total symbols: 130

================================================================================
✅ UPDATE COMPLETE
================================================================================
```

## Manual Editing (Not Recommended)

You can manually edit `data/seed_list.json` if needed, but make sure to:

1. Keep the JSON format valid
2. Update the `last_updated` field
3. Update the `total_count` field
4. Sort symbols alphabetically (optional but recommended)

**Example:**

```json
{
  "metadata": {
    "last_updated": "2026-01-26",
    "total_count": 3
  },
  "seeds": [
    "AAPL",
    "GOOGL",
    "MSFT"
  ]
}
```

## Screening Criteria

The update script uses the following Finviz filters:

| Filter | Description |
|--------|-------------|
| `cap_mega` | Market cap > $200B |
| `cap_large` | Market cap $10B - $200B |
| Volume > 2M | Average daily volume > 2M shares |

This ensures we get:
- ✅ Large, established companies
- ✅ High liquidity (easy to trade)
- ✅ Active stocks (volume filter)

## Why Update Biweekly?

- **Market changes:** Companies get acquired, go private, or delist
- **Liquidity shifts:** Some stocks become more/less actively traded
- **New IPOs:** Large companies go public
- **Market cap changes:** Companies cross the $10B threshold

## Troubleshooting

### Error: "No module named 'finviz'"

```bash
pip install finviz
```

### Error: "429 Too Many Requests"

Finviz rate limited you. Wait 5-10 minutes and try again.

### Seed list file not found

The update script will create a new one automatically.

### Want to keep removed stocks?

Manually add them back to `data/seed_list.json` after the update, but consider why they were removed (possibly delisted or low liquidity).

## Advanced: Custom Screening

If you want to customize the screening criteria, edit `scripts/update_seed_list.py`:

```python
# Example: Add mid-cap stocks too
screener_mid = Screener(
    filters=["cap_mid"],  # $2B-$10B
    table="Overview",
    order="-marketcap",
)
```

Available Finviz filters:
- `cap_mega`: > $200B
- `cap_large`: $10B - $200B
- `cap_mid`: $2B - $10B
- `cap_small`: $300M - $2B
- `sh_avgvol_o2000`: Avg volume > 2M
- `sh_avgvol_o5000`: Avg volume > 5M
- `sec_technology`: Technology sector
- ... and many more

See [Finviz screener](https://finviz.com/screener.ashx) for all available filters.

## Next Steps After Update

After updating the seed list, you may want to:

1. **Test universe selection:**
   ```python
   from src.api.universe_api import UniverseAPI

   api = UniverseAPI()
   symbols = api.select_universe(top_n=20)
   print(symbols)
   ```

2. **Run backtests** with the updated universe

3. **Review removed symbols** to understand market changes
