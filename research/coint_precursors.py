"""
Multi-signal backward-trajectory computation for the 87,293 detection events
in research/coint_survival_events.parquet. Exploratory, retrospective-only --
does not touch trade eligibility, discovery, or either trade pool.

For each event and each of four lookback lengths (14, 10, 7, 4 days),
computes a fixed-width daily trajectory for five signals: beta_cv,
half_life, spread_volatility (relative to the event's own eventual
stationary level), EWMA-fitted theta, and funding-rate convergence between
the two legs. 20 trajectory columns total (5 signals x 4 lookback lengths).

Design decisions (confirmed with the user before running):

Fixed-width windows, not expanding (Option A). An expanding window makes
"days before detection" and "estimate reliability" the same axis, which
risks manufacturing an apparent "things stabilize before detection" pattern
that's really just the window growing. Every trace point instead comes from
a window of the SAME width W, so all points have equal statistical footing.
W = floor(lookback_days / 2), matching beta_cv's own sub-window choice --
applied uniformly across all five signals for a given lookback length. Cost:
the earliest (W-1) days of each nominal lookback can't produce a valid
reading (not enough self-contained data before them) and are dropped, not
estimated on thin data. At L=14 this drops 6 of 14 days (43%); at L=4 it
drops 1 of 4 (25%) -- see the conversation this was decided in for the full
tradeoff table against the alternative (W = L/4, less data loss, noisier
individual points).

Self-containment: for lookback length L, EVERYTHING (the beta/alpha freeze,
every trajectory window) uses ONLY data within [detection_date - L days,
detection_date]. Never reaches outside that L-day boundary, and never
reuses a different L's window.

Frozen vs. re-estimated beta:
  - beta_cv: genuinely re-estimated rolling beta (pair_analysis.rolling_hedge_ratio,
    window = W days, one continuous per-bar path over the L-day span), then
    an EXPANDING coefficient-of-variation over that already-equal-footing
    beta path. This is NOT the same flaw as an expanding estimation window --
    every individual beta point is estimated from an identical W-day window;
    only the CV's own sample size grows as more of those already-reliable
    points accumulate. Confirmed as-is, unchanged.
  - half_life / spread_volatility: beta/alpha frozen ONCE per event per
    lookback length, from a compute_spread() fit over the FULL L-day window
    (matching pairs_strategy.py's own live convention: the hedge ratio is
    fixed once and reused, "re-estimating it mid-trade would shift the
    spread baseline"). The resulting single spread series is then sliced
    into fixed-width W-day sub-windows for the trajectory -- one spread
    definition per (event, L), not one per window.
  - theta (EWMA): ou_model.fit_ou_ewma is called FRESH, independently, on
    each W-day price sub-window -- not extracted from one continuous pass
    over the whole L-day span. This matters specifically for EWMA: a single
    continuous pass's early readings would reflect however little state the
    exponential decay has accumulated by that point, silently reintroducing
    the same expanding-window reliability gradient this whole redesign was
    meant to eliminate. Confirmed by direct comparison during development --
    a continuous pass's early-cutoff theta does NOT match a fresh fit on
    just that window. Costs more than a single pass would have (~111ms vs.
    ~5ms per event) but is the only correct way to give every theta point
    equal footing. fit_ou_ewma does its own internal reference beta fit from
    whatever window it's given -- it is not able to accept an externally
    frozen beta, so theta's own internal hedge-ratio reference is
    self-contained to each W-day window, not literally shared with
    half_life/spread_volatility's externally frozen beta.

"Eventual stationary level" (for spread_volatility's denominator): fit_ou
(static, full-sample) on each event's own OBSERVED alive-period --
detection_date through detection_date+survival_days_smoothed for concluded
events, or through last_data_date for still-alive/censored ones. Computed
ONCE per event (independent of lookback length, since it's about the
post-detection period, not the backward trace) and reused across all four
lookback lengths' spread_volatility trajectories.

Funding convergence: |funding_a - funding_b| using the `open` column
(confirmed as the real value field -- close/high/low are always exactly 0
across all 212 tickers, a schema convention not a data defect), both legs
resampled to daily resolution first (native cadence is 4h for 152 tickers,
8h for 60 -- never actually 1h despite the filename -- so daily resampling
is what makes two different-cadence legs comparable at all). Simple daily
values, no windowing concept applies (each day IS one reading), so this
signal is unaffected by the fixed-vs-expanding-window question. RECALL
excluded (near-zero variance, degenerate); AGLD and ONE flagged low-confidence
(9.1% / 34.4% missing periods) via a `funding_quality` column, not silently
dropped.

Output: research/coint_precursors.parquet, one row per event. Checkpointed
every 5,000 events to a temp file (append-only within one run) given the
multi-hour expected runtime -- insurance against losing hours of work to a
late crash, consolidated into the final file at the end.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from data_loader import get_price_levels
from pair_analysis import compute_spread, half_life, rolling_hedge_ratio, BARS_PER_DAY
from ou_model import fit_ou, fit_ou_ewma

PROJECT_ROOT = Path(__file__).parent.parent
EVENTS_PATH = PROJECT_ROOT / "research" / "coint_survival_events.parquet"
OUTPUT_PATH = PROJECT_ROOT / "research" / "coint_precursors.parquet"
CHECKPOINT_PATH = PROJECT_ROOT / "research" / "coint_precursors_checkpoint.parquet"
FUNDING_DIR = PROJECT_ROOT / "user_data" / "data" / "okx" / "futures"

LOOKBACKS = [14, 10, 7, 4]
DEGENERATE_FUNDING_TICKERS = {"RECALL"}
LOW_CONFIDENCE_FUNDING_TICKERS = {"AGLD", "ONE"}
CHECKPOINT_EVERY = 5000


def _sub_window_days(L: int) -> int:
    """W = floor(L/2), floor at 1 day -- matches beta_cv's own choice,
    applied uniformly across all five signals for this lookback length."""
    return max(1, L // 2)


def _load_all_funding_daily() -> dict[str, pd.Series]:
    """Every ticker's funding `open` column, resampled to daily mean, loaded
    once -- avoids 87,293 x 2 individual feather reads. ~212 reads total."""
    out = {}
    for f in sorted(FUNDING_DIR.glob("*-1h-funding_rate.feather")):
        ticker = f.name.split("_USDT_USDT")[0]
        df = pd.read_feather(f)
        if df.empty:
            continue
        df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
        out[ticker] = df.set_index("date")["open"].resample("1D").mean()
    return out


def _beta_cv_trajectory(pa_L: np.ndarray, pb_L: np.ndarray, L: int, W: int) -> np.ndarray:
    """Genuinely re-estimated rolling beta (window=W days), expanding CV over
    that already-equal-footing beta path. Confirmed as-is, unchanged."""
    beta_window = W * BARS_PER_DAY
    if len(pa_L) <= beta_window:
        return np.array([])
    roll_beta = rolling_hedge_ratio(pa_L, pb_L, window=beta_window).to_numpy()
    n_valid = len(roll_beta) // BARS_PER_DAY  # only genuinely distinct daily cuts, no padding/duplication
    out = np.full(n_valid, np.nan)
    for d in range(1, n_valid + 1):
        seg = roll_beta[: d * BARS_PER_DAY]
        m = seg.mean()
        out[d - 1] = (seg.std() / abs(m)) if m != 0 else np.inf
    return out


def _fixed_width_spread_trajectory(spread_L: np.ndarray, L: int, W: int) -> tuple[np.ndarray, np.ndarray]:
    """half_life and raw spread std, both from FIXED W-day windows sliced off
    the one frozen-beta spread series for this (event, L). Returns
    (half_life_trajectory, spread_std_trajectory), chronological (oldest first)."""
    W_bars = W * BARS_PER_DAY
    total_days = len(spread_L) // BARS_PER_DAY
    valid_ends = range(W, total_days + 1)  # day-index (from start of L-day span) of each window's END
    hl_out, std_out = [], []
    for e in valid_ends:
        seg = spread_L[(e - W) * BARS_PER_DAY: e * BARS_PER_DAY]
        if len(seg) >= 3:
            hl_out.append(half_life(seg))
            std_out.append(float(np.std(seg)))
        else:
            hl_out.append(np.nan)
            std_out.append(np.nan)
    return np.array(hl_out), np.array(std_out)


def _theta_trajectory(pa_L: np.ndarray, pb_L: np.ndarray, L: int, W: int) -> np.ndarray:
    """FRESH, independent fit_ou_ewma per fixed W-day window -- not extracted
    from one continuous pass (see module docstring for why that would
    silently reintroduce the expanding-window flaw)."""
    W_bars = W * BARS_PER_DAY
    total_days = len(pa_L) // BARS_PER_DAY
    out = []
    for e in range(W, total_days + 1):
        a_seg = pa_L[(e - W) * BARS_PER_DAY: e * BARS_PER_DAY]
        b_seg = pb_L[(e - W) * BARS_PER_DAY: e * BARS_PER_DAY]
        if len(a_seg) >= 40:  # fit_ou_ewma needs >= 2*min_bars(20)
            out.append(fit_ou_ewma(a_seg, b_seg, bar_hours=0.5).theta)
        else:
            out.append(np.nan)
    return np.array(out)


def _funding_trajectory(
    funding_daily: dict[str, pd.Series], ticker_a: str, ticker_b: str,
    detection_date: pd.Timestamp, L: int,
) -> tuple[np.ndarray, str]:
    """Daily |funding_a - funding_b| for the L days ending at detection_date.
    No windowing concept -- each day is already one reading. Returns
    (trajectory, quality_flag)."""
    if ticker_a in DEGENERATE_FUNDING_TICKERS or ticker_b in DEGENERATE_FUNDING_TICKERS:
        return np.array([]), "excluded_degenerate"
    da = funding_daily.get(ticker_a)
    db = funding_daily.get(ticker_b)
    if da is None or db is None:
        return np.array([]), "missing_ticker"
    end = detection_date.normalize()
    start = end - pd.Timedelta(days=L - 1)
    idx = pd.date_range(start, end, freq="D")
    diff = (da.reindex(idx) - db.reindex(idx)).abs().to_numpy()
    quality = "low_confidence" if (ticker_a in LOW_CONFIDENCE_FUNDING_TICKERS
                                    or ticker_b in LOW_CONFIDENCE_FUNDING_TICKERS) else "ok"
    return diff, quality


def _eventual_stationary_sigma(
    price_a_full: pd.Series, price_b_full: pd.Series,
    detection_date: pd.Timestamp, survival_days_smoothed: int,
    smoothed_still_alive: bool, last_data_date: pd.Timestamp,
) -> float:
    """fit_ou over the event's own observed alive-period, once per event."""
    end = last_data_date if smoothed_still_alive else detection_date + pd.Timedelta(days=survival_days_smoothed)
    window = price_a_full[(price_a_full.index >= detection_date) & (price_a_full.index <= end)]
    window_b = price_b_full[(price_b_full.index >= detection_date) & (price_b_full.index <= end)]
    joint = pd.DataFrame({"a": window, "b": window_b}).dropna()
    if len(joint) < 3:
        return float("nan")
    params = fit_ou(joint["a"].values, joint["b"].values, bar_hours=0.5)
    if not np.isfinite(params.theta) or params.theta <= 0:
        return float("nan")
    return params.sigma / np.sqrt(2.0 * params.theta)


def run(events_path: Path = EVENTS_PATH, output_path: Path = OUTPUT_PATH) -> pd.DataFrame:
    print("[INFO] Loading detection events...")
    events = pd.read_parquet(events_path)
    print(f"[INFO] {len(events)} events")

    print("[INFO] Loading price universe...")
    price_df = get_price_levels(align=False)

    print("[INFO] Loading + resampling all funding files...")
    funding_daily = _load_all_funding_daily()
    print(f"[INFO] {len(funding_daily)} tickers with funding data")

    rows = []
    t_start = time.time()
    progress_step = max(1, len(events) // 100)
    checkpoint_files = []

    for idx, ev in events.iterrows():
        a, b = ev["ticker_a"], ev["ticker_b"]
        detection_date = pd.Timestamp(ev["detection_date"]).normalize()

        if a not in price_df.columns or b not in price_df.columns:
            continue
        pair_full = price_df[[a, b]].dropna()
        if pair_full.empty:
            continue

        sigma_stationary = _eventual_stationary_sigma(
            pair_full[a], pair_full[b], detection_date,
            ev["survival_days_smoothed"], bool(ev["smoothed_still_alive"]), ev["last_data_date"],
        )

        row = {
            "ticker_a": a, "ticker_b": b, "detection_date": detection_date,
            "eventual_stationary_sigma": sigma_stationary,
        }

        for L in LOOKBACKS:
            W = _sub_window_days(L)
            span_bars = L * BARS_PER_DAY
            window_data = pair_full[pair_full.index <= detection_date].tail(span_bars)
            pa_L, pb_L = window_data[a].values, window_data[b].values

            suffix = f"{L}d"
            if len(pa_L) < span_bars:
                # not enough pre-detection history for this lookback length at all
                row[f"beta_cv_trajectory_{suffix}"] = np.array([])
                row[f"half_life_trajectory_{suffix}"] = np.array([])
                row[f"spread_volatility_trajectory_{suffix}"] = np.array([])
                row[f"theta_trajectory_{suffix}"] = np.array([])
                funding_traj, funding_quality = _funding_trajectory(funding_daily, a, b, detection_date, L)
                row[f"funding_convergence_trajectory_{suffix}"] = funding_traj
                row[f"funding_quality_{suffix}"] = funding_quality
                continue

            row[f"beta_cv_trajectory_{suffix}"] = _beta_cv_trajectory(pa_L, pb_L, L, W)

            spread_L, beta_frozen, alpha_frozen = compute_spread(pa_L, pb_L)
            hl_traj, std_traj = _fixed_width_spread_trajectory(spread_L, L, W)
            row[f"half_life_trajectory_{suffix}"] = hl_traj
            row[f"spread_volatility_trajectory_{suffix}"] = (
                std_traj / sigma_stationary if np.isfinite(sigma_stationary) and sigma_stationary > 0
                else np.full(len(std_traj), np.nan)
            )

            row[f"theta_trajectory_{suffix}"] = _theta_trajectory(pa_L, pb_L, L, W)

            funding_traj, funding_quality = _funding_trajectory(funding_daily, a, b, detection_date, L)
            row[f"funding_convergence_trajectory_{suffix}"] = funding_traj
            row[f"funding_quality_{suffix}"] = funding_quality

        rows.append(row)

        if (idx + 1) % progress_step == 0 or (idx + 1) == len(events):
            elapsed = time.time() - t_start
            rate = (idx + 1) / elapsed
            eta_min = (len(events) - idx - 1) / rate / 60 if rate > 0 else float("nan")
            print(f"  [{idx + 1}/{len(events)}] {elapsed:.0f}s elapsed, {rate:.1f} events/s, ETA {eta_min:.1f} min")

        if len(rows) >= CHECKPOINT_EVERY:
            ckpt_path = CHECKPOINT_PATH.with_name(f"{CHECKPOINT_PATH.stem}_{len(checkpoint_files)}.parquet")
            pd.DataFrame(rows).to_parquet(ckpt_path, index=False)
            checkpoint_files.append(ckpt_path)
            print(f"[INFO] Checkpoint written: {ckpt_path} ({len(rows)} rows)")
            rows = []

    if rows:
        ckpt_path = CHECKPOINT_PATH.with_name(f"{CHECKPOINT_PATH.stem}_{len(checkpoint_files)}.parquet")
        pd.DataFrame(rows).to_parquet(ckpt_path, index=False)
        checkpoint_files.append(ckpt_path)

    print(f"[INFO] Consolidating {len(checkpoint_files)} checkpoint files...")
    full = pd.concat([pd.read_parquet(f) for f in checkpoint_files], ignore_index=True)
    full.to_parquet(output_path, index=False)
    for f in checkpoint_files:
        f.unlink()
    print(f"[INFO] Wrote {len(full)} rows to {output_path}")
    return full


if __name__ == "__main__":
    run()
