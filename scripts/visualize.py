"""
visualize.py
------------
Generates 4 charts from the analysis output tables.

Charts produced:
    1. sector_returns_bar.png   - Average annual return by sector (2020-2024)
    2. returns_heatmap.png      - Sector returns heatmap by year
    3. risk_reward_scatter.png  - Return vs volatility (risk/reward quadrant)
    4. bear_vs_recovery_bar.png - Sector performance: bear market vs recovery

Usage:
    python scripts/visualize.py

Inputs:  outputs/tables/*.csv
Outputs: outputs/charts/*.png
"""

import os
import logging
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import seaborn as sns

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

TABLES_DIR = os.path.join("outputs", "tables")
CHARTS_DIR = os.path.join("outputs", "charts")

# Consistent color palette across all charts
SECTOR_PALETTE = "RdYlGn"   # red = bad, green = good (intuitive for finance)
CHART_DPI      = 150
FIG_STYLE      = "seaborn-v0_8-whitegrid"

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
    os.makedirs(CHARTS_DIR, exist_ok=True)
    log.info("Output directory ready: %s", CHARTS_DIR)


def load(filename: str) -> pd.DataFrame:
    path = os.path.join(TABLES_DIR, filename)
    df = pd.read_csv(path)
    log.info("Loaded: %s (%d rows)", path, len(df))
    return df


def save_chart(filename: str):
    path = os.path.join(CHARTS_DIR, filename)
    plt.savefig(path, dpi=CHART_DPI, bbox_inches="tight")
    plt.close()
    log.info("Saved chart: %s", path)


# ---------------------------------------------------------------------------
# Chart 1: Average Annual Return by Sector (bar chart)
# ---------------------------------------------------------------------------

def chart_sector_returns_bar(df: pd.DataFrame):
    """
    Bar chart showing each sector's average annual return
    across the full 2020-2024 period, sorted descending.
    """
    log.info("Generating chart 1: sector returns bar...")

    # Average across all years per sector
    avg = (
        df.groupby("sector")["avg_return"]
        .mean()
        .sort_values(ascending=False)
        .reset_index()
    )

    colors = sns.color_palette(SECTOR_PALETTE, len(avg))

    with plt.style.context(FIG_STYLE):
        fig, ax = plt.subplots(figsize=(12, 6))

        bars = ax.bar(avg["sector"], avg["avg_return"], color=colors, edgecolor="white", linewidth=0.5)

        # Add value labels on each bar
        for bar, val in zip(bars, avg["avg_return"]):
            y_pos = bar.get_height() + 0.003 if val >= 0 else bar.get_height() - 0.018
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                y_pos,
                f"{val:.1%}",
                ha="center", va="bottom", fontsize=8.5, fontweight="bold"
            )

        ax.axhline(0, color="black", linewidth=0.8, linestyle="--", alpha=0.5)
        ax.yaxis.set_major_formatter(mtick.PercentFormatter(xmax=1, decimals=0))
        ax.set_xlabel("Sector", fontsize=11)
        ax.set_ylabel("Avg Annual Return", fontsize=11)
        ax.set_title("S&P 500 Average Annual Return by Sector (2020–2024)", fontsize=13, fontweight="bold", pad=15)
        plt.xticks(rotation=35, ha="right", fontsize=9)
        plt.tight_layout()

    save_chart("sector_returns_bar.png")


# ---------------------------------------------------------------------------
# Chart 2: Sector Returns Heatmap by Year
# ---------------------------------------------------------------------------

def chart_returns_heatmap(df: pd.DataFrame):
    """
    Heatmap with sectors as rows and years as columns.
    Cell color = annual return. Red = negative, green = positive.
    """
    log.info("Generating chart 2: returns heatmap...")

    pivot = df.pivot(index="sector", columns="year", values="avg_return")

    # Sort sectors by total average return (best at top)
    pivot = pivot.loc[pivot.mean(axis=1).sort_values(ascending=False).index]

    with plt.style.context(FIG_STYLE):
        fig, ax = plt.subplots(figsize=(10, 7))

        sns.heatmap(
            pivot,
            annot=True,
            fmt=".1%",
            cmap="RdYlGn",
            center=0,
            linewidths=0.5,
            linecolor="white",
            ax=ax,
            cbar_kws={"format": mtick.PercentFormatter(xmax=1, decimals=0), "shrink": 0.8},
        )

        ax.set_title("S&P 500 Sector Annual Returns Heatmap (2020–2024)", fontsize=13, fontweight="bold", pad=15)
        ax.set_xlabel("Year", fontsize=11)
        ax.set_ylabel("")
        ax.tick_params(axis="y", labelsize=9)
        plt.tight_layout()

    save_chart("returns_heatmap.png")


# ---------------------------------------------------------------------------
# Chart 3: Risk / Reward Scatter (return vs volatility)
# ---------------------------------------------------------------------------

def chart_risk_reward_scatter(df_vol: pd.DataFrame, df_returns: pd.DataFrame):
    """
    Scatter plot: x = annualized volatility, y = average annual return.
    Each point = one sector. Quadrant lines divide high/low risk and return.
    """
    log.info("Generating chart 3: risk/reward scatter...")

    # Get overall avg return per sector across all years
    avg_returns = (
        df_returns.groupby("sector")["avg_return"]
        .mean()
        .reset_index()
        .rename(columns={"avg_return": "avg_annual_return"})
    )

    df = df_vol.merge(avg_returns, on="sector")

    mid_vol    = df["annualized_vol"].median()
    mid_return = df["avg_annual_return"].median()

    colors = sns.color_palette("tab10", len(df))

    with plt.style.context(FIG_STYLE):
        fig, ax = plt.subplots(figsize=(10, 7))

        for i, row in df.iterrows():
            ax.scatter(row["annualized_vol"], row["avg_annual_return"],
                       color=colors[i], s=120, zorder=3)
            ax.annotate(
                row["sector"],
                (row["annualized_vol"], row["avg_annual_return"]),
                textcoords="offset points",
                xytext=(8, 4),
                fontsize=8,
            )

        # Quadrant lines
        ax.axvline(mid_vol,    color="gray", linestyle="--", linewidth=0.8, alpha=0.6)
        ax.axhline(mid_return, color="gray", linestyle="--", linewidth=0.8, alpha=0.6)

        # Quadrant labels
        ax.text(df["annualized_vol"].min() * 1.01, df["avg_annual_return"].max() * 0.97,
                "Low Risk\nHigh Return", fontsize=8, color="green", alpha=0.7)
        ax.text(df["annualized_vol"].max() * 0.85, df["avg_annual_return"].max() * 0.97,
                "High Risk\nHigh Return", fontsize=8, color="orange", alpha=0.7)
        ax.text(df["annualized_vol"].min() * 1.01, df["avg_annual_return"].min() * 1.05,
                "Low Risk\nLow Return", fontsize=8, color="steelblue", alpha=0.7)
        ax.text(df["annualized_vol"].max() * 0.85, df["avg_annual_return"].min() * 1.05,
                "High Risk\nLow Return", fontsize=8, color="red", alpha=0.7)

        ax.xaxis.set_major_formatter(mtick.PercentFormatter(xmax=1, decimals=0))
        ax.yaxis.set_major_formatter(mtick.PercentFormatter(xmax=1, decimals=0))
        ax.set_xlabel("Annualized Volatility", fontsize=11)
        ax.set_ylabel("Avg Annual Return", fontsize=11)
        ax.set_title("S&P 500 Sector Risk vs Return (2020–2024)", fontsize=13, fontweight="bold", pad=15)
        plt.tight_layout()

    save_chart("risk_reward_scatter.png")


# ---------------------------------------------------------------------------
# Chart 4: Bear Market vs Recovery (grouped bar)
# ---------------------------------------------------------------------------

def chart_bear_vs_recovery(df: pd.DataFrame):
    """
    Grouped bar chart: for each sector, two bars side by side —
    one for 2022 bear market return, one for 2023-2024 recovery return.
    Sorted by recovery return descending.
    """
    log.info("Generating chart 4: bear vs recovery bar...")

    df = df.sort_values("recovery_return", ascending=False)
    sectors = df["sector"].tolist()
    x = range(len(sectors))
    width = 0.38

    with plt.style.context(FIG_STYLE):
        fig, ax = plt.subplots(figsize=(13, 6))

        bars_bear = ax.bar(
            [i - width / 2 for i in x],
            df["bear_return"],
            width=width,
            label="2022 Bear Market",
            color="#d62728",
            alpha=0.85,
            edgecolor="white",
        )
        bars_rec = ax.bar(
            [i + width / 2 for i in x],
            df["recovery_return"],
            width=width,
            label="2023–2024 Recovery",
            color="#2ca02c",
            alpha=0.85,
            edgecolor="white",
        )

        ax.axhline(0, color="black", linewidth=0.8, linestyle="--", alpha=0.5)
        ax.yaxis.set_major_formatter(mtick.PercentFormatter(xmax=1, decimals=0))
        ax.set_xticks(list(x))
        ax.set_xticklabels(sectors, rotation=35, ha="right", fontsize=9)
        ax.set_ylabel("Total Return", fontsize=11)
        ax.set_title("Sector Performance: 2022 Bear Market vs 2023–2024 Recovery", fontsize=13, fontweight="bold", pad=15)
        ax.legend(fontsize=10)
        plt.tight_layout()

    save_chart("bear_vs_recovery_bar.png")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    log.info("=" * 55)
    log.info("S&P 500 Sector Analysis — visualize.py")
    log.info("=" * 55)

    make_dirs()

    # Load tables
    returns   = load("sector_annual_returns.csv")
    vol       = load("sector_volatility.csv")
    bear_rec  = load("bear_vs_recovery.csv")

    # Generate charts
    chart_sector_returns_bar(returns)
    chart_returns_heatmap(returns)
    chart_risk_reward_scatter(vol, returns)
    chart_bear_vs_recovery(bear_rec)

    log.info("=" * 55)
    log.info("visualize.py complete. Charts saved to outputs/charts/")
    log.info("Pipeline complete! Check outputs/ for all results.")
    log.info("=" * 55)


if __name__ == "__main__":
    main()
