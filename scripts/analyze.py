"""
analyze.py
----------
Runs all SQL queries against finance.db and exports results to outputs/tables/.

What this script does:
    1. Reads each .sql file from the sql/ directory
    2. Executes it against finance.db
    3. Saves the results as CSVs to outputs/tables/
    4. Prints a preview of each result to the console

Usage:
    python scripts/analyze.py

Inputs:  finance.db, sql/*.sql
Outputs: outputs/tables/*.csv
"""

import os
import logging
import sqlite3
import pandas as pd

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DB_PATH     = "finance.db"
SQL_DIR     = "sql"
TABLES_DIR  = os.path.join("outputs", "tables")

# Maps sql filename -> output csv filename + display title
QUERIES = [
    {
        "sql_file": "sector_annual_returns.sql",
        "out_file": "sector_annual_returns.csv",
        "title":    "Sector Annual Returns (2020-2024)",
    },
    {
        "sql_file": "sector_volatility.sql",
        "out_file": "sector_volatility.csv",
        "title":    "Sector Volatility & Sharpe Ratio",
    },
    {
        "sql_file": "bear_vs_recovery.sql",
        "out_file": "bear_vs_recovery.csv",
        "title":    "Bear Market (2022) vs Recovery (2023-2024)",
    },
    {
        "sql_file": "top_bottom_stocks_per_sector.sql",
        "out_file": "top_bottom_stocks.csv",
        "title":    "Top & Bottom 3 Stocks Per Sector (Full Period)",
    },
    {
        "sql_file": "macro_correlation.sql",
        "out_file": "macro_correlation.csv",
        "title":    "Sector Returns by Interest Rate Regime",
    },
]

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
# Helpers
# ---------------------------------------------------------------------------

def make_dirs():
    os.makedirs(TABLES_DIR, exist_ok=True)
    log.info("Output directory ready: %s", TABLES_DIR)


def load_sql(filename: str) -> str:
    path = os.path.join(SQL_DIR, filename)
    with open(path, "r") as f:
        return f.read()


def run_query(conn: sqlite3.Connection, sql: str) -> pd.DataFrame:
    return pd.read_sql_query(sql, conn)


def save(df: pd.DataFrame, filename: str):
    path = os.path.join(TABLES_DIR, filename)
    df.to_csv(path, index=False)
    log.info("Saved: %s (%d rows)", path, len(df))


def preview(df: pd.DataFrame, title: str):
    """Print a readable preview of a result table."""
    print()
    print("=" * 65)
    print(f"  {title}")
    print("=" * 65)
    # Format decimal columns as percentages where they represent returns
    display = df.copy()
    for col in display.columns:
        if "return" in col or "vol" in col:
            display[col] = display[col].apply(
                lambda x: f"{x:.2%}" if pd.notna(x) else "N/A"
            )
    print(display.to_string(index=False))
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    log.info("=" * 55)
    log.info("S&P 500 Sector Analysis — analyze.py")
    log.info("=" * 55)

    make_dirs()

    conn = sqlite3.connect(DB_PATH)

    try:
        for query in QUERIES:
            log.info("Running: %s", query["sql_file"])

            sql = load_sql(query["sql_file"])
            df  = run_query(conn, sql)

            save(df, query["out_file"])
            preview(df, query["title"])

    finally:
        conn.close()
        log.info("Database connection closed.")

    log.info("=" * 55)
    log.info("analyze.py complete. Tables saved to outputs/tables/")
    log.info("Next step: run scripts/visualize.py")
    log.info("=" * 55)


if __name__ == "__main__":
    main()
