"""HL-FLOW1: the population, split and measures every part shares. One definition.

Population = the dislocations whose 1-minute window (minutes 0..600 after the
entry close) is finite for both legs: reachmu.stage_paths writes their row
positions (into disloc_meta) to reach_paths.npz along with the target `reach`
(depth >= |z_at_entry| on 1-minute closes, mu frozen at entry, no stop, 10h) and
`chance` (the same path's 1-minute steps with random signs, 50 seeds).

Split (hl3_split.py, from the meta's day column only): CUT 2026-05-25; validation
= the last 20% of the fit days; HO1 / HO2 = held-out days up to / after
envelope.HO_BOUNDARY (2026-08-15).

Measures, all on a held-out HALF, ranked within the half:
  flag80   share of episodes flagged to catch 80% of the half's reverters (lower is better)
  top20    hit rate of the top-20% by score (higher is better)
  gap80    reach rate - mean chance probability over the episodes flagged at 80% catch
  gap20    the same over the top 20%
Intervals are day-clustered (envelope.day_boot, 300 resamples), ranks recomputed in
each resample.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd

import harness, paths
from envelope import HO_BOUNDARY, day_boot
from reachmu import PATHS_OUT, flag_share, top_set

CATCH = (0.5, 0.8, 0.9)
TOP = 0.2


class Pop:
    """The matched population with its split, halves and bootstrap sets."""

    def __init__(self):
        z = np.load(paths.DISLOC)
        self.Y = z["outcomes"].astype(np.float64)
        self.W = z["windows"]
        self.meta_all = pd.read_parquet(paths.META)
        PZ = np.load(PATHS_OUT)
        self.rows = PZ["rows"]
        self.y = PZ["reach"].astype(int)
        self.chance = PZ["chance"].astype(float)
        self.meta = self.meta_all.iloc[self.rows].reset_index(drop=True)
        self.day = self.meta.day.to_numpy()
        self.e = self.Y[self.rows, 0]
        self.sp = harness.Split(self.day, self.e)
        self.tr, self.va, self.te = self.sp.train, self.sp.val, self.sp.test
        h1 = self.te & (self.day < HO_BOUNDARY)
        h2 = self.te & (self.day >= HO_BOUNDARY)
        self.halves = {"HO1": np.flatnonzero(h1), "HO2": np.flatnonzero(h2)}
        self.hboot = {hn: day_boot(self.day[ix]) for hn, ix in self.halves.items()}
        self.n = len(self.rows)

    def band(self):
        """|z_at_entry| band label per row: < 2, 2-3, >= 3."""
        a = np.abs(self.e)
        return np.where(a < 2, "<2", np.where(a < 3, "2-3", ">=3"))


def measure(kind, score, y, chance):
    """One measure on one set of rows (a half, or a bootstrap resample of it)."""
    if kind == "flag80":
        return flag_share(score, y, 0.8)[0]
    if kind == "top20":
        return float(y[top_set(score, TOP)].mean())
    if kind == "gap80":
        ix = flag_share(score, y, 0.8)[2]
        return float(y[ix].mean() - chance[ix].mean())
    if kind == "gap20":
        ix = top_set(score, TOP)
        return float(y[ix].mean() - chance[ix].mean())
    raise ValueError(kind)


def half_measure(P, kind, score, hn):
    """(point, lo, hi) of `kind` for scores on the whole population, in half hn."""
    ix = P.halves[hn]
    s, y, c = score[ix], P.y[ix], P.chance[ix]
    pt = measure(kind, s, y, c)
    dr = [measure(kind, s[b], y[b], c[b]) for b in P.hboot[hn]]
    return pt, *np.percentile(dr, [2.5, 97.5])


def paired_measure(P, kind, sa, sb, hn):
    """(point, lo, hi) of measure(A) - measure(B) in half hn, same resamples."""
    ix = P.halves[hn]
    a, b_, y, c = sa[ix], sb[ix], P.y[ix], P.chance[ix]
    pt = measure(kind, a, y, c) - measure(kind, b_, y, c)
    dr = [measure(kind, a[b], y[b], c[b]) - measure(kind, b_[b], y[b], c[b]) for b in P.hboot[hn]]
    return pt, *np.percentile(dr, [2.5, 97.5])
