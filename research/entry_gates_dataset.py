"""Compute the live entry gates for every candidate row in the reversion dataset.

WHY: exit_sweep_paths.parquet carries only `passing` (gate 1, smoothed
cointegration) and `p_value`. Every sweep run off it therefore measured
"dislocation + cointegration", which is one gate out of six, and any statement
about "the gated strategy" made from it was really a statement about gate 1.

This module fills in the other four so a sweep can vary HOW MANY gates a
candidate must clear, instead of treating gating as a single on/off switch.

The six gates, as generate_entry_signal applies them:

  1 cointegration    pre_entry_coint_check p <= 0.10      -> already stored as `passing`
  2 OU fit           fit_ou_ewma returns finite theta > 0
  3 min deviation    |S0 - mu| >= min_dev * sigma_stationary
  4 theta signif.    ou_residual_diagnostics theta_p <= 0.05
  5 vol regime       spread_volatility_regime <= 1.1
  6 reversion prob   ou_reversion_probability >= 0.60

Gate 3 is stored as a continuous `dev_sigma` rather than a boolean, because the
entry threshold is the thing being swept -- collapsing it to a pass/fail at 1.0
would hard-code the very parameter under test.

MATCHING THE LIVE PATH: the price window handed to each gate is the trailing
ENTRY_WINDOW_BARS (336 bars = 7 days at 30m), which is what run_backtest's
MIN_BARS now feeds the strategy. bar_hours=0.5 throughout. The gates are
evaluated at the last bar of each calendar day, the same sampling point
reversion_dataset.build_pair_rows uses, so rows join on (pair, date) exactly.

NOTE ON SIGMA: gate 3 and the position sizer use sigma_stationary =
sigma / sqrt(2*theta), the long-run OU spread deviation. The `sigma` column
already in exit_sweep_paths is the 7-day rolling sample std of the spread.
They are different quantities and both are stored, unrenamed, so nothing
downstream silently substitutes one for the other.

RUNNING IT ON A SMALL MACHINE

The first version of this file ran 8 workers and accumulated all 661k result
rows as Python dicts in the parent before writing anything. On an 8GB laptop
that is roughly 2GB of interpreter overhead plus a growing multi-hundred-MB
list, and it took the machine down twice, losing every minute of work both
times. The design now assumes the process WILL be killed:

  - work is split into shards of SHARD_PAIRS pairs
  - each finished shard is written to its own parquet under PARTS_DIR and the
    rows are dropped from memory immediately
  - a rerun skips shards whose part file already exists, so a crash costs at
    most one shard
  - workers default to cpu_count//2 and are recycled every few tasks
    (maxtasksperchild) so no worker's memory can creep

Run it as many times as needed; it converges. `--merge` combines the parts.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gc
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).parent.parent
PATHS_PATH = PROJECT_ROOT / "research" / "exit_sweep_paths.parquet"
OUTPUT_PATH = PROJECT_ROOT / "research" / "entry_gates.parquet"
PARTS_DIR = PROJECT_ROOT / "research" / "entry_gates_parts"

BAR_HOURS = 0.5
F_FRAC = 0.20              # signal_generator's f
COINT_P_THRESHOLD = 0.10
THETA_P_THRESHOLD = 0.05
REGIME_THRESHOLD = 1.1
PROB_THRESHOLD = 0.60

# Monte Carlo paths for gate 6. Live uses ou_reversion_probability's default of
# 5000; this dataset uses 1000 deliberately.
#
# Measured on 622 real gate inputs, 1000 vs 5000 paths: mean absolute error in
# the probability 0.0073, max 0.0362, and 0.15% of rows land on the other side
# of the 0.60 threshold. So roughly 1 gate decision in 700 differs from what
# live would have done -- immaterial against the portfolio effects this dataset
# exists to measure.
#
# The reason to take that trade is not speed in the abstract. On this 8GB
# machine the 5000-path array is large enough to hit swap, which made it ~10x
# slower than 2000 paths rather than the 2.5x the path ratio implies, and the
# build could not survive long enough to finish. A dataset that exists at 1000
# paths beats an exact one that never completes.
MC_PATHS = 1000

SHARD_PAIRS = 50           # pairs per checkpoint; small so a crash costs ~30s

_PRICES = None             # per-worker cache


def _init(price_df):
    """Runs once per worker. Deprioritise so the laptop stays usable."""
    global _PRICES
    try:
        os.nice(10)
    except (OSError, AttributeError):
        pass
    _PRICES = price_df


def _gates_for_pair(a, b, wanted):
    """Every requested date for one pair. Returns a list of row dicts.

    Failures are recorded as NaN rather than dropped. A silently missing row
    is survivorship bias -- the MANA/SHIB and NEIRO/PNUT crashes earlier in
    this project removed 2 of 6 pairs from a comparison without warning, and
    the result looked better than it was.
    """
    from ou_model import (fit_ou_ewma, ou_residual_diagnostics,
                          ou_reversion_probability)
    from trade_diagnostics import spread_volatility_regime
    from reversion_dataset import ENTRY_WINDOW_BARS, rolling_beta_alpha

    if a not in _PRICES.columns or b not in _PRICES.columns:
        return []
    sub = _PRICES[[a, b]].dropna()
    if len(sub) < ENTRY_WINDOW_BARS + 1:
        return []

    pa = sub[a].to_numpy(dtype=float)
    pb = sub[b].to_numpy(dtype=float)
    idx = sub.index
    n = len(pa)

    beta, alpha = rolling_beta_alpha(pa, pb, ENTRY_WINDOW_BARS)
    spread_roll = pa - beta * pb - alpha

    day_end = pd.Series(np.arange(n), index=idx).groupby(idx.normalize()).last()
    rng = np.random.default_rng(abs(hash((a, b))) % (2**32))

    out = []
    for day, t in day_end.items():
        t = int(t)
        if day not in wanted or t < ENTRY_WINDOW_BARS:
            continue
        lo = t - ENTRY_WINDOW_BARS + 1
        wa, wb = pa[lo:t + 1], pb[lo:t + 1]
        row = {"ticker_a": a, "ticker_b": b, "date": day,
               "theta": np.nan, "sigma_ou": np.nan, "sigma_stationary": np.nan,
               "dev_sigma": np.nan, "theta_p": np.nan, "regime": np.nan,
               "rev_prob": np.nan}
        if not (np.isfinite(wa).all() and np.isfinite(wb).all()):
            out.append(row)
            continue
        if np.ptp(wa) == 0.0 or np.ptp(wb) == 0.0:
            out.append(row)
            continue

        try:
            # fit_df=False skips the Student-t tail fit, which is ~95% of this
            # call and is not read by any gate: theta, mu, sigma and the
            # residual series come back bit-identical either way.
            p = fit_ou_ewma(wa, wb, bar_hours=BAR_HOURS, fit_df=False)
        except (ValueError, np.linalg.LinAlgError):
            out.append(row)
            continue

        # Gate 2: a non-finite or non-positive theta is not a mean-reverting
        # fit, and every quantity below divides by it.
        if not np.isfinite(p.theta) or p.theta <= 0 or not np.isfinite(p.sigma):
            out.append(row)
            continue

        s0 = float(spread_roll[t])
        sig_stat = float(p.sigma / np.sqrt(2.0 * p.theta))
        row["theta"] = float(p.theta)
        row["sigma_ou"] = float(p.sigma)
        row["sigma_stationary"] = sig_stat
        if sig_stat > 0 and np.isfinite(s0) and np.isfinite(p.mu):
            row["dev_sigma"] = float(abs(s0 - p.mu) / sig_stat)

        try:
            d = ou_residual_diagnostics(wa, wb)
            row["theta_p"] = float(d.theta_p)
        except (ValueError, np.linalg.LinAlgError):
            pass

        # The regime window is the same 7 days the fit saw, matching
        # generate_entry_signal's window_bars for 30m bars.
        row["regime"] = float(spread_volatility_regime(
            spread_roll[lo:t + 1], p.sigma, window=ENTRY_WINDOW_BARS))

        try:
            tau = float(np.log(1.0 / F_FRAC) / p.theta)
            row["rev_prob"] = float(ou_reversion_probability(
                s0, p.theta, p.mu, p.sigma, tau,
                residuals=p.residuals, bar_hours=BAR_HOURS,
                n_paths=MC_PATHS, rng=rng))
        except (ValueError, np.linalg.LinAlgError, ZeroDivisionError):
            pass

        out.append(row)
    return out


def _run_shard(task):
    """One checkpoint unit: a list of pairs, written to its own parquet.

    Returns (shard_id, n_rows). The rows themselves never travel back to the
    parent -- shipping 661k dicts through the pool result queue is what made
    the parent's memory the binding constraint.
    """
    shard_id, jobs = task
    rows = []
    for a, b, wanted in jobs:
        rows.extend(_gates_for_pair(a, b, wanted))
    part = PARTS_DIR / ("part_%05d.parquet" % shard_id)
    if rows:
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        df.to_parquet(part, index=False)
    else:
        # An empty shard still gets a marker so a rerun does not redo it.
        pd.DataFrame(columns=["ticker_a", "ticker_b", "date", "theta",
                              "sigma_ou", "sigma_stationary", "dev_sigma",
                              "theta_p", "regime", "rev_prob"]
                     ).to_parquet(part, index=False)
    n = len(rows)
    del rows
    gc.collect()
    return shard_id, n


def merge(output_path: Path = OUTPUT_PATH) -> pd.DataFrame:
    """Concatenate the shards one at a time, so peak memory is one shard."""
    parts = sorted(PARTS_DIR.glob("part_*.parquet"))
    if not parts:
        raise FileNotFoundError("no shards in %s" % PARTS_DIR)
    frames = [pd.read_parquet(p) for p in parts]
    df = pd.concat(frames, ignore_index=True)
    del frames
    df.to_parquet(output_path, index=False)
    print("merged %d shards -> %d rows -> %s" % (len(parts), len(df), output_path))
    for c in ["theta", "dev_sigma", "theta_p", "regime", "rev_prob"]:
        print("  %-18s finite %5.1f%%" % (c, df[c].notna().mean() * 100))
    return df


def run(workers=None, max_pairs=None, min_absz=None, shard_pairs=SHARD_PAIRS):
    from data_loader import get_price_levels
    from pair_analysis import _base_symbol

    t_start = time.time()
    PARTS_DIR.mkdir(exist_ok=True)

    cols = ["ticker_a", "ticker_b", "date"] + (["z"] if min_absz else [])
    paths = pd.read_parquet(PATHS_PATH, columns=cols)
    paths["date"] = pd.to_datetime(paths["date"])
    if min_absz:
        paths = paths[paths["z"].abs() >= min_absz]

    jobs = [(a, b, set(g["date"]))
            for (a, b), g in paths.groupby(["ticker_a", "ticker_b"])]
    del paths
    gc.collect()
    if max_pairs:
        jobs = jobs[:max_pairs]

    shards = [(i, jobs[s:s + shard_pairs])
              for i, s in enumerate(range(0, len(jobs), shard_pairs))]
    total = len(shards)
    todo = [s for s in shards
            if not (PARTS_DIR / ("part_%05d.parquet" % s[0])).exists()]
    done_already = total - len(todo)
    del jobs, shards
    gc.collect()

    if workers is None:
        # Memory, not cores, is what kills this job: each worker carries its
        # own pandas/statsmodels image. Two fit; four do not.
        workers = max(1, min(2, (os.cpu_count() or 4) // 2))

    print("%d shards of <=%d pairs | %d already done | %d to run | %d workers"
          % (total, shard_pairs, done_already, len(todo), workers))
    if not todo:
        print("nothing to do; merging")
        return merge()

    prices = get_price_levels(align=False)
    prices.columns = [_base_symbol(c) for c in prices.columns]
    prices = prices.loc[:, ~prices.columns.duplicated()]
    prices = prices.astype("float32")   # halves what each worker carries

    n_rows = 0
    with Pool(workers, initializer=_init, initargs=(prices,),
              maxtasksperchild=4) as pool:
        for k, (sid, n) in enumerate(pool.imap_unordered(_run_shard, todo), 1):
            n_rows += n
            el = time.time() - t_start
            print("  shard %d done (%d/%d) %d rows | %.0fs elapsed | eta %.0fs"
                  % (sid, k, len(todo), n, el, el / k * (len(todo) - k)),
                  flush=True)

    print("\n%d new rows in %.0fs" % (n_rows, time.time() - t_start))
    return merge()


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=None,
                    help="default: half the cores, to keep the laptop usable")
    ap.add_argument("--max-pairs", type=int, default=None)
    ap.add_argument("--min-absz", type=float, default=None,
                    help="only compute gates for rows above this |z|")
    ap.add_argument("--shard-pairs", type=int, default=SHARD_PAIRS)
    ap.add_argument("--merge-only", action="store_true")
    a = ap.parse_args()
    if a.merge_only:
        merge()
    else:
        run(a.workers, a.max_pairs, a.min_absz, a.shard_pairs)
