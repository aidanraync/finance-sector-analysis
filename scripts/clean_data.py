"""
clean_data.py
-------------
Cleans and prepares all raw data for the S&P 500 Sector Performance Analysis.

What this script does:
    1. Cleans the ticker/sector mapping (dedupe, normalize sector names)
    2. Cleans price data (drops delisted tickers, forward-fills small gaps,
       removes outliers, adds daily return column)
    3. Cleans macro data (filters to analysis window, interpolates monthly
       FRED data to daily frequency for joins)
    4. Saves all cleaned outputs to data/cleaned/

Usage:
    python scripts/clean_data.py

Inputs:  data/raw/
Outputs: data/cleaned/
"""

import os
import logging
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

RAW_DIR     = os.path.join("data", "raw")
CLEANED_DIR = os.path.join("data", "cleaned")

ANALYSIS_START = "2020-01-01"
ANALYSIS_END   = "2024-12-31"

# Drop a ticker if it has fewer than this many trading days of data
MIN_TRADING_DAYS = 200

# Forward-fill gaps up to this many consecutive days (covers weekends + holidays)
MAX_FFILL_DAYS = 5

# Flag daily returns beyond this many standard deviations as outliers
OUTLIER_STD = 10

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
    os.makedirs(CLEANED_DIR, exist_ok=True)
    log.info("Output directory ready: %s", CLEANED_DIR)


def load(filename: str) -> pd.DataFrame:
    path = os.path.join(RAW_DIR, filename)
    df = pd.read_csv(path)
    log.info("Loaded: %s (%d rows)", path, len(df))
    return df


def save(df: pd.DataFrame, filename: str):
    path = os.path.join(CLEANED_DIR, filename)
    df.to_csv(path, index=False)
    log.info("Saved:  %s (%d rows)", path, len(df))


# ---------------------------------------------------------------------------
# Cleaning functions
# ---------------------------------------------------------------------------

def clean_tickers(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean the S&P 500 ticker/sector mapping.
        - Drop duplicate tickers
        - Strip whitespace from all string columns
        - Normalize sector names to title case
    """
    log.info("--- Cleaning ticker/sector mapping ---")

    before = len(df)
    df = df.drop_duplicates(subset=["ticker"])
    df["ticker"]  = df["ticker"].str.strip()
    df["sector"]  = df["sector"].str.strip().str.title()
    df["company"] = df["company"].str.strip()

    log.info("Tickers: %d -> %d after deduplication", before, len(df))
    log.info("Sectors found:\n%s", df["sector"].value_counts().to_string())
    return df


def clean_prices(prices: pd.DataFrame, tickers: pd.DataFrame) -> pd.DataFrame:
    """
    Clean the raw price data.
        - Parse and filter dates to the analysis window
        - Drop tickers with too few trading days (delisted/missing)
        - Forward-fill small gaps (weekends, holidays, data gaps)
        - Calculate daily return for each ticker
        - Flag and remove outlier returns
        - Merge sector labels onto price data
    """
    log.info("--- Cleaning price data ---")

    # Parse dates and filter to analysis window
    prices["date"] = pd.to_datetime(prices["date"])
    prices = prices[
        (prices["date"] >= ANALYSIS_START) &
        (prices["date"] <= ANALYSIS_END)
    ].copy()
    log.info("After date filter: %d rows", len(prices))

    # Drop tickers with insufficient data
    ticker_counts = prices.groupby("ticker")["date"].count()
    valid_tickers = ticker_counts[ticker_counts >= MIN_TRADING_DAYS].index
    dropped = ticker_counts[ticker_counts < MIN_TRADING_DAYS].index.tolist()
    if dropped:
        log.info("Dropping %d tickers with < %d trading days: %s",
                 len(dropped), MIN_TRADING_DAYS, dropped)
    prices = prices[prices["ticker"].isin(valid_tickers)].copy()
    log.info("After dropping thin tickers: %d tickers remain", prices["ticker"].nunique())

    # Sort and forward-fill small gaps per ticker
    prices = prices.sort_values(["ticker", "date"])
    prices["close"] = (
        prices.groupby("ticker")["close"]
        .transform(lambda s: s.ffill(limit=MAX_FFILL_DAYS))
    )

    # Calculate daily return: (today / yesterday) - 1
    prices["daily_return"] = (
        prices.groupby("ticker")["close"]
        .pct_change()
    )

    # Remove outlier returns (data errors, corporate actions not adjusted)
    std_threshold = prices["daily_return"].std() * OUTLIER_STD
    outliers = prices["daily_return"].abs() > std_threshold
    if outliers.sum() > 0:
        log.info("Removing %d outlier return rows (> %dx std dev)", outliers.sum(), OUTLIER_STD)
        prices = prices[~outliers].copy()

    # Merge sector labels
    prices = prices.merge(
        tickers[["ticker", "sector", "company"]],
        on="ticker",
        how="left",
    )

    missing_sector = prices["sector"].isna().sum()
    if missing_sector > 0:
        log.warning("%d rows have no sector label — dropping.", missing_sector)
        prices = prices.dropna(subset=["sector"])

    log.info(
        "Price data clean: %d rows | %d tickers | %d sectors",
        len(prices),
        prices["ticker"].nunique(),
        prices["sector"].nunique(),
    )
    return prices


def clean_macro(df: pd.DataFrame, series_name: str) -> pd.DataFrame:
    """
    Clean a FRED macro series.
        - Parse dates
        - Filter to analysis window
        - Drop missing values
        - Interpolate from monthly to daily frequency (forward-fill)
          so it can be joined to daily price data later
    """
    log.info("--- Cleaning macro series: %s ---", series_name)

    df["date"] = pd.to_datetime(df["date"])
    df = df[
        (df["date"] >= ANALYSIS_START) &
        (df["date"] <= ANALYSIS_END)
    ].copy()

    before = len(df)
    df = df.dropna(subset=[series_name])
    log.info("%s: %d -> %d rows after dropping nulls", series_name, before, len(df))

    # Reindex to daily and forward-fill (FRED data is monthly)
    df = df.set_index("date")
    daily_index = pd.date_range(start=ANALYSIS_START, end=ANALYSIS_END, freq="D")
    df = df.reindex(daily_index)
    df.index.name = "date"
    df[series_name] = df[series_name].ffill()
    df = df.reset_index()

    log.info("%s interpolated to daily: %d rows", series_name, len(df))
    return df


def build_macro_combined(ffr: pd.DataFrame, cpi: pd.DataFrame) -> pd.DataFrame:
    """Merge federal funds rate and CPI into a single daily macro table."""
    log.info("--- Building combined macro table ---")
    macro = ffr.merge(cpi, on="date", how="outer").sort_values("date")
    log.info("Combined macro table: %d rows", len(macro))
    return macro


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate(prices: pd.DataFrame, tickers: pd.DataFrame, macro: pd.DataFrame):
    """Print a summary so you can sanity-check the outputs before loading to DB."""
    log.info("=" * 55)
    log.info("VALIDATION SUMMARY")
    log.info("=" * 55)
    log.info("Tickers:  %d rows | columns: %s", len(tickers), list(tickers.columns))
    log.info("Prices:   %d rows | %d tickers | date range: %s to %s",
             len(prices),
             prices["ticker"].nunique(),
             prices["date"].min().date(),
             prices["date"].max().date())
    log.info("Macro:    %d rows | date range: %s to %s",
             len(macro),
             macro["date"].min().date(),
             macro["date"].max().date())

    null_counts = prices[["close", "daily_return", "sector"]].isna().sum()
    log.info("Null counts in prices:\n%s", null_counts.to_string())

    log.info("Sector distribution:\n%s",
             prices.groupby("sector")["ticker"].nunique().sort_values(ascending=False).to_string())
    log.info("=" * 55)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    log.info("=" * 55)
    log.info("S&P 500 Sector Analysis — clean_data.py")
    log.info("=" * 55)

    make_dirs()

    # Load raw data
    tickers_raw = load("sp500_tickers.csv")
    prices_raw  = load("prices_raw.csv")
    ffr_raw     = load("federal_funds_rate_raw.csv")
    cpi_raw     = load("cpi_raw.csv")

    # Clean each dataset
    tickers_clean = clean_tickers(tickers_raw)
    prices_clean  = clean_prices(prices_raw, tickers_clean)
    ffr_clean     = clean_macro(ffr_raw, "federal_funds_rate")
    cpi_clean     = clean_macro(cpi_raw, "cpi")
    macro_clean   = build_macro_combined(ffr_clean, cpi_clean)

    # Validate before saving
    validate(prices_clean, tickers_clean, macro_clean)

    # Save
    save(tickers_clean, "tickers.csv")
    save(prices_clean,  "prices.csv")
    save(macro_clean,   "macro.csv")

    log.info("clean_data.py complete. Files saved to data/cleaned/")
    log.info("Next step: run scripts/load_to_db.py")


if __name__ == "__main__":
    main()
