import sys
import os
import json
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
import streamlit as st

from research.data_loader import get_price_levels
from research.pair_analysis import (
    analyze_top_pairs,
    get_tradeable_pairs,
    compute_spread,
    rolling_hedge_ratio,
    rolling_coint,
    BAR_LENGTH,
    BARS_PER_DAY,
)
from research.ou_model import fit_ou, ou_residual_diagnostics, ou_reversion_probability
from research.trade_diagnostics import pre_entry_coint_check, spread_volatility_regime
from research.signal_generator import generate_entry_signal

TRADE_LOG_PATH = Path(__file__).resolve().parent.parent / "research" / "trade_log_dump.json"

GATE_NAMES = [
    "Gate 1: Cointegration",
    "Gate 2: OU fit",
    "Gate 3: Minimum deviation",
    "Gate 4: Theta significance",
    "Gate 5: Volatility regime",
    "Gate 6: Reversion probability",
]


@st.cache_data(show_spinner="Loading price data...")
def load_price_levels(timeframe: str = "30m") -> pd.DataFrame:
    return get_price_levels(timeframe=timeframe)


@st.cache_data(show_spinner="Screening pairs — running cointegration tests on every combination...")
def run_screen(top_n: int, window_days: int, lookback_days: int) -> pd.DataFrame:
    window_bars = window_days * BARS_PER_DAY
    return analyze_top_pairs(top_n=top_n, window=window_bars, days=lookback_days)


def tradeable_mask(summary: pd.DataFrame) -> pd.Series:
    if summary.empty:
        return pd.Series([], dtype=bool)
    tradeable = get_tradeable_pairs(summary)
    tradeable_keys = set(zip(tradeable.ticker_a, tradeable.ticker_b))
    return summary.apply(lambda r: (r.ticker_a, r.ticker_b) in tradeable_keys, axis=1)


@st.cache_data(show_spinner="Fitting spread and OU model...")
def compute_pair_diagnostics(
    price_df: pd.DataFrame, ticker_a: str, ticker_b: str, window_days: int
) -> dict:
    pair = price_df[[ticker_a, ticker_b]].dropna()
    pa, pb = pair[ticker_a].values, pair[ticker_b].values

    spread, beta, alpha = compute_spread(pa, pb)
    spread_mean, spread_std = float(np.mean(spread)), float(np.std(spread))
    zscore = (spread - spread_mean) / spread_std

    ou = fit_ou(pa, pb)
    diag = ou_residual_diagnostics(pa, pb)

    window_bars = window_days * BARS_PER_DAY
    n = len(pa)

    roll_beta = rolling_hedge_ratio(pa, pb, window_bars)
    roll_beta_index = pair.index[window_bars : window_bars + len(roll_beta)]

    roll_p = rolling_coint(pa, pb, window=window_bars, stride=window_bars)
    coint_positions = list(range(0, n - window_bars, window_bars))[: len(roll_p)]
    roll_p_index = [pair.index[i + window_bars - 1] for i in coint_positions]

    return {
        "index": pair.index,
        "price_a": pa,
        "price_b": pb,
        "spread": spread,
        "spread_mean": spread_mean,
        "spread_std": spread_std,
        "zscore": zscore,
        "beta": beta,
        "alpha": alpha,
        "ou": ou,
        "diag": diag,
        "roll_beta": roll_beta,
        "roll_beta_index": roll_beta_index,
        "roll_p": roll_p,
        "roll_p_index": roll_p_index,
    }


def evaluate_gates(
    price_a: np.ndarray,
    price_b: np.ndarray,
    coint_p_threshold: float = 0.10,
    regime_threshold: float = 1.1,
    prob_threshold: float = 0.67,
    theta_p_threshold: float = 0.05,
    f: float = 0.20,
    min_deviation_sigma: float = 1.0,
) -> list[dict]:
    """Evaluate every gate from signal_generator.generate_entry_signal, without the
    short-circuit, so all six can be displayed at once. Same primitives, same order,
    same math as the authoritative function — this is a display-only re-derivation."""
    gates = []
    spread_arr, beta, alpha = compute_spread(price_a, price_b)
    S = np.asarray(spread_arr, dtype=float)
    S = S[np.isfinite(S)]
    if len(S) < 3:
        return [{"name": name, "passed": False, "detail": "insufficient data"} for name in GATE_NAMES]
    S0 = float(S[-1])

    coint_p = pre_entry_coint_check(price_a, price_b)
    g1 = not np.isnan(coint_p) and coint_p <= coint_p_threshold
    gates.append({
        "name": GATE_NAMES[0], "passed": g1,
        "detail": f"p={coint_p:.4f} (need <= {coint_p_threshold})" if not np.isnan(coint_p) else "p=nan (insufficient window)",
    })

    params = fit_ou(price_a, price_b)
    g2 = not np.isnan(params.theta)
    gates.append({
        "name": GATE_NAMES[1], "passed": g2,
        "detail": f"theta={params.theta:.4f}/bar" if g2 else "fit failed (theta<=0 or insufficient data)",
    })
    if not g2:
        for name in GATE_NAMES[2:]:
            gates.append({"name": name, "passed": False, "detail": "skipped — no OU fit"})
        return gates

    sigma_stationary = params.sigma / np.sqrt(2.0 * params.theta)
    deviation = abs(S0 - params.mu)
    g3 = deviation >= min_deviation_sigma * sigma_stationary
    gates.append({
        "name": GATE_NAMES[2], "passed": g3,
        "detail": f"{deviation / sigma_stationary:.2f}σ from μ (need >= {min_deviation_sigma}σ)",
    })

    diag = ou_residual_diagnostics(price_a, price_b)
    g4 = not np.isnan(diag.theta_p) and diag.theta_p <= theta_p_threshold
    gates.append({
        "name": GATE_NAMES[3], "passed": g4,
        "detail": f"theta_p={diag.theta_p:.4f} (need <= {theta_p_threshold})" if not np.isnan(diag.theta_p) else "nan",
    })

    regime = spread_volatility_regime(S, params.sigma)
    g5 = not np.isnan(regime) and regime <= regime_threshold
    gates.append({
        "name": GATE_NAMES[4], "passed": g5,
        "detail": f"log-ratio={regime:.3f} (need <= {regime_threshold})" if not np.isnan(regime) else "nan (insufficient window)",
    })

    tau = np.log(1.0 / f) / params.theta
    prob = ou_reversion_probability(S0, params.theta, params.mu, params.sigma, tau)
    g6 = not np.isnan(prob) and prob >= prob_threshold
    gates.append({
        "name": GATE_NAMES[5], "passed": g6,
        "detail": f"P={prob:.3f} (need >= {prob_threshold})" if not np.isnan(prob) else "nan",
    })

    return gates


@st.cache_data(show_spinner=False)
def load_trade_log() -> pd.DataFrame:
    if not TRADE_LOG_PATH.exists():
        return pd.DataFrame()
    with open(TRADE_LOG_PATH) as f:
        trades = json.load(f)
    df = pd.DataFrame(trades)
    if df.empty:
        return df
    df["entry_time"] = pd.to_datetime(df["entry_time"])
    df["exit_time"] = pd.to_datetime(df["exit_time"])
    df["cumulative_pnl"] = df["realized_pnl_net"].cumsum()
    return df
