import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from data_loader import get_price_levels
from statsmodels.tsa.stattools import coint
import itertools
import numpy as np
import pandas as pd

BAR_LENGTH = 30  # minutes per bar
BARS_PER_DAY = (24 * 60) // BAR_LENGTH  # 48 at 30-min


def compute_spread(price_a: np.ndarray, price_b: np.ndarray):
    beta, alpha = np.polyfit(price_b, price_a, 1)
    spread = price_a - alpha - beta * price_b
    return spread, beta, alpha


def half_life(spread: np.ndarray) -> float:
    S = np.asarray(spread, dtype=float)
    S = S[np.isfinite(S)]
    if len(S) < 3:
        return np.inf
    lam, _ = np.polyfit(S[:-1], np.diff(S), 1)
    if lam >= 0:
        return np.inf
    return -np.log(2) / lam  # bars


def hurst_exponent(spread: np.ndarray) -> float:
    S = np.asarray(spread, dtype=float)
    S = S[np.isfinite(S)]
    lags = [2, 4, 8, 16, 32, 64, 128, 256]
    if len(S) < 2 * max(lags):
        return np.nan
    variances = [np.var(S[lag:] - S[:-lag]) for lag in lags]
    slope, _ = np.polyfit(np.log(lags), np.log(variances), 1)
    return slope / 2


def rolling_coint(price_a: np.ndarray, price_b: np.ndarray, window: int = 7 * BARS_PER_DAY, stride: int = 7 * BARS_PER_DAY) -> pd.Series:
    pvalues = []
    for i in range(0, len(price_a) - window, stride):
        chunk_a = price_a[i:i + window]
        chunk_b = price_b[i:i + window]
        if not (np.isfinite(chunk_a).all() and np.isfinite(chunk_b).all()):
            continue
        _, pval, _ = coint(chunk_a, chunk_b)
        pvalues.append(pval)
    return pd.Series(pvalues)


def rolling_hedge_ratio(price_a: np.ndarray, price_b: np.ndarray, window: int = 7 * BARS_PER_DAY) -> pd.Series:
    betas = []
    for i in range(len(price_a) - window):
        beta, _ = np.polyfit(price_b[i:i + window], price_a[i:i + window], 1)
        betas.append(beta)
    return pd.Series(betas)


def get_tradeable_pairs(summary: pd.DataFrame) -> pd.DataFrame:
    mask = (
          summary["half_life_hours"].between(0.1 * 24, 2 * 24) &
        (summary["hurst"] < 0.48) &
        (summary["coint_stability"] >= 0.5) &
        (summary["beta_cv"] < 0.4)
    )
    return summary[mask].reset_index(drop=True)



def analyze_top_pairs(top_n: int = 10, window: int = 7 * BARS_PER_DAY, days: int = 30):
    print("Fetching price data...")
    df = get_price_levels()

    cutoff = df.index.max() - pd.Timedelta(days=days)
    df = df[df.index >= cutoff]
    print(f"Using last {days} days of data ({cutoff.date()} → {df.index.max().date()}), {len(df)} bars per pair.")

    spacings = df.index.to_series().diff().dropna().dt.total_seconds() / 60
    median_spacing = spacings.median()
    if abs(median_spacing - BAR_LENGTH) > 1:
        raise RuntimeError(
            f"Loaded data has median bar spacing {median_spacing:.1f}m, expected {BAR_LENGTH}m. "
            f"Check feather files or BAR_LENGTH constant."
        )

    tickers = df.columns.tolist()
    min_bars = days * BARS_PER_DAY // 2  # require at least half the expected bars

    pairs = list(itertools.combinations(tickers, 2))
    print(f"Running cointegration scan on {len(pairs)} pairs (min {min_bars} bars required)...")
    coint_results = []
    for a, b in pairs:
        pair = df[[a,b]].dropna()
        if len(pair) < min_bars:
            continue
        _, pval, _ = coint(pair[a].values, pair[b].values)
        coint_results.append((a, b, pval))

    coint_df = (
        pd.DataFrame(coint_results, columns=["ticker_a", "ticker_b", "p_value"])
        .sort_values("p_value")
        .head(top_n)
        .reset_index(drop=True)
    )

    print(f"\nRunning diagnostics on top {top_n} pairs (rolling window = {window} bars = {window // BARS_PER_DAY}d)...")
    rows = []
    for i, row in coint_df.iterrows():
        a, b, pval = row.ticker_a, row.ticker_b, row.p_value
        print(f"  [{i + 1}/{top_n}] {a}/{b}")
        pair_clean = df[[a, b]].dropna()
        pa, pb = pair_clean[a].values, pair_clean[b].values

        spread, _beta, _alpha = compute_spread(pa, pb)
        hl_bars = half_life(spread)
        H = hurst_exponent(spread)

        roll_beta = rolling_hedge_ratio(pa, pb, window)
        beta_mean = roll_beta.mean()
        beta_std = roll_beta.std()
        beta_cv = beta_std / abs(beta_mean) if beta_mean != 0 else np.inf

        roll_p = rolling_coint(pa, pb, window)
        coint_stability = (roll_p < 0.05).mean()  # fraction of windows that are cointegrated

        rows.append({
            "ticker_a": a,
            "ticker_b": b,
            "p_value": round(pval, 4),
            "half_life_hours": round(hl_bars * BAR_LENGTH / 60, 1) if np.isfinite(hl_bars) else np.inf,
            "hurst": round(H, 3),
            "coint_stability": round(coint_stability, 2),
            "beta_mean": round(beta_mean, 3),
            "beta_cv": round(beta_cv, 3),
        })

    summary = pd.DataFrame(rows)

    print("\n--- Pair Diagnostics ---")
    print(summary.to_string(index=False))


    tradeable = get_tradeable_pairs(summary)
    print()
    if not tradeable.empty:
        print("Tradeable candidates (0.1-2d half-life, H<0.48, stable coint, β_cv<0.4):")
        print(tradeable[["ticker_a", "ticker_b", "half_life_hours", "hurst", "coint_stability", "beta_cv"]].to_string(index=False))
    else:
        print("No pairs pass all tradeable filters.")

    return summary


if __name__ == "__main__":
    analyze_top_pairs(days=30)
