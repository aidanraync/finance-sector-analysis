"""
load_to_db.py
-------------
Loads all cleaned data into a local SQLite database (finance.db).

What this script does:
    1. Creates finance.db with three tables: sectors, prices, macro
    2. Loads cleaned CSVs into each table
    3. Adds indexes on ticker and date for fast query performance
    4. Runs a quick row-count validation after loading

Usage:
    python scripts/load_to_db.py

Inputs:  data/cleaned/
Outputs: finance.db (in project root)
"""

import os
import logging
import sqlite3
import pandas as pd

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

CLEANED_DIR = os.path.join("data", "cleaned")
DB_PATH     = "finance.db"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS sectors (
    ticker   TEXT PRIMARY KEY,
    company  TEXT NOT NULL,
    sector   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS prices (
    date          TEXT    NOT NULL,
    ticker        TEXT    NOT NULL,
    close         REAL    NOT NULL,
    daily_return  REAL,
    sector        TEXT    NOT NULL,
    company       TEXT    NOT NULL,
    PRIMARY KEY (date, ticker)
);

CREATE TABLE IF NOT EXISTS macro (
    date                 TEXT PRIMARY KEY,
    federal_funds_rate   REAL,
    cpi                  REAL
);
"""

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_prices_ticker ON prices (ticker);",
    "CREATE INDEX IF NOT EXISTS idx_prices_date   ON prices (date);",
    "CREATE INDEX IF NOT EXISTS idx_prices_sector ON prices (sector);",
    "CREATE INDEX IF NOT EXISTS idx_macro_date    ON macro  (date);",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_csv(filename: str) -> pd.DataFrame:
    path = os.path.join(CLEANED_DIR, filename)
    df = pd.read_csv(path)
    log.info("Loaded: %s (%d rows)", path, len(df))
    return df


def create_schema(conn: sqlite3.Connection):
    """Drop existing tables and recreate schema from scratch."""
    log.info("Creating schema...")
    cursor = conn.cursor()

    # Drop tables if they exist so re-runs are safe
    for table in ["prices", "sectors", "macro"]:
        cursor.execute(f"DROP TABLE IF EXISTS {table}")
        log.info("  Dropped table (if existed): %s", table)

    conn.executescript(SCHEMA)
    conn.commit()
    log.info("Schema created.")


def create_indexes(conn: sqlite3.Connection):
    log.info("Creating indexes...")
    for stmt in INDEXES:
        conn.execute(stmt)
    conn.commit()
    log.info("Indexes created.")


def load_table(conn: sqlite3.Connection, df: pd.DataFrame, table: str):
    """Load a DataFrame into a SQLite table."""
    log.info("Loading %d rows into table: %s...", len(df), table)
    df.to_sql(table, conn, if_exists="append", index=False)
    log.info("  Done.")


def validate(conn: sqlite3.Connection):
    """Print row counts and a sample query to confirm data loaded correctly."""
    log.info("=" * 55)
    log.info("VALIDATION")
    log.info("=" * 55)

    cursor = conn.cursor()

    for table in ["sectors", "prices", "macro"]:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        log.info("  %-10s  %d rows", table, count)

    # Spot check: sector breakdown from the DB
    log.info("\nSector ticker counts (from DB):")
    cursor.execute("""
        SELECT sector, COUNT(DISTINCT ticker) as tickers
        FROM prices
        GROUP BY sector
        ORDER BY tickers DESC
    """)
    for row in cursor.fetchall():
        log.info("  %-35s %d", row[0], row[1])

    # Spot check: date range
    cursor.execute("SELECT MIN(date), MAX(date) FROM prices")
    min_date, max_date = cursor.fetchone()
    log.info("\nPrice date range: %s to %s", min_date, max_date)

    # Spot check: macro date range
    cursor.execute("SELECT MIN(date), MAX(date) FROM macro")
    min_date, max_date = cursor.fetchone()
    log.info("Macro date range: %s to %s", min_date, max_date)

    log.info("=" * 55)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    log.info("=" * 55)
    log.info("S&P 500 Sector Analysis — load_to_db.py")
    log.info("=" * 55)

    # Load cleaned CSVs
    tickers = load_csv("tickers.csv")
    prices  = load_csv("prices.csv")
    macro   = load_csv("macro.csv")

    # Trim prices to only the columns the DB schema expects
    prices = prices[["date", "ticker", "close", "daily_return", "sector", "company"]]

    # Connect to SQLite (creates finance.db if it doesn't exist)
    log.info("Connecting to database: %s", DB_PATH)
    conn = sqlite3.connect(DB_PATH)

    try:
        create_schema(conn)
        load_table(conn, tickers, "sectors")
        load_table(conn, prices,  "prices")
        load_table(conn, macro,   "macro")
        create_indexes(conn)
        validate(conn)
    finally:
        conn.close()
        log.info("Database connection closed.")

    log.info("load_to_db.py complete. Database saved to: %s", DB_PATH)
    log.info("Next step: write your SQL files in sql/ then run scripts/analyze.py")


if __name__ == "__main__":
    main()
