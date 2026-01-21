CREATE TABLE IF NOT EXISTS market_data (
    symbol TEXT NOT NULL,
    date TEXT NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume INTEGER NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (symbol, date)
);

CREATE INDEX IF NOT EXISTS idx_market_data_symbol ON market_data(symbol);
CREATE INDEX IF NOT EXISTS idx_market_data_date ON market_data(date);

-- Universe selection history
CREATE TABLE IF NOT EXISTS universes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    symbol TEXT NOT NULL,
    date TEXT NOT NULL,
    rank INTEGER,
    metadata TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(name, symbol, date)
);

CREATE INDEX IF NOT EXISTS idx_universes_name ON universes(name);
CREATE INDEX IF NOT EXISTS idx_universes_date ON universes(date);
CREATE INDEX IF NOT EXISTS idx_universes_symbol ON universes(symbol);
