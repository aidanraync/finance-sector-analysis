"""
fetch_data.py
-------------
Fetches all raw data for the S&P 500 Sector Performance Analysis project.

What this script does:
    1. Pulls the S&P 500 ticker list + GICS sector mapping from Wikipedia
    2. Downloads 5 years of daily adjusted closing prices via yfinance
    3. Downloads Federal Funds Rate and CPI data from FRED (St. Louis Fed)
    4. Saves everything raw to data/raw/ — no transformations here

Usage:
    python scripts/fetch_data.py

Requirements:
    pip install yfinance pandas requests
"""

import os
import time
import logging
import requests
import pandas as pd
import yfinance as yf

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

RAW_DIR = os.path.join("data", "raw")

PRICE_START = "2020-01-01"
PRICE_END   = "2024-12-31"

# FRED CSV endpoints — no API key required
FRED_URLS = {
    "federal_funds_rate": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=FEDFUNDS",
    "cpi":                "https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPIAUCSL",
}

# Batch size for yfinance downloads (avoids hitting rate limits)
BATCH_SIZE = 50
BATCH_PAUSE = 2  # seconds between batches

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
    """Create output directories if they don't exist."""
    os.makedirs(RAW_DIR, exist_ok=True)
    log.info("Output directory ready: %s", RAW_DIR)


def fetch_sp500_tickers() -> pd.DataFrame:
    """
    Scrape the S&P 500 constituent list from Wikipedia.

    Returns a DataFrame with columns:
        ticker   - stock symbol (e.g. 'AAPL')
        sector   - GICS sector (e.g. 'Information Technology')
        company  - company name
    """
    log.info("Fetching S&P 500 ticker list from Wikipedia...")

    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    tables = pd.read_html(
        url,
        storage_options={"User-Agent": "Mozilla/5.0 (research project)"},
    )

    df = tables[0][["Symbol", "Security", "GICS Sector"]].copy()
    df.columns = ["ticker", "company", "sector"]

    # BRK.B and BF.B use dots on Wikipedia but yfinance expects hyphens
    df["ticker"] = df["ticker"].str.replace(".", "-", regex=False)

    log.info("Found %d tickers across %d sectors.", len(df), df["sector"].nunique())
    return df


def fetch_prices(tickers: list[str]) -> pd.DataFrame:
    """
    Download daily adjusted closing prices for all tickers using yfinance.

    Downloads in batches to stay within rate limits.
    Returns a DataFrame with columns: date, ticker, close
    """
    log.info(
        "Downloading price data for %d tickers (%s to %s)...",
        len(tickers), PRICE_START, PRICE_END,
    )

    all_frames = []
    batches = [tickers[i:i + BATCH_SIZE] for i in range(0, len(tickers), BATCH_SIZE)]

    for i, batch in enumerate(batches, start=1):
        log.info("  Batch %d / %d (%d tickers)...", i, len(batches), len(batch))

        raw = yf.download(
            batch,
            start=PRICE_START,
            end=PRICE_END,
            auto_adjust=True,   # adjusts for splits and dividends automatically
            progress=False,
        )

        if raw.empty:
            log.warning("  Batch %d returned no data — skipping.", i)
            continue

        # yfinance returns a MultiIndex columns (metric, ticker)
        # We only need Close prices
        close = raw["Close"].copy()

        # Reshape from wide (date x ticker) to long (date, ticker, close)
        close = close.reset_index().melt(
            id_vars="Date",
            var_name="ticker",
            value_name="close",
        )
        close.rename(columns={"Date": "date"}, inplace=True)
        close.dropna(subset=["close"], inplace=True)

        all_frames.append(close)

        if i < len(batches):
            time.sleep(BATCH_PAUSE)

    if not all_frames:
        raise RuntimeError("No price data was downloaded. Check your internet connection.")

    prices = pd.concat(all_frames, ignore_index=True)
    log.info("Downloaded %d price rows for %d tickers.", len(prices), prices["ticker"].nunique())
    return prices


def fetch_macro_series(name: str, url: str) -> pd.DataFrame:
    """
    Download a single FRED time series via its CSV endpoint.

    Returns a DataFrame with columns: date, <name>
    """
    log.info("Fetching macro series: %s...", name)

    response = requests.get(url, timeout=30)
    response.raise_for_status()

    from io import StringIO
    df = pd.read_csv(StringIO(response.text))
    df.columns = ["date", name]
    df["date"] = pd.to_datetime(df["date"])

    # FRED uses '.' as a placeholder for missing values
    df[name] = pd.to_numeric(df[name], errors="coerce")

    log.info("  %s: %d rows (%s to %s).", name, len(df), df["date"].min().date(), df["date"].max().date())
    return df


def save(df: pd.DataFrame, filename: str):
    """Save a DataFrame to data/raw/ as CSV."""
    path = os.path.join(RAW_DIR, filename)
    df.to_csv(path, index=False)
    log.info("Saved: %s (%d rows)", path, len(df))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    log.info("=" * 55)
    log.info("S&P 500 Sector Analysis — fetch_data.py")
    log.info("=" * 55)

    make_dirs()

    # 1. Ticker + sector mapping
    tickers_df = fetch_sp500_tickers()
    save(tickers_df, "sp500_tickers.csv")

    # 2. Price history
    ticker_list = tickers_df["ticker"].tolist()
    prices_df = fetch_prices(ticker_list)
    save(prices_df, "prices_raw.csv")

    # 3. Macro data from FRED
    for series_name, url in FRED_URLS.items():
        macro_df = fetch_macro_series(series_name, url)
        save(macro_df, f"{series_name}_raw.csv")

    log.info("=" * 55)
    log.info("fetch_data.py complete. Files saved to data/raw/")
    log.info("Next step: run scripts/clean_data.py")
    log.info("=" * 55)


if __name__ == "__main__":
    main()
