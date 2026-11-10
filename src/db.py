import os
import sqlite3
import pandas as pd

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "prices.db")

def get_connection(db_path=DB_PATH):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db(db_path=DB_PATH):
    """Initialize schema for bulletins, commodities, markets, and prices."""
    conn = get_connection(db_path)
    cur = conn.cursor()

    cur.executescript("""
    CREATE TABLE IF NOT EXISTS bulletins (
        bulletin_id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        source TEXT NOT NULL, -- 'HARTI' or 'CBSL'
        language TEXT DEFAULT 'EN',
        url TEXT UNIQUE NOT NULL,
        local_path TEXT,
        file_size INTEGER DEFAULT 0,
        download_status TEXT DEFAULT 'PENDING', -- 'PENDING', 'DOWNLOADED', 'FAILED'
        parse_status TEXT DEFAULT 'PENDING',    -- 'PENDING', 'PARSED', 'FAILED', 'EMPTY'
        num_rows INTEGER DEFAULT 0,
        error_message TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS commodities (
        commodity_id TEXT PRIMARY KEY,
        canonical_name TEXT NOT NULL,
        category TEXT, -- 'Up-Country', 'Low-Country', 'Other'
        default_margin_pct REAL DEFAULT 0.15
    );

    CREATE TABLE IF NOT EXISTS markets (
        market_id TEXT PRIMARY KEY,
        market_name TEXT NOT NULL,
        market_type TEXT NOT NULL, -- 'WHOLESALE_HUB', 'COLOMBO_TERMINAL', 'REGIONAL'
        province TEXT
    );

    CREATE TABLE IF NOT EXISTS wholesale_prices (
        date TEXT NOT NULL,
        commodity_id TEXT NOT NULL,
        market_id TEXT NOT NULL,
        price_low REAL,
        price_high REAL,
        price_mid REAL,
        is_traded INTEGER NOT NULL DEFAULT 1,
        source TEXT DEFAULT 'HARTI',
        PRIMARY KEY (date, commodity_id, market_id),
        FOREIGN KEY (commodity_id) REFERENCES commodities(commodity_id),
        FOREIGN KEY (market_id) REFERENCES markets(market_id)
    );

    CREATE TABLE IF NOT EXISTS retail_prices (
        date TEXT NOT NULL,
        commodity_id TEXT NOT NULL,
        market_id TEXT NOT NULL,
        price_low REAL,
        price_high REAL,
        price_mid REAL,
        is_traded INTEGER NOT NULL DEFAULT 1,
        source TEXT DEFAULT 'HARTI',
        PRIMARY KEY (date, commodity_id, market_id),
        FOREIGN KEY (commodity_id) REFERENCES commodities(commodity_id),
        FOREIGN KEY (market_id) REFERENCES markets(market_id)
    );

    CREATE INDEX IF NOT EXISTS idx_wholesale_date ON wholesale_prices(date);
    CREATE INDEX IF NOT EXISTS idx_wholesale_comm ON wholesale_prices(commodity_id);
    CREATE INDEX IF NOT EXISTS idx_wholesale_mkt ON wholesale_prices(market_id);
    CREATE INDEX IF NOT EXISTS idx_bulletin_date ON bulletins(date);
    """)

    # Pre-populate canonical commodities
    canonical_commodities = [
        ('BEANS', 'Beans (Green / Bochi)', 'Up-Country', 0.15),
        ('CARROT', 'Carrot', 'Up-Country', 0.15),
        ('TOMATO', 'Tomato', 'Up-Country', 0.15),
        ('LEEKS', 'Leeks', 'Up-Country', 0.15),
        ('CABBAGE', 'Cabbage', 'Up-Country', 0.15),
        ('BEET_ROOT', 'Beet root', 'Up-Country', 0.15),
        ('KNOLKHOL', 'Knolkhol', 'Up-Country', 0.15),
        ('RADDISH', 'Raddish', 'Up-Country', 0.15),
        ('GREEN_CHILLI', 'Green Chilli', 'Low-Country', 0.18),
        ('BIG_ONION', 'Big Onion (Local/Imported)', 'Other', 0.12),
        ('POTATO', 'Potato (Nuwara Eliya / Welimada)', 'Up-Country', 0.12),
        ('BRINJAL', 'Brinjal', 'Low-Country', 0.15),
        ('PUMPKIN', 'Pumpkin', 'Low-Country', 0.15),
        ('SNAKE_GOURD', 'Snake Gourd', 'Low-Country', 0.15),
        ('BITTER_GOURD', 'Bitter Gourd', 'Low-Country', 0.15)
    ]
    cur.executemany("""
        INSERT OR IGNORE INTO commodities (commodity_id, canonical_name, category, default_margin_pct)
        VALUES (?, ?, ?, ?)
    """, canonical_commodities)

    # Pre-populate canonical markets
    canonical_markets = [
        ('DAMBULLA', 'Dambulla Dedicated Economic Centre', 'WHOLESALE_HUB', 'Central'),
        ('PELIYAGODA', 'Peliyagoda Manning Market', 'COLOMBO_TERMINAL', 'Western'),
        ('PETTAH', 'Pettah Wholesale / Retail Market', 'COLOMBO_TERMINAL', 'Western'),
        ('MEEGODA', 'Meegoda Economic Centre', 'REGIONAL', 'Western'),
        ('KEPPETIPOLA', 'Keppetipola Economic Centre', 'WHOLESALE_HUB', 'Uva'),
        ('NUWARA_ELIYA', 'Nuwara Eliya Wholesale Market', 'WHOLESALE_HUB', 'Central'),
        ('KANDY', 'Kandy Wholesale Market', 'REGIONAL', 'Central'),
        ('BANDARAWELA', 'Bandarawela Wholesale Market', 'WHOLESALE_HUB', 'Uva'),
        ('THAMBUTHTHEGAMA', 'Thambuththegama DEC', 'WHOLESALE_HUB', 'North Central'),
        ('VEYANGODA', 'Veyangoda Market', 'REGIONAL', 'Western'),
        ('NOROCHCHOLE', 'Norochchole Market', 'REGIONAL', 'North Western')
    ]
    cur.executemany("""
        INSERT OR IGNORE INTO markets (market_id, market_name, market_type, province)
        VALUES (?, ?, ?, ?)
    """, canonical_markets)

    conn.commit()
    conn.close()
    print(f"Database initialized successfully at {db_path}")

if __name__ == "__main__":
    init_db()
