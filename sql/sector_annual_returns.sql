-- sector_annual_returns.sql
-- -------------------------
-- Calculates the average annual return for each sector, per year.
--
-- Method:
--   For each ticker, find its first and last closing price within the year.
--   Annual return = (last_close / first_close) - 1
--   Sector return = average of all ticker returns within that sector.
--
-- Output columns:
--   year            - calendar year (2020-2024)
--   sector          - GICS sector name
--   avg_return      - average annual return across tickers in sector (decimal)
--   ticker_count    - number of tickers contributing to the average

WITH yearly_bounds AS (
    -- Get the first and last trading date per ticker per year
    SELECT
        ticker,
        sector,
        STRFTIME('%Y', date)            AS year,
        MIN(date)                       AS first_date,
        MAX(date)                       AS last_date
    FROM prices
    GROUP BY ticker, sector, STRFTIME('%Y', date)
),

ticker_prices AS (
    -- Join back to prices to get the actual close values on those dates
    SELECT
        b.ticker,
        b.sector,
        b.year,
        p_first.close   AS first_close,
        p_last.close    AS last_close
    FROM yearly_bounds b
    JOIN prices p_first
        ON p_first.ticker = b.ticker
        AND p_first.date  = b.first_date
    JOIN prices p_last
        ON p_last.ticker = b.ticker
        AND p_last.date  = b.last_date
),

ticker_returns AS (
    -- Calculate annual return per ticker
    SELECT
        ticker,
        sector,
        year,
        ROUND((last_close / first_close) - 1, 6) AS annual_return
    FROM ticker_prices
    WHERE first_close > 0   -- guard against divide-by-zero
)

-- Aggregate to sector level
SELECT
    year,
    sector,
    ROUND(AVG(annual_return), 6)    AS avg_return,
    COUNT(DISTINCT ticker)          AS ticker_count
FROM ticker_returns
GROUP BY year, sector
ORDER BY year, avg_return DESC;
