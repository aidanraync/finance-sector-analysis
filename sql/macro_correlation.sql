-- macro_correlation.sql
-- ----------------------
-- Examines how sector performance relates to macroeconomic conditions
-- by bucketing the federal funds rate into regimes and comparing
-- average sector returns across those regimes.
--
-- Why buckets instead of a correlation coefficient?
-- SQLite has no CORR() function. Bucketing is actually more readable
-- for a portfolio project — it tells a cleaner story.
--
-- Rate regimes:
--   Low  : federal_funds_rate <  1.0  (near-zero / accommodative)
--   Mid  : federal_funds_rate >= 1.0 AND < 4.0
--   High : federal_funds_rate >= 4.0  (restrictive / tightening)
--
-- Output columns:
--   sector          - GICS sector name
--   rate_regime     - 'low', 'mid', or 'high'
--   avg_daily_return- mean daily return in that regime
--   trading_days    - number of days in the regime for this sector

WITH prices_macro AS (
    -- Join daily prices to macro data on date
    SELECT
        p.sector,
        p.ticker,
        p.date,
        p.daily_return,
        m.federal_funds_rate,
        CASE
            WHEN m.federal_funds_rate <  1.0 THEN 'low'
            WHEN m.federal_funds_rate <  4.0 THEN 'mid'
            ELSE                                  'high'
        END     AS rate_regime
    FROM prices p
    JOIN macro m ON m.date = p.date
    WHERE p.daily_return IS NOT NULL
      AND m.federal_funds_rate IS NOT NULL
)

SELECT
    sector,
    rate_regime,
    ROUND(AVG(daily_return), 8)     AS avg_daily_return,
    COUNT(*)                        AS trading_days
FROM prices_macro
GROUP BY sector, rate_regime
ORDER BY sector, 
    CASE rate_regime
        WHEN 'low'  THEN 1
        WHEN 'mid'  THEN 2
        WHEN 'high' THEN 3
    END;
