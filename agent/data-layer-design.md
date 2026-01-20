# Data Layer Design

## Overview

The data layer is responsible for acquiring, storing, and serving market data for the investable universe defined by the Universe Selection layer. The design emphasizes **provider abstraction** to enable seamless switching between different data sources without impacting upper layers.

## Core Design Principle

**Interface Abstraction for Replaceability**: The system should be able to swap between yfinance, Alpaca, and Interactive Brokers APIs through configuration changes, not code rewrites.

## Target Use Case

- **Primary timeframe**: Daily bars (EOD data)
- **Secondary timeframe**: Hourly/minute bars for research (future consideration)
- **Not in scope**: Tick data, high-frequency trading
- **Universe constraint**: Only fetch data for symbols in the current investable universe

This focus on daily data simplifies initial design - real-time streaming can be deferred.

## Architecture

### Abstraction Layer

```
Universe Selection → Data Layer → Strategy Layer
      ↓
DataProvider (Abstract Interface)
      ↓
┌─────────┬──────────────┬─────────────┐
│YFinance │ Alpaca       │ Interactive │
│Provider │ Provider     │ Brokers     │
│         │              │ Provider    │
└─────────┴──────────────┴─────────────┘
```

### DataProvider Interface

The abstract `DataProvider` class defines the contract that all implementations must follow:

```python
# Conceptual interface (detailed implementation TBD)

class DataProvider(ABC):
    @abstractmethod
    def get_historical_bars(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: str
    ) -> pd.DataFrame:
        """Retrieve historical OHLCV data"""
        pass

    @abstractmethod
    def get_latest_quote(self, symbol: str) -> Quote:
        """Get latest bid/ask quote"""
        pass

    @abstractmethod
    def get_latest_trade(self, symbol: str) -> Trade:
        """Get latest executed trade"""
        pass

    # Future: Real-time streaming support
    # def subscribe_bars(self, symbols: List[str], callback) -> Stream:
    #     pass
```

### Standard Output Format

All providers must return data in a consistent format:

**OHLCV DataFrame Structure**:
```
Columns: [timestamp, open, high, low, close, volume]
Index: DatetimeIndex
Data types: float64 for OHLCV, int64 for volume
Timezone: UTC (standardized)
```

### Key Abstraction Points

Different providers have variations that need normalization:

1. **Timeframe Representation**:
   - yfinance: '1d', '1h', '1m'
   - Alpaca: TimeFrame.Day, TimeFrame.Hour (enums)
   - IB: '1 day', '1 hour' (string format)
   - **Solution**: Internal enum mapped to provider-specific formats

2. **Authentication**:
   - yfinance: No authentication needed
   - Alpaca: API key + secret
   - IB: TWS/Gateway connection
   - **Solution**: Provider-specific configuration in settings

3. **Column Names**:
   - Different providers may use 'Close' vs 'close'
   - **Solution**: Normalize to lowercase in provider implementation

4. **Timezone Handling**:
   - Standardize all timestamps to UTC
   - Provider implementations handle timezone conversion

## Progressive Implementation Plan

### Phase 1: Foundation (Current)
- Implement `UniverseSelector` abstract base class and basic implementation
- Implement `DataProvider` abstract base class
- Implement `YFinanceProvider` as first concrete provider
- Define standard data formats and contracts
- **Goal**: Enable strategy development with historical data for selected universe

### Phase 2: Production Data (Post-validation)
- Implement `AlpacaProvider`
- Add provider configuration system (YAML/environment variables)
- Validate data consistency between providers
- **Goal**: Enable paper trading with better data quality

### Phase 3: Professional Grade (Pre-production)
- Implement `IBProvider` if needed
- Add real-time streaming support to interface
- Implement data quality monitoring
- **Goal**: Production-ready data infrastructure

## Benefits of This Design

1. **Low Initial Friction**: Start with yfinance's simplicity
2. **Future-Proof**: Easy migration path to better data sources
3. **Testability**: Mock providers for unit testing
4. **Strategy Portability**: Strategies don't depend on specific data sources
5. **Risk Reduction**: Can A/B test data sources without code changes

## Data Storage

**Decision deferred** - Will be discussed when addressing:
- Caching historical data to reduce API calls
- Backtesting data management
- Performance requirements

Initial approach: Direct API calls, no caching (sufficient for daily strategies).

## Error Handling

Each provider implementation should:
- Handle rate limiting gracefully
- Retry transient failures
- Raise consistent exception types
- Log data quality issues

Specific error handling strategies TBD during implementation.

## Configuration

Providers should be selectable via configuration:

```yaml
# Conceptual example
data:
  provider: yfinance  # or alpaca, ib
  yfinance:
    # provider-specific settings
  alpaca:
    api_key: ${ALPACA_API_KEY}
    api_secret: ${ALPACA_SECRET_KEY}
    paper: true
```

## Next Steps

1. Design and discuss remaining layers (strategy, execution, risk)
2. Define overall system architecture showing layer interactions
3. Implement `DataProvider` abstraction
4. Implement `YFinanceProvider`

## Related Documents

- [tech-stack.md](tech-stack.md) - Technology selection rationale
- [architecture-overview.md](architecture-overview.md) - How data layer fits in overall system (TBD)
