-- top_bottom_stocks_per_sector.sql
-- ----------------------------------
-- Identifies the top 3 and bottom 3 performing stocks within each sector
-- over the full 5-year analysis period (2020-2024).
--
-- Method: total return from first to last available close price.
--
-- Output columns:
--   sector          - GICS sector name
--   ticker          - stock symbol
--   company         - company name
--   total_return    - return over full period (decimal)
--   rank_type       - 'top' or 'bottom'
--   rank            - 1 (best/worst) to 3

WITH full_period_bounds AS (
    SELECT
        ticker,
        sector,
        company,
        MIN(date)   AS first_date,
        MAX(date)   AS last_date
    FROM prices
    GROUP BY ticker, sector, company
),

ticker_total_returns AS (
    SELECT
        b.ticker,
        b.sector,
        b.company,
        ROUND((p_last.close / p_first.close) - 1, 6)   AS total_return
    FROM full_period_bounds b
    JOIN prices p_first
        ON p_first.ticker = b.ticker AND p_first.date = b.first_date
    JOIN prices p_last
        ON p_last.ticker  = b.ticker AND p_last.date  = b.last_date
    WHERE p_first.close > 0
),

ranked AS (
    -- Rank within each sector from highest return (rank 1 = best)
    SELECT
        ticker,
        sector,
        company,
        total_return,
        ROW_NUMBER() OVER (
            PARTITION BY sector
            ORDER BY total_return DESC
        )   AS rank_desc,
        ROW_NUMBER() OVER (
            PARTITION BY sector
            ORDER BY total_return ASC
        )   AS rank_asc
    FROM ticker_total_returns
)

SELECT
    sector,
    ticker,
    company,
    total_return,
    'top'       AS rank_type,
    rank_desc   AS rank
FROM ranked
WHERE rank_desc <= 3

UNION ALL

SELECT
    sector,
    ticker,
    company,
    total_return,
    'bottom'    AS rank_type,
    rank_asc    AS rank
FROM ranked
WHERE rank_asc <= 3

ORDER BY sector, rank_type DESC, rank ASC;
