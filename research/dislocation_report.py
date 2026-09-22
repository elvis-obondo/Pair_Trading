"""The dislocation study: what separates the ones that revert from the ones that don't.

READ THE TWO RULES FIRST

1. REVERSION RATE IS NOT THE ANSWER. At a 3-sigma entry and a 0.5-sigma stop a
   full reversion banks ~6R and a stop costs ~1.4R (bar-close overshoot), so
   roughly a 19% reversion rate breaks even. Every gate ever tested on this
   system raised the win rate and lost money -- 15.7% -> 21.6% in e5f494e --
   because it removed the far tail of |z| that the expectation lives in. So
   every table reports mean R next to the rate, and the rate alone never
   decides anything.

2. CONFIDENCE INTERVALS ARE BLOCK-BOOTSTRAPPED BY DAY. Episodes are not
   independent draws: one macro headline dislocates hundreds of pairs in the
   same hour, and a single coin running puts the same leg in 50 pairs at once.
   Resampling rows would divide the standard error by sqrt(207,000) and declare
   everything significant. Resampling DAYS keeps the clustering. This is the
   same lesson as the $626 pair-labelling noise floor: the effective sample
   size is far smaller than the row count.

WHAT THIS CANNOT DO

It has no slots, no theta ranking, no per-ticker cap and no cooldown, so it
describes the POPULATION of dislocations, not the strategy. Per-trade path
analysis has twice ruled a change IN falsely here. Use it to rule features OUT.

    python research/dislocation_report.py
"""
from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import argparse

import numpy as np
import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(PROJECT_ROOT, "research", "dislocations.parquet")
N_BOOT = 400


def block_ci(d: pd.DataFrame, col: str = "r", n_boot: int = N_BOOT,
             seed: int = 0) -> tuple[float, float]:
    """95% CI for the mean of `col`, resampling whole DAYS with replacement.

    A day is the block because that is the scale the clustering lives on: the
    same regime, the same moving coins, the same headline.
    """
    if not len(d):
        return (np.nan, np.nan)
    groups = [g[col].to_numpy() for _, g in d.groupby(d.date.dt.floor("D"))]
    if len(groups) < 3:
        return (np.nan, np.nan)
    rng = np.random.default_rng(seed)
    k = len(groups)
    means = np.empty(n_boot)
    for i in range(n_boot):
        pick = rng.integers(0, k, k)
        means[i] = np.concatenate([groups[j] for j in pick]).mean()
    return tuple(np.percentile(means, [2.5, 97.5]))


def decile_table(d: pd.DataFrame, col: str, q: int = 10, label: str | None = None,
                 boot: bool = True) -> pd.DataFrame:
    """Outcome by quantile bucket of one entry feature."""
    x = d[d[col].notna()].copy()
    if not len(x):
        print(f"\n{col}: no finite values")
        return pd.DataFrame()
    try:
        x["bucket"] = pd.qcut(x[col], q, duplicates="drop")
    except ValueError:
        x["bucket"] = pd.cut(x[col], q)
    rows = []
    for b, g in x.groupby("bucket", observed=True):
        lo, hi = block_ci(g) if boot else (np.nan, np.nan)
        rows.append(dict(bucket=str(b), n=len(g),
                         rev_pct=100 * (g.exit_reason == "take_profit").mean(),
                         stop_pct=100 * (g.exit_reason == "adverse_move").mean(),
                         mean_R=g.r.mean(), med_R=g.r.median(),
                         ci_lo=lo, ci_hi=hi,
                         med_bars=g.bars_held.median()))
    t = pd.DataFrame(rows)
    print(f"\n{'=' * 104}")
    print(f"{label or col}")
    print("=" * 104)
    print(t.to_string(index=False, float_format=lambda v: f"{v:+.3f}"))
    # A feature is only interesting if the extreme buckets differ by more than
    # their own intervals overlap.
    a, b = t.iloc[0], t.iloc[-1]
    sep = (a.ci_hi < b.ci_lo) or (b.ci_hi < a.ci_lo)
    print(f"  bottom bucket {a.mean_R:+.3f}R [{a.ci_lo:+.3f},{a.ci_hi:+.3f}]  "
          f"top bucket {b.mean_R:+.3f}R [{b.ci_lo:+.3f},{b.ci_hi:+.3f}]  "
          f"-> {'SEPARATES' if sep else 'intervals overlap: no separation'}")
    return t


def main(path: str = DATA) -> None:
    d = pd.read_parquet(path)
    d["day"] = d.date.dt.floor("D")
    d["dominance"] = np.maximum(d.leg_a_share, 1 - d.leg_a_share)
    d["abs_beta"] = d.beta.abs()
    d["beta_neg"] = d.beta < 0
    d["revert"] = d.exit_reason == "take_profit"

    print("=" * 104)
    print("DISLOCATION POPULATION")
    print("=" * 104)
    print(f"  episodes              : {len(d):,}")
    print(f"  distinct pairs        : {d.groupby(['ticker_a','ticker_b']).ngroups:,}")
    print(f"  window                : {d.date.min()} -> {d.date.max()}  "
          f"({d.day.nunique()} days)")
    lo, hi = block_ci(d)
    print(f"  mean R                : {d.r.mean():+.4f}  [{lo:+.3f}, {hi:+.3f}] "
          f"day-block 95% CI")
    print(f"  reversion rate        : {100*d.revert.mean():.2f}%")
    print(f"  break-even rate       : {100*(-d[~d.revert].r.mean())/(d[d.revert].r.mean() - d[~d.revert].r.mean()):.2f}%"
          "   <- what the mix needs to clear")
    print()
    g = d.groupby("exit_reason").agg(n=("r", "size"), mean_R=("r", "mean"),
                                     med_R=("r", "median"),
                                     med_bars=("bars_held", "median"))
    g["pct"] = 100 * g.n / len(d)
    print(g.to_string(float_format=lambda v: f"{v:+.3f}"))

    for col, label in [
        ("r2", "FIT QUALITY. r2 of the hedge regression over the 7-day window"),
        ("absz", "DISLOCATION SIZE. |z| at the crossing bar"),
        ("breadth_max", "BREADTH. how many dislocated pairs the busier leg sits in"),
        ("dominance", "LEG DOMINANCE. share of the 3h move contributed by one leg"),
        ("neutrality", "NEUTRALITY. |1-beta|/(1+|beta|); 0 is dollar-neutral"),
        ("sigma", "SPREAD VOLATILITY. 7-day rolling sigma of the spread"),
        ("n_dislocated", "UNIVERSE COUNT. dislocated pairs at that bar"),
        ("abs_beta", "HEDGE SIZE. |beta|"),
    ]:
        decile_table(d, col, label=label)

    print(f"\n{'=' * 104}")
    print("BINARY SPLITS")
    print("=" * 104)
    for name, mask in [("beta < 0 (both legs same side, not a hedge)", d.beta_neg),
                       ("entered ABOVE mu", d.above_mu),
                       ("pair dislocated earlier in the window", d.episode_num > 0)]:
        for val, sub in [(True, d[mask]), (False, d[~mask])]:
            lo, hi = block_ci(sub)
            print(f"  {name:48s} {str(val):5s}  n {len(sub):7,}  "
                  f"rev {100*sub.revert.mean():5.2f}%  "
                  f"R {sub.r.mean():+.3f} [{lo:+.3f},{hi:+.3f}]")

    print(f"\n{'=' * 104}")
    print("PER DAY. mean R and reversion rate, to see how much is regime")
    print("=" * 104)
    pd_ = d.groupby("day").agg(n=("r", "size"), rev_pct=("revert", lambda s: 100 * s.mean()),
                               mean_R=("r", "mean"), med_r2=("r2", "median"),
                               med_breadth=("breadth_max", "median"))
    print(pd_.to_string(float_format=lambda v: f"{v:+.3f}"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=DATA)
    a = ap.parse_args()
    main(a.data)
