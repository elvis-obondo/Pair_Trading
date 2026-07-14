import sys
import os
from random import randint
sys.path.insert(0, os.path.dirname(__file__))

import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from data_loader import get_price_levels
from pair_analysis import analyze_top_pairs, compute_spread, get_tradeable_pairs
from ou_model import fit_ou


def filter_to_30_days(price_data: pd.DataFrame) -> pd.DataFrame:
    cutoff = price_data.index.max() - pd.Timedelta(days=30)
    return price_data[price_data.index >= cutoff]


def compute_zscore_series(price_a: pd.Series, price_b: pd.Series) -> pd.Series:
    common_idx = price_a.index.intersection(price_b.index)
    pa = price_a.loc[common_idx]
    pb = price_b.loc[common_idx]

    spread_arr, _beta, _alpha = compute_spread(pa.values, pb.values)
    spread = pd.Series(spread_arr, index=common_idx)

    spread_mean = spread.mean()
    spread_std  = spread.std()
    zscore      = (spread - spread_mean) / spread_std
    return zscore, spread_mean, spread_std


def plot_all_pairs(tradeable: pd.DataFrame, price_data: pd.DataFrame, output_path: Path):
    n = len(tradeable)
    ncols = 2
    nrows = math.ceil(n / ncols)

    fig, axes = plt.subplots(nrows, ncols, figsize=(16, 4 * nrows))
    axes = np.array(axes).flatten()

    for i, row in enumerate(tradeable.itertuples(index=False)):
        ax = axes[i]
        ticker_a, ticker_b = row.ticker_a, row.ticker_b

        if ticker_a not in price_data.columns or ticker_b not in price_data.columns:
            ax.set_title(f"{ticker_a}/{ticker_b} (data missing)")
            ax.set_visible(False)
            continue

        zscore, spread_mean, spread_std = compute_zscore_series(
            price_data[ticker_a], price_data[ticker_b]
        )

        pair_a = price_data[ticker_a].dropna().values
        pair_b = price_data[ticker_b].dropna().values
        ou     = fit_ou(pair_a, pair_b)
        ou_ok  = not np.isnan(ou.theta)

        x = np.arange(len(zscore))
        ax.plot(x, zscore.values, color="steelblue", linewidth=0.8)

        if ou_ok:
            mu_z = (ou.mu - spread_mean) / spread_std
            ax.axhline(mu_z, color="dimgrey", linewidth=0.8, linestyle="dashed", label="μ")
            
            ax.set_ylabel("Z-Score")

        if ou_ok:
            sigma_stationary = ou.sigma / np.sqrt(2.0 * ou.theta)
            upper_stat_z     = (ou.mu + 2.0 * sigma_stationary - spread_mean) / spread_std
            lower_stat_z     = (ou.mu - 2.0 * sigma_stationary - spread_mean) / spread_std
            ax.axhline(
                upper_stat_z,
                color="orange", linewidth=0.8, linestyle="dashed", alpha=0.7,
            )
            ax.axhline(
                lower_stat_z,
                color="orange", linewidth=0.8, linestyle="dashed", alpha=0.7,
            )

        tick_positions = list(range(0, len(zscore), 24))
        tick_labels = list(range(1, len(tick_positions) + 1))
        ax.set_xticks(tick_positions)
        ax.set_xticklabels(tick_labels)
        ax.set_xlabel("Day (last 30 days)")
        if ou_ok:
            ax.set_title(
                f"{ticker_a}/{ticker_b}"
                f"  [OU overlay: θ={ou.theta:.4f}  σ_stat={sigma_stationary:.4f}]"
            )
        else:
            ax.set_title(f"{ticker_a}/{ticker_b}  [OU fit failed — overlay skipped]")
        ax.set_ylabel("Z-Score")
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right")

    for j in range(i + 1, len(axes)):
        axes[j].set_visible(False)

    plt.suptitle("Spread Z-Scores (30-day, fixed OLS beta)", fontsize=14, y=1.01)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved: {output_path}")


def main():
    summary = analyze_top_pairs()
    tradeable = get_tradeable_pairs(summary)

    if tradeable.empty:
        print("No tradeable pairs — nothing to plot.")
        return

    print(f"\nPlotting {len(tradeable)} tradeable pair(s)...")
    price_data = get_price_levels()
    price_data = filter_to_30_days(price_data)

    output_path = Path(__file__).parent / f"spread_zscores_{randint(0,1000)}_.png"
    plot_all_pairs(tradeable, price_data, output_path)


if __name__ == "__main__":
    main()
