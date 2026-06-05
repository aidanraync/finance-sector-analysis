-- sector_volatility.sql
-- ----------------------
-- Calculates annualized volatility and a Sharpe-like ratio per sector.
--
-- Method:
--   Volatility = standard deviation of daily returns, annualized by * SQRT(252)
--   252 = approximate number of trading days in a year
--
--   Sharpe-like ratio = avg_daily_return / daily_stddev
--   (simplified: no risk-free rate subtracted, but directionally correct)
--   Higher = better risk-adjusted return.
--
-- Output columns:
--   sector              - GICS sector name
--   avg_daily_return    - mean daily return across all tickers and days
--   daily_stddev        - standard deviation of daily returns
--   annualized_vol      - daily_stddev * SQRT(252), expressed as decimal
--   sharpe_ratio        - avg_daily_return / daily_stddev
--   ticker_count        - number of tickers in sector

WITH sector_stats AS (
    SELECT
        sector,
        AVG(daily_return)                                   AS avg_daily_return,
        -- SQLite has no STDDEV, so we compute it manually:
        -- stddev = SQRT( AVG(x^2) - AVG(x)^2 )
        SQRT(
            AVG(daily_return * daily_return) -
            (AVG(daily_return) * AVG(daily_return))
        )                                                   AS daily_stddev,
        COUNT(DISTINCT ticker)                              AS ticker_count
    FROM prices
    WHERE daily_return IS NOT NULL
    GROUP BY sector
)

SELECT
    sector,
    ROUND(avg_daily_return, 8)                              AS avg_daily_return,
    ROUND(daily_stddev, 8)                                  AS daily_stddev,
    -- Annualize: multiply daily stddev by sqrt(252)
    ROUND(daily_stddev * 15.8745, 6)                        AS annualized_vol,
    ROUND(
        CASE
            WHEN daily_stddev > 0
            THEN avg_daily_return / daily_stddev
            ELSE NULL
        END, 6
    )                                                       AS sharpe_ratio,
    ticker_count
FROM sector_stats
ORDER BY annualized_vol ASC;
