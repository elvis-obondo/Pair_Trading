"""Mean-reversion speed for every 3-sigma candidate, on the two-year panel.

The ranking rule in the settled spec is "take the fastest-reverting candidates",
and theta is the only feature that survived testing: it is the one that
correlates positively with per-trade outcome (+0.189), where ranking by spread
volatility correlates with the payoff SCALER instead and carries 32% ruin.

Why this is a separate, cheap job rather than a rerun of entry_gates_dataset:
that module also computes the Monte Carlo reversion probability, which was 85%
of its runtime, and the settled spec applies no gates so none of it is needed.
Fitting theta alone on the 154k candidates that clear 3 sigma takes minutes
rather than hours.

Only rows at or above MIN_SIGMA get a fit. Everything below is a trade the
strategy would never open, so fitting it would be work spent on rows that are
filtered out immediately afterwards.
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
PATHS = PROJECT_ROOT / "research" / "exit_sweep_paths.parquet"
OUTPUT = PROJECT_ROOT / "research" / "candidate_theta.parquet"
PARTS = PROJECT_ROOT / "research" / "candidate_theta_parts"

MIN_SIGMA = 3.0
BAR_HOURS = 0.5
SHARD_PAIRS = 400

_PRICES = None


def _init(px):
    global _PRICES
    try:
        os.nice(10)
    except (OSError, AttributeError):
        pass
    _PRICES = px


def _theta_for_pair(a, b, wanted):
    from ou_model import fit_ou_ewma
    from reversion_dataset import ENTRY_WINDOW_BARS

    if a not in _PRICES.columns or b not in _PRICES.columns:
        return []
    sub = _PRICES[[a, b]].dropna()
    if len(sub) < ENTRY_WINDOW_BARS + 1:
        return []
    pa = sub[a].to_numpy(dtype=float)
    pb = sub[b].to_numpy(dtype=float)
    idx = sub.index
    day_end = pd.Series(np.arange(len(pa)), index=idx).groupby(idx.normalize()).last()

    out = []
    for day, t in day_end.items():
        t = int(t)
        if day not in wanted or t < ENTRY_WINDOW_BARS:
            continue
        lo = t - ENTRY_WINDOW_BARS + 1
        wa, wb = pa[lo:t + 1], pb[lo:t + 1]
        row = {"ticker_a": a, "ticker_b": b, "date": day, "theta": np.nan}
        if (np.isfinite(wa).all() and np.isfinite(wb).all()
                and np.ptp(wa) > 0 and np.ptp(wb) > 0):
            try:
                # fit_df=False: the Student-t tail parameter is ~95% of this
                # call's cost and is read nowhere.
                p = fit_ou_ewma(wa, wb, bar_hours=BAR_HOURS, fit_df=False)
                if np.isfinite(p.theta) and p.theta > 0:
                    row["theta"] = float(p.theta)
            except (ValueError, np.linalg.LinAlgError):
                pass
        out.append(row)
    return out


def _run_shard(task):
    sid, jobs = task
    rows = []
    for a, b, wanted in jobs:
        rows.extend(_theta_for_pair(a, b, wanted))
    part = PARTS / f"part_{sid:05d}.parquet"
    df = pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=["ticker_a", "ticker_b", "date", "theta"])
    if len(df):
        df["date"] = pd.to_datetime(df["date"])
    df.to_parquet(part, index=False)
    n = len(rows)
    del rows, df
    gc.collect()
    return sid, n


def main(workers=3):
    from data_loader import get_price_levels
    from pair_analysis import _base_symbol

    t0 = time.time()
    PARTS.mkdir(exist_ok=True)
    p = pd.read_parquet(PATHS, columns=["ticker_a", "ticker_b", "date", "z"])
    p["date"] = pd.to_datetime(p["date"])
    p = p[p["z"].abs() >= MIN_SIGMA]
    print(f"{len(p):,} candidates at >={MIN_SIGMA} sigma")

    jobs = [(a, b, set(g["date"])) for (a, b), g in p.groupby(["ticker_a", "ticker_b"])]
    del p
    gc.collect()

    shards = [(i, jobs[s:s + SHARD_PAIRS])
              for i, s in enumerate(range(0, len(jobs), SHARD_PAIRS))]
    todo = [s for s in shards if not (PARTS / f"part_{s[0]:05d}.parquet").exists()]
    print(f"{len(shards)} shards, {len(todo)} to run, {workers} workers")
    del jobs, shards
    gc.collect()

    if todo:
        px = get_price_levels(align=False)
        px.columns = [_base_symbol(c) for c in px.columns]
        px = px.loc[:, ~px.columns.duplicated()].astype("float32")
        with Pool(workers, initializer=_init, initargs=(px,), maxtasksperchild=4) as pool:
            for k, (sid, n) in enumerate(pool.imap_unordered(_run_shard, todo), 1):
                el = time.time() - t0
                print(f"  shard {sid} ({k}/{len(todo)}) {n} rows {el:.0f}s "
                      f"eta {el/k*(len(todo)-k):.0f}s", flush=True)

    frames = [f for f in (pd.read_parquet(x) for x in sorted(PARTS.glob("part_*.parquet")))
              if len(f)]
    out = pd.concat(frames, ignore_index=True)
    out.to_parquet(OUTPUT, index=False)
    print(f"\nwrote {len(out):,} rows to {OUTPUT} in {time.time()-t0:.0f}s "
          f"({out.theta.notna().mean()*100:.1f}% with a finite theta)")


if __name__ == "__main__":
    main()
