-- bear_vs_recovery.sql
-- ---------------------
-- Compares sector performance during the 2022 bear market vs the 2023-2024 recovery.
--
-- Windows:
--   Bear market : 2022-01-01 to 2022-12-31  (S&P 500 fell ~19%)
--   Recovery    : 2023-01-01 to 2024-12-31  (S&P 500 recovered and hit new highs)
--
-- Method: same as sector_annual_returns — price return over each full window.
--
-- Output columns:
--   sector          - GICS sector name
--   bear_return     - sector return during 2022 bear market
--   recovery_return - sector return during 2023-2024 recovery
--   difference      - recovery_return - bear_return (spread)

WITH period_bounds AS (
    -- First and last trading date per ticker within each period
    SELECT
        ticker,
        sector,
        CASE
            WHEN date BETWEEN '2022-01-01' AND '2022-12-31' THEN 'bear'
            WHEN date BETWEEN '2023-01-01' AND '2024-12-31' THEN 'recovery'
        END                         AS period,
        MIN(date)                   AS first_date,
        MAX(date)                   AS last_date
    FROM prices
    WHERE date BETWEEN '2022-01-01' AND '2024-12-31'
    GROUP BY
        ticker,
        sector,
        CASE
            WHEN date BETWEEN '2022-01-01' AND '2022-12-31' THEN 'bear'
            WHEN date BETWEEN '2023-01-01' AND '2024-12-31' THEN 'recovery'
        END
),

ticker_period_returns AS (
    SELECT
        b.ticker,
        b.sector,
        b.period,
        ROUND((p_last.close / p_first.close) - 1, 6)   AS period_return
    FROM period_bounds b
    JOIN prices p_first
        ON p_first.ticker = b.ticker AND p_first.date = b.first_date
    JOIN prices p_last
        ON p_last.ticker  = b.ticker AND p_last.date  = b.last_date
    WHERE p_first.close > 0
),

sector_period_avg AS (
    SELECT
        sector,
        period,
        ROUND(AVG(period_return), 6)    AS avg_return
    FROM ticker_period_returns
    GROUP BY sector, period
)

SELECT
    bear.sector,
    bear.avg_return                             AS bear_return,
    rec.avg_return                              AS recovery_return,
    ROUND(rec.avg_return - bear.avg_return, 6)  AS difference
FROM sector_period_avg bear
JOIN sector_period_avg rec
    ON rec.sector = bear.sector
    AND rec.period = 'recovery'
WHERE bear.period = 'bear'
ORDER BY difference DESC;
