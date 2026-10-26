"""Describe the envelope: how well do five features describe how FAR the spread
travels, and is that description trustworthy.

    .venv/bin/python research/dislocation_model/envelope.py --target-source 30m
    .venv/bin/python research/dislocation_model/envelope.py --target-source 1m

PURE DESCRIPTION. No research gate, no permutation null, no direction claim, no
strategy. Nothing here says which way a spread goes or what to trade. Direction
is closed on seven independent lines (docs/STATE.md section 3) and this does not
reopen it: MAE and MFE are both magnitudes, and both are measured on every
episode regardless of which way it went.

CALIBRATION GATES SHARPNESS. Pinball is only compared among models that pass
calibration. A model can win on pinball by being wide everywhere -- safe and
useless -- and a model can look calibrated on aggregate while being badly wrong
underneath. That second failure already happened once in this project: the CRPS
work read 0.98x on aggregate while being 1.53x too wide on nine deciles and
1.84x too narrow on the tenth. The sliced coverage section exists so it cannot
happen twice.

The calibration criterion here is an ADMISSIBILITY rule, not a finding gate. It
decides which models get their sharpness compared. It never promotes anything to
a result.

REALIZED-MAGNITUDE SLICING IS A DIAGNOSTIC AND IS NOT COUNTED. Conditioning
coverage on the realized target is mechanically monotone: deciles are sorted by
y, so every decile below the prediction gives coverage 1.0 and every decile above
gives 0.0. Measured on climatology, MAE at 10h, q50, it is exactly
[1, 1, 1, 1, 1, 0.316, 0, 0, 0, 0]. A PERFECTLY calibrated model fails it too, so
counting it toward admissibility would be a criterion rigged to fail. It is
computed and printed, because the shape still shows where a model sits relative
to the outcome; it just cannot gate anything.

The CRPS failure this section guards against sliced by realized post-entry
VOLATILITY -- a quantity distinct from the target -- which is why that one was
informative. The predicted-magnitude decile is the direct equivalent here and it
IS counted.

THE TARGET. Max adverse and max favourable excursion, sign-folded, as RUNNING
extremes over j = 1..k:

    MOVE[:, j] = -(Y[:, j] - Y[:, 0]) * sign(Y[:, 0])     positive = toward mu
    MFE(k) = max over j=1..k of  MOVE[:, j]
    MAE(k) = max over j=1..k of -MOVE[:, j]

Both are non-decreasing in k BY CONSTRUCTION. The real target at 10h can never
be smaller than at 5h. That is a hard constraint, so a model whose PREDICTED
envelope shrinks with horizon has a correctness bug, not a bad fit -- which is
why the monotonicity violation rate is reported as a bug-catcher rather than a
judgment call.

NEITHER IS CLAMPED AT ZERO. The standard trading definition clamps -- MAE =
max(0, worst adverse) -- and that would be wrong here. At k=1 roughly half of
episodes never move adversely at all, so clamping would put ~45% of the mass
exactly at 0 and the 5th and 25th predicted percentiles would both be 0 by
construction, making calibration at the low quantiles meaningless. Unclamped,
a negative MAE reads as "it never went against us; the closest it came was X",
the distribution stays continuous, and the running-max monotonicity still holds.

THIS RUN USES 30-MINUTE CLOSES (when --target-source 30m). The true envelope is
strictly worse than what is measured: the worst point inside a bar is not
observed. CLIMATOLOGY IS BIASED THE SAME WAY, so the comparative skill numbers
should be largely unaffected -- that is an assumption, it is stated rather than
corrected for, and --stage match1m is what tests it.

THE UNDERSTATEMENT IS ABOUT TWICE WHAT THIS PROJECT ASSUMED. The figure carried
here for months was "roughly 0.3 sigma, one-sided". Measured at 10 hours on the
53,757 episodes where minute data exists: MAE +0.681 sigma on a mean of 2.119
(32% larger) and MFE +0.457 on 2.053 (22% larger). On the narrower 9,240-episode
rule-A subset it reads +0.607 and +0.456. So 0.46 to 0.68 sigma, not 0.3. The
quantity is real and large, which is why the matched comparison is worth running.
IGNORE THE 0.5h ROW of that table: at k=1 the 30-minute target is a SINGLE
observation against the minute target's thirty, so the comparison there is
structurally extreme rather than informative.
"""
import argparse
import hashlib
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import warnings

import numpy as np
import pandas as pd
from sklearn.exceptions import ConvergenceWarning
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import QuantileRegressor
from sklearn.neighbors import NearestNeighbors

import harness
import paths
from adapters.hyperliquid_futures import HL_FUTURES_DIR, bar_file

QUANTILES = (0.05, 0.25, 0.50, 0.75, 0.95)
MEDIAN_IX = 2
HORIZONS = (1, 2, 4, 10, 20)
HLABEL = {1: "0.5h", 2: "1h", 4: "2h", 10: "5h", 20: "10h"}
DIRECTIONS = ("MAE", "MFE")

# kNN's neighbour count is TYPED, not tuned. The val block is reserved for
# GBDT's iteration count and is never scored, so there is nowhere legitimate to
# tune this. 200 of ~22,700 training rows is a ~1% local window.
KNN_K = 200

# Admissibility thresholds. Stated here so they are not buried in the code.
SLICE_TOL = 2.0     # inconsistent slices allowed, as a multiple of chance (5%)

# Precision budgets for the two 1-minute structural checks, in float32 ulps at
# the compared magnitude. disloc.npz stores `outcomes` as float32 and |Y| reaches
# 96.1, so the 30-minute reference carries up to ~1e-05 of its own error; both
# checks are assertions about the 1-minute PATH, not about that storage choice,
# so neither can be asserted tighter than the reference it is compared against.
# 8 ulps covers the handful of float32 roundings that accumulate through the
# spread arithmetic without coming anywhere near a real defect: a bar-label
# offset lands at order 0.1, four orders of magnitude clear of this.
REP_ULPS = 8.0
DOM_ULPS = 8.0
# Absolute floor under every ulp budget. np.spacing of a value near ZERO is a
# denormal (1e-45), so a tolerance taken from the magnitude of a near-zero
# quantity is effectively zero and any comparison against it explodes -- the
# dominance ratio read 1.1e+30 before this existed. The 1-minute path is float64
# end to end, so 1e-9 is far above its own noise and far below any real defect.
ULP_FLOOR = 1e-9
RAW_BAR_DIR = str(HL_FUTURES_DIR)     # the Hyperliquid 1m bars (HL-BUILD2)


# ----------------------------------------------------------------- targets
def _assert_monotone(targets, src):
    """The TARGET must be finite and non-decreasing in k. Before any model runs.

    FINITENESS IS CHECKED FIRST, AND THAT ORDER MATTERS. The monotonicity test
    compares with `< -1e-12`, which is False for NaN, so a NaN target slips
    through it silently and flows into every model. On the 1-minute path a fully
    gappy window makes np.nanmax return NaN, so this is the exact failure the
    assertion was written to catch and did not. Finiteness is now asserted
    explicitly rather than inferred from an ordering test.

    Model monotonicity violations are only meaningful if the target itself
    satisfies the constraint. A bug in the running-max construction would
    otherwise be measured against a broken reference and never noticed.
    """
    for d in DIRECTIONS:
        st = np.stack([targets[(d, k)] for k in HORIZONS])
        nbad = int((~np.isfinite(st)).sum())
        if nbad:
            rows = np.unique(np.nonzero(~np.isfinite(st))[1])
            raise SystemExit(
                f"[{src}] NON-FINITE TARGET: {d} has {nbad} NaN/inf values across "
                f"{len(rows)} episodes. On the 1-minute path this means a fully "
                f"gappy window -- np.nanmax of all-NaN is NaN. Nothing is "
                f"forward-filled to hide it; drop those episodes explicitly or "
                f"finish the backfill. Offending rows: {rows[:10]}"
                f"{' ...' if len(rows) > 10 else ''}")
        bad = int((np.diff(st, axis=0) < -1e-12).sum())
        if bad:
            raise SystemExit(
                f"[{src}] TARGET BUG: {d} decreases with horizon on {bad} "
                f"(row, step) pairs. MAE/MFE are running maximums and cannot.")


def build_targets_30m(Y):
    """Running MAE/MFE from the 30-minute outcome grid in disloc.npz."""
    e = Y[:, 0]
    s = np.sign(e)
    s[s == 0] = 1.0
    move = -(Y - e[:, None]) * s[:, None]
    out = {}
    for k in HORIZONS:
        seg = move[:, 1:k + 1]
        out[("MFE", k)] = seg.max(1)
        out[("MAE", k)] = (-seg).max(1)
    _assert_monotone(out, "30m")
    return out, dict(source="30m", note="30-minute closes; true envelope is worse")


# ------------------------------------------------- 1-minute coverage and paths
# The backfill wall. 131 of the 212 instruments in the episode set have their
# 1-minute history begin on one of these two days, and it cannot be pushed back
# -- the exchange does not serve older minutes for them. An instrument NOT at the
# wall has 1-minute history from its own listing, so every episode it appears in
# is measurable.
WALL_STARTS = ("2025-06-26", "2025-06-27")


def scan_1m_coverage(meta, verbose=True):
    """Per-instrument 1-minute span. Reads only the date column, so it is cheap."""
    tick = sorted(set(meta.ticker_a) | set(meta.ticker_b))
    rows = []
    for t in tick:
        f = str(bar_file(t, "1m"))
        if not os.path.exists(f):
            rows.append((t, pd.NaT, pd.NaT, 0))
            continue
        d = pd.read_feather(f, columns=["date"])
        if d.empty:
            rows.append((t, pd.NaT, pd.NaT, 0))
            continue
        ix = pd.to_datetime(d["date"], utc=True).dt.tz_localize(None)
        rows.append((t, ix.min(), ix.max(), len(d)))
    cov = pd.DataFrame(rows, columns=["ticker", "start", "end", "n"]).set_index("ticker")
    if verbose:
        at_wall = cov.start.dt.strftime("%Y-%m-%d").isin(WALL_STARTS)
        print(f"[1m  ] {int(cov.n.gt(0).sum())} of {len(cov)} instruments have a "
              f"1-minute file")
        print(f"[1m  ] {int(at_wall.sum())} begin at the backfill wall "
              f"({'/'.join(WALL_STARTS)}); {int((~at_wall).sum())} reach further back")
    return cov


def select_1m_subset(meta, cov, verbose=True):
    """The matched population: every episode whose 1-minute window exists.

    THREE RULES WERE CONSIDERED AND THE CHOICE MOVED THE SAMPLE BY 6x, so all
    three counts are reported rather than left to be inferred:

      A  neither leg at the backfill wall                     9,240 episodes
      B  each leg's 1-minute history spans the window the
         target needs, [entry+29m, entry+10.5h]              53,757 episodes
      C  both legs' 1-minute history reaches their own
         listing date in the 30-minute panel                  5,240 episodes

    RULE B IS USED. It keeps 5.8x A's episodes, 6.5x its pairs (3,000 against
    462), and -- the part worth most -- all 18,064 held-out rows, which is
    exactly the held-out population the first envelope run scored. That makes
    the 30-minute arm of this comparison sit on the same ground as the published
    numbers instead of on a 46%-held-out, 81-instrument slice. The cost is that
    B truncates the sample to 2025-06-26 onward, losing the pre-wall part of the
    fit block.

    Rule C is what the phrase "reaches their own listing date" literally
    describes; it is stricter than A, not equal to it.

    B IS A SPAN TEST, NOT A PRESENCE TEST, and that was the one thing standing
    in its way. The mask compares each instrument's overall first and last
    minute against the window and never checks the individual minutes inside it,
    so interior gaps are invisible to it -- and A's clean zero-missing-minutes
    result comes from 81 well-backfilled instruments and does not transfer to
    B's 212. So B's gaps were MEASURED before it was adopted, by running the
    path builder and the missing-minute counter over all 53,757 rows: 192
    missing minutes of 32,307,957 (0.0006%), 53,750 of 53,757 episodes with none
    at all, 7 episodes affected, deepest 41 minutes, none above 60. Trivial, and
    the empty-window abort and the dominance check both pass on it. Had they
    not, A was the fallback.
    """
    nz = cov.n.gt(0)
    at_wall = cov.start.dt.strftime("%Y-%m-%d").isin(WALL_STARTS)
    good = set(cov.index[nz & ~at_wall])
    mask_a = (meta.ticker_a.isin(good) & meta.ticker_b.isin(good)).to_numpy()

    entry = pd.to_datetime(meta.entry_time)
    nmin = max(HORIZONS) * 30
    lo = entry.to_numpy()
    hi = (entry + pd.Timedelta(minutes=29 + nmin)).to_numpy()
    sa = cov.start.reindex(meta.ticker_a.values).to_numpy()
    sb = cov.start.reindex(meta.ticker_b.values).to_numpy()
    ea = cov.end.reindex(meta.ticker_a.values).to_numpy()
    eb = cov.end.reindex(meta.ticker_b.values).to_numpy()
    mask_b = (sa <= lo) & (sb <= lo) & (ea >= hi) & (eb >= hi)

    if verbose:
        day = meta.day.to_numpy()
        print()
        print("  COVERAGE -- three rules, all measured. B is the one used.")
        print(f"  {'rule':<4}{'episodes':>10}{'fit':>9}{'held out':>10}"
              f"{'pairs':>8}{'days':>7}  {'span':<26}")
        for nm, m in (("A", mask_a), ("B", mask_b)):
            sub = meta[m]
            print(f"  {nm:<4}{int(m.sum()):>10,}"
                  f"{int((m & (day < harness.CUT)).sum()):>9,}"
                  f"{int((m & (day >= harness.CUT)).sum()):>10,}"
                  f"{sub.groupby(['ticker_a','ticker_b']).ngroups:>8,}"
                  f"{len(np.unique(day[m])):>7,}  "
                  f"{str(pd.Timestamp(day[m].min()).date())+' .. '+str(pd.Timestamp(day[m].max()).date()):<26}")
        print("  A = neither leg at the backfill wall. REPORTED, NOT USED: 46% of it is")
        print("      held out against 30% of the full set, and its 462 pairs are selected")
        print("      by which instruments got backfilled first.")
        print("  B = each leg's 1-minute history spans the window. USED. All 18,064")
        print("      held-out rows -- exactly the population run 1 scored -- so the")
        print("      30-minute arm sits on the same ground as the published numbers.")
        print("      B is a SPAN test, so its interior gaps were measured, not assumed:")
        print("      192 missing minutes of 32,307,957 (0.0006%), 7 episodes of 53,757")
        print("      affected, deepest 41. Trivial. Both structural checks pass on it.")
        print()
        print()
        print("  SELECTION, measured rather than asserted. Rule B's exclusion is purely")
        print("  TEMPORAL: it drops episodes entered before the backfill wall and keeps")
        print("  every pair, so the cross-section is intact (3,000 of 3,000) and the")
        print(f"  sample starts {pd.Timestamp(meta.day.to_numpy()[mask_b].min()).date()} "
              f"instead of 2024-09-18. That is a milder bias than")
        print("  A's: A is selected by which instruments were backfilled first, B by")
        print("  calendar alone.")
        print("  STILL NOT THE FULL 60,000. The fit block loses its first nine months, so")
        print("  nothing here describes the envelope over the whole history. It answers")
        print("  one question: on the episodes where the measurement can be checked, does")
        print("  the measurement fix matter.")
    return mask_b, mask_a


def load_1m_series(tickers, verbose=True):
    """Dense minute-indexed log-price arrays, one per instrument.

    A dense array plus its first timestamp makes the lookup integer arithmetic
    instead of a pandas reindex per episode -- the previous build did two
    reindexes for each of 60,000 rows. Duplicate minutes resolve to the LAST
    occurrence, matching the `~index.duplicated(keep="last")` the old path used.
    Gaps stay NaN. Nothing is forward filled.

    FLOAT64, AND NOT AS A DEFAULT -- float32 BREAKS BOTH DOWNSTREAM ASSERTIONS.
    The spread divides by meta.sigma, whose minimum is 1.8e-3. float32 carries
    ~1e-7 relative error on a log price of order 1-5, which after that division
    lands at ~3e-4. Measured on the 9,240-episode subset: the reproduction
    assertion read max error 1.451e-04 against its 1e-6 threshold, and the
    dominance check found 2,789 violations as deep as -5.7e-05 against -1e-9.
    Both aborted, and both pointed at the bar-label offset, which was correct.
    The alternative -- loosening both tolerances to ~1e-3 -- would turn the
    dominance check from an exact structural guarantee into a precision floor and
    throw away most of its value. The memory is not worth it: 81 instruments go
    from ~170MB to ~340MB and the episode grid from 44MB to 89MB.
    """
    out = {}
    nbytes = 0
    for t in tickers:
        f = str(bar_file(t, "1m"))
        d = pd.read_feather(f, columns=["date", "close"])
        ix = (pd.to_datetime(d["date"], utc=True).dt.tz_localize(None)
              .to_numpy().astype("datetime64[m]"))
        v = np.log(d["close"].to_numpy(float))
        t0 = ix.min()
        off = ((ix - t0) / np.timedelta64(1, "m")).astype(np.int64)
        arr = np.full(int(off.max()) + 1, np.nan, np.float64)
        arr[off] = v                      # duplicates: last wins
        out[t] = (t0, arr)
        nbytes += arr.nbytes
    if verbose:
        print(f"[1m  ] loaded {len(out)} instruments, {nbytes/1e6:.0f} MB of dense "
              f"float64 minute grids (NaN where a minute did not trade)")
    return out


def _window(arr, off, n):
    """n values from arr at integer offset off, NaN-padded outside the array."""
    out = np.full(n, np.nan)
    lo, hi = max(off, 0), min(off + n, len(arr))
    if hi > lo:
        out[lo - off:hi - off] = arr[lo:hi]
    return out


def one_min_paths(meta, rows, series):
    """The sign-unfolded 1-minute spread path per episode. Shape (len(rows), 601).

    BAR LABELLING, which is the one thing that silently ruins this. Bars are
    labelled by OPEN time. A 30-minute bar labelled T closes at T+30, and the
    1-minute bar that closes at T+30 is the one labelled T+29. So the 30-minute
    close at label T is the 1-minute close at label T+29 -- not T, not T+30. The
    window therefore starts at entry+29m, and column 0 of the result is the
    entry bar's own close, which must equal Y[:, 0].
    """
    nmin = max(HORIZONS) * 30
    entry = pd.to_datetime(meta.entry_time).to_numpy().astype("datetime64[m]")
    beta = meta.beta.to_numpy(float)
    mu = meta.mu.to_numpy(float)
    sig = meta.sigma.to_numpy(float)
    alpha = meta.alpha.to_numpy(float)
    ta = meta.ticker_a.to_numpy()
    tb = meta.ticker_b.to_numpy()
    P = np.full((len(rows), nmin + 1), np.nan)
    miss = np.zeros(len(rows), int)
    for j, i in enumerate(rows):
        t0a, aa = series[ta[i]]
        t0b, ab = series[tb[i]]
        start = entry[i] + np.timedelta64(29, "m")
        va = _window(aa, int((start - t0a) / np.timedelta64(1, "m")), nmin + 1)
        vb = _window(ab, int((start - t0b) / np.timedelta64(1, "m")), nmin + 1)
        sp = (va - beta[i] * vb - alpha[i] - mu[i]) / sig[i]
        miss[j] = int(np.isnan(sp).sum())
        P[j] = sp
    return P, miss


def build_targets_1m(Y, meta, rows=None, verbose=True):
    """Running MAE/MFE from 1-MINUTE closes, over `rows` (default: every episode).

    THREE THINGS THIS DOES THAT THE 30-MINUTE PATH DOES NOT, all required:

    1. ASSERTS THE 1-MINUTE PATH REPRODUCES THE 30-MINUTE CLOSES EXACTLY at the
       30-minute marks. If it does not, the two runs are not measuring the same
       episodes and nothing is comparable.
    2. BAR LABELLING. See one_min_paths: the 30-minute close at label T is the
       1-minute close at label T+29.
    3. MISSING MINUTES ARE COUNTED AND REPORTED PER EPISODE, never forward
       filled. A minute where either leg did not trade is not a price anybody
       made, and crediting an excursion to it would invent the very thing this
       run exists to measure.

    `rows` EXISTS BECAUSE THE FULL EPISODE SET IS NOT MEASURABLE. 131 of 212
    instruments have no 1-minute history before the 2025-06-26/27 backfill wall,
    so a whole-population 1-minute run aborts and should. Passing a row subset is
    how the matched comparison gets run on the episodes that can be measured;
    with rows=None the old whole-population behaviour and its abort are intact.
    """
    cov = scan_1m_coverage(meta, verbose=verbose)
    if rows is None:
        rows = np.arange(len(meta))
    rows = np.asarray(rows)
    sub = meta.iloc[rows]

    # coverage, scoped to the rows actually asked for
    nmin = max(HORIZONS) * 30
    entry = pd.to_datetime(sub.entry_time)
    lo = entry.to_numpy()
    hi = (entry + pd.Timedelta(minutes=29 + nmin)).to_numpy()
    sa = cov.start.reindex(sub.ticker_a.values).to_numpy()
    sb = cov.start.reindex(sub.ticker_b.values).to_numpy()
    ea = cov.end.reindex(sub.ticker_a.values).to_numpy()
    eb = cov.end.reindex(sub.ticker_b.values).to_numpy()
    ok = (sa <= lo) & (sb <= lo) & (ea >= hi) & (eb >= hi)
    if not ok.all():
        bad = int((~ok).sum())
        raise SystemExit(
            f"\n[1m  ] ABORT -- {bad:,} of {len(rows):,} requested episodes have no "
            f"1-minute data over\n"
            f"        the window the target reads, [entry+29m, entry+{29+nmin}m].\n"
            f"        earliest 1-minute start across instruments: {cov.start.min()}\n"
            f"        {int(cov.start.dt.strftime('%Y-%m-%d').isin(WALL_STARTS).sum())} "
            f"instruments begin at the backfill wall and cannot be pushed back.\n"
            f"        Pass a `rows` subset that excludes them, or finish the backfill.\n"
            f"        Nothing is forward-filled or interpolated to paper over this.")

    sig_min = float(sub.sigma.min())
    series = load_1m_series(sorted(set(sub.ticker_a) | set(sub.ticker_b)), verbose)
    P, miss = one_min_paths(meta, rows, series)
    Ys = Y[rows]

    # 1. the reproduction assertion, at every 30-minute mark.
    #
    # THE TOLERANCE IS THE STORED REFERENCE'S OWN PRECISION, NOT A ROUND NUMBER.
    # disloc.npz stores `outcomes` as float32 and |Y| reaches 96.1, where float32
    # spacing is 7.6e-06. So the 30-minute closes this is checked against carry
    # up to ~1e-05 of their own error, and the 1-minute path -- float64 end to
    # end -- is MORE precise than its own reference. A fixed 1e-6 threshold was
    # therefore unreachable by construction and aborted at 3.3e-06 on a path that
    # was correct. The tolerance is now per-element: a few float32 ulps at each
    # compared magnitude, so a large z-score is allowed its larger absolute
    # error and a small one is not. A real bar-label offset is of order 0.1 and
    # clears this by four orders of magnitude.
    marks = np.arange(0, nmin + 1, 30)
    rep = P[:, marks]
    fin = np.isfinite(rep) & np.isfinite(Ys)
    ulp = np.spacing(np.abs(Ys).astype(np.float32)).astype(np.float64)
    tol = np.maximum(REP_ULPS * ulp, ULP_FLOOR)
    err = float(np.max(np.abs(rep[fin] - Ys[fin]))) if fin.any() else np.inf
    ratio = (float(np.max(np.abs(rep[fin] - Ys[fin]) / tol[fin]))
             if fin.any() else np.inf)
    if verbose:
        print(f"[1m  ] max |1-minute path - 30-minute close| at the {len(marks)} "
              f"30m marks: {err:.3e}")
        print(f"[1m  ] as a fraction of the stored float32 reference's own "
              f"precision ({REP_ULPS} ulps): {ratio:.3f}  "
              f"({int(fin.sum()):,} comparisons, must be < 1)")
    if not (ratio < 1.0):
        raise SystemExit(
            f"[1m  ] ABORT -- the 1-minute path does not reproduce the 30-minute "
            f"closes.\n"
            f"        max error {err:.3e}, which is {ratio:.2f}x the stored "
            f"reference's own float32\n"
            f"        precision ({REP_ULPS} ulps). THIS IS A REAL DISAGREEMENT, not "
            f"rounding -- rounding\n"
            f"        cannot exceed 1.0 here.\n"
            f"        Two causes, in order of likelihood. (1) THE BAR-LABEL OFFSET: "
            f"a 30m bar labelled T\n"
            f"        closes at the 1m bar labelled T+29, not T and not T+30; an "
            f"offset error shows up\n"
            f"        at order 0.1, i.e. ratio in the thousands. (2) THE MINUTE "
            f"GRID'S DTYPE: float32\n"
            f"        there puts ~3e-4 into the spread because it divides by a "
            f"sigma as small as\n"
            f"        {sig_min:.2e}, and that reads as a ratio near 20. The grid is "
            f"float64 for this reason.")

    if verbose:
        print(f"[1m  ] missing minutes per episode (of {nmin+1}): "
              f"mean {miss.mean():.1f}  p50 {np.percentile(miss, 50):.0f}  "
              f"p95 {np.percentile(miss, 95):.0f}  max {miss.max()}   "
              f"episodes with none: {int((miss == 0).sum()):,} of {len(rows):,}")

    # REFUSE on episodes with no usable minute in the shortest window. nanmax of
    # an all-NaN slice is NaN, and a NaN target passes the ordering test silently.
    short = P[:, 1:HORIZONS[0] * 30 + 1]
    empty = np.flatnonzero((~np.isfinite(short)).all(axis=1))
    if len(empty):
        raise SystemExit(
            f"[1m  ] ABORT -- {len(empty)} episodes have NO finite minute in the "
            f"{HORIZONS[0]*30}-minute window, so their target would be NaN.\n"
            f"        subset rows {empty[:10]}{' ...' if len(empty) > 10 else ''}\n"
            f"        Drop them deliberately or finish the backfill. They are not "
            f"being forward-filled.")

    e = Ys[:, 0]
    s = np.sign(e)
    s[s == 0] = 1.0
    move = -(P - e[:, None]) * s[:, None]
    out = {}
    for k in HORIZONS:
        seg = move[:, 1:k * 30 + 1]
        out[("MFE", k)] = np.nanmax(seg, axis=1)
        out[("MAE", k)] = np.nanmax(-seg, axis=1)
    _assert_monotone(out, "1m")
    return out, dict(source="1m", note="1-minute closes", missing=miss, rows=rows)


def assert_1m_dominates(t30, t1m, Ys, verbose=True):
    """The 1-minute target can never be SMALLER than the 30-minute one.

    The 1-minute window over minutes 1..30k contains the 30-minute marks
    30, 60, ..., 30k, and both targets are maxima over their window. So
    1-minute >= 30-minute for every episode, direction and horizon -- exactly in
    exact arithmetic, and to the precision of the stored float32 `outcomes` the
    30-minute side is built from (see the tolerance comment below). This is the structural check specific to the matched
    design, and it is the one that would catch a bar-label off-by-one that the
    reproduction assertion happened to survive.
    """
    worst = 0.0
    nbad = 0
    worst_ratio = 0.0
    for d in DIRECTIONS:
        for k in HORIZONS:
            diff = t1m[(d, k)] - t30[(d, k)]
            # THE TOLERANCE SCALES WITH THE INPUTS, NOT WITH THE TARGET. The
            # 30-minute target is a MAX OF DIFFERENCES of disloc.npz's float32
            # `outcomes`: max over j of +/-(Y[:,j] - Y[:,0]). Its absolute error
            # is therefore set by the largest |Y| in the window -- which reaches
            # 96 -- and not by the size of the difference, which can be near
            # zero while still carrying that error. Scaling by |t30| instead
            # drove the tolerance to a denormal on small targets and made the
            # reported ratio 1.1e+30. Scaling by max|Y| over j=0..k is the
            # correct bound and is what is used.
            scale = np.max(np.abs(Ys[:, :k + 1]), axis=1)
            ulp = np.spacing(scale.astype(np.float32)).astype(np.float64)
            tol = np.maximum(DOM_ULPS * ulp, ULP_FLOOR)
            nbad += int((diff < -tol).sum())
            worst = min(worst, float(diff.min()))
            worst_ratio = max(worst_ratio, float(np.max(-diff / tol)))
    if verbose:
        print(f"[1m  ] 1-minute >= 30-minute, every episode/direction/horizon: "
              f"{nbad} violations")
        print(f"[1m  ] deepest shortfall {worst:.3e}; as a fraction of the float32 "
              f"reference's precision ({DOM_ULPS} ulps): {worst_ratio:.3f} "
              f"(must be < 1)")
    if nbad:
        raise SystemExit(
            f"[1m  ] ABORT -- the 1-minute target is SMALLER than the 30-minute one "
            f"on {nbad} (episode,\n"
            f"        direction, horizon) triples. Deepest shortfall {worst:.3e}, "
            f"which is {worst_ratio:.2f}x the\n"
            f"        float32 reference's own precision -- rounding cannot exceed "
            f"1.0, so this is real.\n"
            f"        The 1-minute window over minutes 1..30k CONTAINS the marks at "
            f"30, 60, ..., 30k and\n"
            f"        both targets are maxima, so true dominance cannot fail. "
            f"Suspect, in order: the\n"
            f"        bar-label offset (order 0.1, ratio in the thousands), a row "
            f"misalignment between\n"
            f"        the two target dicts, or a float32 minute grid (~3e-4, ratio "
            f"near 20).")


def gap_paired_ci(y30, p30, y1m, p1m, boot):
    """1-minute gap minus 30-minute gap, PAIRED on the same episodes.

    Unlike gap_diff_ci, which differences two disjoint day blocks, this is a
    genuinely paired comparison: identical rows, identical split, identical day
    resamples on both sides. Only the target differs. Negative means the
    1-minute target is better calibrated -- the understatement was hurting.
    """
    q = np.asarray(QUANTILES)

    def _gap(y, p, ix):
        h = (y[:, None] <= p)[ix]
        return 100.0 * np.abs(h.mean(0) - q).mean()

    g30 = 100.0 * np.abs((y30[:, None] <= p30).mean(0) - q).mean()
    g1m = 100.0 * np.abs((y1m[:, None] <= p1m).mean(0) - q).mean()
    draws = np.empty(len(boot))
    for r, ix in enumerate(boot):
        draws[r] = _gap(y1m, p1m, ix) - _gap(y30, p30, ix)
    return (float(g1m - g30), float(np.percentile(draws, 2.5)),
            float(np.percentile(draws, 97.5)))


# ----------------------------------------------------------------- models
def _pinball(y, f, q):
    d = y - f
    return float(np.mean(np.maximum(q * d, (q - 1.0) * d)))


def _pinball_rows(y, pred):
    """Per-episode pinball averaged over the quantiles. Shape (n,).

    Kept row-wise so the ratio against climatology can be bootstrapped without
    refitting anything -- the predictions are already in memory.
    """
    out = np.zeros(len(y))
    for j, q in enumerate(QUANTILES):
        d = y - pred[:, j]
        out += np.maximum(q * d, (q - 1.0) * d)
    return out / len(QUANTILES)


def pinball_ratio(y_test, pred_model, pred_clim, boot):
    """Mean pinball as a fraction of climatology's, with a day-clustered interval.

    EVERY coverage number in this run carries an interval and the sharpness ratio
    is the number that actually gets quoted, so it carries one too. The project
    has already published a +0.2826 that turned out to be a window.

    No refit: both prediction arrays are already stored, so this costs nothing.
    """
    lm = _pinball_rows(y_test, pred_model)
    lc = _pinball_rows(y_test, pred_clim)
    ratio = float(lm.mean() / lc.mean())
    draws = np.empty(len(boot))
    for r, ix in enumerate(boot):
        draws[r] = lm[ix].mean() / lc[ix].mean()
    return ratio, float(np.nanpercentile(draws, 2.5)), float(np.nanpercentile(draws, 97.5))


def fit_climatology(ctx, y, tag=None):
    """Unconditional empirical quantile from the TRAIN block of this population.

    Computed per population, so the trending subset is scored against its own
    unconditional envelope and not the full population's.

    TRAIN, NOT THE WHOLE FIT BLOCK. It used to read ctx["fit"] -- train plus val,
    41,936 rows -- while every model it is the denominator for fits on train
    alone, 22,683 rows. That gave the baseline 84% more data than the models
    benchmarked against it, which makes the sharpness ratio a comparison against
    a stronger baseline than the models were allowed to be. Climatology has no
    iteration count to choose, so it has no legitimate use for val either.
    """
    v = np.quantile(y[ctx["train"]], QUANTILES)
    return np.tile(v, (ctx["n_test"], 1))


LINEAR_FALLBACKS = []   # (pop, direction, k, quantile) cells that needed alpha>0


def fit_linear(ctx, y, tag=None, models=None):
    """QuantileRegressor, one fit per quantile. alpha=0 -- pure quantile
    regression, no shrinkage, because this is description and an L1 penalty
    would bias the envelope toward climatology.

    If this ties QTREE, the relationship is additive and the simplest model wins.

    FEATURES ARE STANDARDISED, AND THAT CHANGES NOTHING ABOUT THE MODEL. For an
    UNPENALISED quantile regression, standardising is an affine
    reparameterisation: the coefficients change, the fitted conditional quantile
    function does not. Verified directly -- raw and standardised give pinball
    0.11550 and 0.11550 on ALL/MAE/k=1/q=0.05. It is done because the raw columns
    span two orders of magnitude (train sd 0.0134 for off_mark against 1.0833 for
    vol_slope) and HiGHS hit "Numerical difficulties" on the raw LP.

    THE FALLBACK IS COUNTED, NOT SILENT. If the unpenalised LP still fails to
    solve, the cell is retried with alpha=1e-8 -- numerically negligible on
    standardised features but enough to make the program solvable -- and the cell
    is appended to LINEAR_FALLBACKS and reported at the end of the run. A
    penalised cell is NOT the same model as an unpenalised one, so it is named
    rather than absorbed.
    """
    Ztr, ytr = ctx["Ztr"], y[ctx["train"]]
    out = np.empty((ctx["n_test"], len(QUANTILES)))
    for j, q in enumerate(QUANTILES):
        m = None
        for al in (0.0, 1e-8, 1e-6, 1e-4):
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("error", ConvergenceWarning)
                    m = QuantileRegressor(quantile=q, alpha=al,
                                          solver="highs").fit(Ztr, ytr)
            except Exception:
                continue
            if al > 0:
                LINEAR_FALLBACKS.append((tag, q, al))
            break
        if m is None:
            raise SystemExit(
                f"[linear] {tag} q={q}: the LP failed at every alpha in "
                f"(0, 1e-8, 1e-6, 1e-4). Not papering over this with a NaN.")
        out[:, j] = m.predict(ctx["Zte"])
        if models is not None:      # importance.py reads the fitted coefficients
            models.append((q, m))
    return out


def fit_qtree(ctx, y, tag=None, models=None):
    """GBDT quantile loss. Every hyperparameter but the loss is harness.TREE,
    frozen -- not tuned per cell. Iteration count chosen on val by pinball, and
    val is never scored.
    """
    ytr, yva = y[ctx["train"]], y[ctx["val"]]
    out = np.empty((ctx["n_test"], len(QUANTILES)))
    for j, q in enumerate(QUANTILES):
        m = HistGradientBoostingRegressor(loss="quantile", quantile=q,
                                          random_state=0, **harness.TREE)
        m.fit(ctx["Xtr"], ytr)
        sv = list(m.staged_predict(ctx["Xva"]))
        best = int(np.argmin([_pinball(yva, p, q) for p in sv]))
        out[:, j] = list(m.staged_predict(ctx["Xte"]))[best]
        if models is not None:      # importance.py re-predicts at `best`
            models.append((q, m, best))
    return out


def fit_knn(ctx, y, tag=None):
    """Empirical quantile of the KNN_K nearest training episodes.

    Features are standardised on train statistics -- mandatory, not optional:
    the five columns differ by two orders of magnitude and an unscaled euclidean
    metric would be off_mark-blind and vol_slope-dominated.

    Catches smooth local structure a tree steps past.
    """
    ytr = y[ctx["train"]]
    nb = ctx["knn"]
    return np.quantile(ytr[nb], QUANTILES, axis=1).T



def fit_cqr(ctx, y, tag=None):
    """Conformalized QTREE as a registry model: fit on train, calibrate on val.

    The same correction --stage cqr measured, made a first-class model so it is
    scored on the same coverage, gap and skill tables as the other four instead
    of only in its own stage. Per cell:

      1. QTREE at the val-chosen iteration, predicting val and held-out
         (qtree_val_test -- the identical, deterministic QTREE fit).
      2. Conformal widths on the (q5, q95) and (q25, q75) pairs from val's
         conformity scores, and the one-sided median shift for q50.
      3. Applied to the held-out predictions; levels re-ordered along q.

    WHAT THE BREAKDOWN ALREADY SAYS ABOUT THIS MODEL, recorded so the scoreboard
    row is read correctly: the whole gap reduction --stage cqr measured came from
    the median shift (99.9% on HO1, 130% on HO2), and the conformal widths
    netted to zero or worse. So this row is effectively "QTREE recentred on
    val". The widths are kept because that is what conformalized quantile
    regression is; removing them would make it a different model.

    ONE DIFFERENCE FROM --stage cqr, small and stated. The stage enforces the
    raw QTREE predictions across all five horizons BEFORE calibrating; a
    registry fit sees one horizon at a time, so here only the q-axis is
    enforced before calibration and the horizon pass happens afterwards with
    every other model's. Horizon enforcement moved 0.16-0.68% of QTREE's
    predictions, so the two versions agree closely but not bit for bit.

    THE SAME LEAK AS THE STAGE. Val chose QTREE's iteration count, so val's
    conformity scores are mildly optimistic and the widths are biased toward
    too narrow. Not a new discipline exception: val is still never scored.
    """
    va, te, _ = qtree_val_test(ctx, y)
    va = np.maximum.accumulate(va, axis=1)
    te = np.maximum.accumulate(te, axis=1)
    yva = y[ctx["val"]]
    widths = [conformal_width(yva, va[:, jl], va[:, jh], a)[0]
              for jl, jh, a in CQR_PAIRS]
    shift = float(np.median(yva - va[:, MEDIAN_IX]))
    out, _ = apply_cqr(te, widths, shift)
    return out

# REGISTRY-CONSOLIDATED, 2026-10-12. The standing registry is three models.
# QTREE and kNN are retired as registry ENTRIES: no stage refits them going
# forward. Their published results stay in NUMBERS.md as record, and their
# cached predictions stay in every cache file (save_cache carries keys it does
# not rewrite), because importance.py, copula.py, vol1m.py, newfeat.py and
# rolling_window.py read them as history. fit_qtree is NOT retired as code: it
# is CQR's internal machinery (CQR = QTREE recentred and widened on val), a
# component rather than a competitor. fit_knn stays as code because the
# historical stages that published kNN numbers must still reproduce them.
MODELS = (
    ("Climatology", fit_climatology),
    ("Linear QR", fit_linear),
    ("CQR", fit_cqr),
)
RETIRED_MODELS = (
    ("QTREE", fit_qtree),
    ("kNN", fit_knn),
)
# The five-model registry as it stood until 2026-10-12, in its published order.
# Only for stages whose published numbers were computed on it and must stay
# reproducible (vol1m.mae_registry, rolling_window). New work uses MODELS.
REGISTRY_UNTIL_2026_10_12 = (
    ("Climatology", fit_climatology),
    ("Linear QR", fit_linear),
    ("QTREE", fit_qtree),
    ("kNN", fit_knn),
    ("CQR", fit_cqr),
)
# Every fitter by name, current or retired: what a cache verifier needs to
# refit any cell it finds, whether or not the model is still in the registry.
ALL_FITTERS = dict(REGISTRY_UNTIL_2026_10_12)
# A PARAMETRIC GEV (FRECHET) ENVELOPE WAS BUILT AND DROPPED, 2026-10-11. Decided,
# not pending; the full record is NUMBERS.md, section "GEV parametric envelope".
# Its one argument -- extreme-value theory licenses Frechet for a running
# maximum -- holds for the CLAMPED excursion, and clamping was rejected for a
# measured reason (54.6% of MAE mass at zero, vacuous low quantiles). The
# unclamped target's lower tail reaches -61 sigma on train, below a Frechet
# floor that every row must clear, so the family fails by construction rather
# than by fit. Without the theory, an unbounded-tail family is just another
# parametric curve, and QTREE and kNN already fit the shape without assuming
# one. IF TAIL MODELLING EVER BECOMES THE QUESTION, the clean version is a
# peaks-over-threshold fit on the UPPER tail only, where the argument applies --
# a separate plan item, not a sixth learner here.


# ------------------------------------------------------- calibration engine
def _ci(samples):
    return (float(np.nanpercentile(samples, 2.5)),
            float(np.nanpercentile(samples, 97.5)))


def agg_coverage(hits, boot):
    """Aggregate coverage per quantile, with a day-clustered 95% interval."""
    pt = hits.mean(0)
    lo = np.empty(hits.shape[1]); hi = np.empty(hits.shape[1])
    draws = np.empty((len(boot), hits.shape[1]))
    for r, ix in enumerate(boot):
        draws[r] = hits[ix].mean(0)
    for j in range(hits.shape[1]):
        lo[j], hi[j] = _ci(draws[:, j])
    return pt, lo, hi


def sliced_coverage(hits, groups, n_groups, boot):
    """Coverage per group per quantile, each with a day-clustered interval.

    Returns (point, lo, hi, n) each shaped (n_groups, n_quantiles) but n (n_groups,).
    """
    nq = hits.shape[1]
    cnt = np.bincount(groups, minlength=n_groups).astype(float)
    pt = np.full((n_groups, nq), np.nan)
    for j in range(nq):
        h = np.bincount(groups, weights=hits[:, j].astype(float), minlength=n_groups)
        pt[:, j] = np.where(cnt > 0, h / np.maximum(cnt, 1), np.nan)
    draws = np.full((len(boot), n_groups, nq), np.nan)
    for r, ix in enumerate(boot):
        g = groups[ix]
        c = np.bincount(g, minlength=n_groups).astype(float)
        for j in range(nq):
            h = np.bincount(g, weights=hits[ix, j].astype(float), minlength=n_groups)
            draws[r, :, j] = np.where(c > 0, h / np.maximum(c, 1), np.nan)
    lo = np.nanpercentile(draws, 2.5, axis=0)
    hi = np.nanpercentile(draws, 97.5, axis=0)
    return pt, lo, hi, cnt


def deciles(v):
    """Decile group ids 0..9 by rank, robust to ties and to constant input."""
    if np.ptp(v) == 0:
        return np.zeros(len(v), int), 1
    edges = np.quantile(v, np.linspace(0, 1, 11)[1:-1])
    return np.clip(np.searchsorted(edges, v, side="right"), 0, 9), 10


# ----------------------------------------------------------------- run
def build_context(mask, X, day, y_entry, verbose=True):
    """Split, standardised features and kNN neighbours for one population.

    harness.Split is reused UNCHANGED, constructed on the population's own rows:
    train = first 80% of its fit days, val = last 20% (iteration count only,
    never scored), held out = after 2026-07-18, touched once. Split by day
    throughout -- episodes share days and move together on market-wide news.
    """
    sub = np.flatnonzero(mask)
    sp = harness.Split(day[sub], y_entry[sub])
    Xs = X[sub]
    mu = Xs[sp.train].mean(0)
    sd = Xs[sp.train].std(0)
    sd[sd == 0] = 1.0
    Z = (Xs - mu) / sd
    nn = NearestNeighbors(n_neighbors=KNN_K).fit(Z[sp.train])
    knn = nn.kneighbors(Z[sp.test], return_distance=False)
    ctx = dict(sub=sub, sp=sp, fit=sp.fit, train=sp.train, val=sp.val, test=sp.test,
               Xtr=Xs[sp.train], Xva=Xs[sp.val], Xte=Xs[sp.test],
               Ztr=Z[sp.train], Zva=Z[sp.val], Zte=Z[sp.test],
               n_test=sp.n_test, knn=knn, day_test=day[sub][sp.test])
    if verbose:
        print(f"       {sp.describe()}")
    return ctx



# ------------------------------------------------- run 2: halves + isotonic
HO_BOUNDARY = np.datetime64("2026-08-15")   # HL-FLOW1: first HO2 day, from hl3_split.py (meta only)


def day_boot(day_sub, seed=5, n_boot=harness.N_BOOT):
    """Day-clustered resamples over an arbitrary row subset.

    Same machinery as harness.Split: resample DAYS with replacement and
    concatenate their rows. Episodes share days and move together on
    market-wide news, so resampling rows would understate every interval.
    """
    du = np.unique(day_sub)
    pos = {d: np.flatnonzero(day_sub == d) for d in du}
    rb = np.random.default_rng(seed)
    return [np.concatenate([pos[d] for d in rb.choice(du, len(du), replace=True)])
            for _ in range(n_boot)]


def coverage_ci(y, pred, boot):
    """Actual coverage at each nominal level, with a day-clustered interval."""
    hits = y[:, None] <= pred
    draws = np.empty((len(boot), hits.shape[1]))
    for r, ix in enumerate(boot):
        draws[r] = hits[ix].mean(0)
    return (hits.mean(0),
            np.percentile(draws, 2.5, axis=0),
            np.percentile(draws, 97.5, axis=0))


def gap_ci(y, pred, boot):
    """Calibration gap: mean |actual - nominal| over the 5 levels, in pp."""
    hits = y[:, None] <= pred
    q = np.asarray(QUANTILES)
    pt = 100.0 * float(np.abs(hits.mean(0) - q).mean())
    draws = np.empty(len(boot))
    for r, ix in enumerate(boot):
        draws[r] = 100.0 * np.abs(hits[ix].mean(0) - q).mean()
    return pt, float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))


def skill_ci(y, pred_m, pred_c, boot):
    """Pinball skill against climatology, in percent. Positive = better.

    100 * (1 - pinball_model / pinball_climatology). Plainly: if you sized a
    decision off this model instead of doing nothing, this is how much it helps.
    """
    lm = _pinball_rows(y, pred_m)
    lc = _pinball_rows(y, pred_c)
    pt = 100.0 * (1.0 - lm.mean() / lc.mean())
    draws = np.empty(len(boot))
    for r, ix in enumerate(boot):
        draws[r] = 100.0 * (1.0 - lm[ix].mean() / lc[ix].mean())
    return pt, float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))


def pit_positions(y, pred):
    """Each episode's empirical position in its OWN predicted distribution.

    Inverts the predicted quantile function at the realised value, linearly
    across the 5 stored levels. Below the predicted 5th percentile returns 0,
    above the 95th returns 1 -- the shape outside the stored range is unknown and
    is not invented.
    """
    lv = np.asarray(QUANTILES, float)
    u = np.empty(len(y))
    for i in range(len(y)):
        u[i] = np.interp(y[i], pred[i], lv, left=0.0, right=1.0)
    return u


def isotonic_map(u_cal, n_grid=199):
    """Nominal level -> empirical coverage, isotonic, fitted on the calibration
    half. Returns (grid, fitted) with fitted non-decreasing.
    """
    grid = np.linspace(0.005, 0.995, n_grid)
    emp = np.array([(u_cal <= g).mean() for g in grid])
    iso = IsotonicRegression(y_min=0.0, y_max=1.0, increasing=True,
                             out_of_bounds="clip")
    return grid, iso.fit_transform(grid, emp)


def apply_isotonic(pred, grid, fitted):
    """Correct predictions using the map fitted on the other half.

    To make the nominal tau-quantile actually cover tau, read the model's own
    quantile function at the level tau' where fitted(tau') = tau. tau' is
    non-decreasing in tau and pred is non-decreasing across levels, so the
    corrected quantiles stay ordered.
    """
    taup = np.interp(np.asarray(QUANTILES, float), fitted, grid)
    lv = np.asarray(QUANTILES, float)
    out = np.empty_like(pred)
    for i in range(len(pred)):
        out[i] = np.interp(taup, lv, pred[i])
    return out, taup


def stage_run2(targets, pops, ctxs, P, full_sp, meta, args, t0):
    """Split the held-out block, test isotonic transfer, reorder the report."""
    nomin = "".join(f"{100*q:>8.1f}" for q in QUANTILES)

    print("=" * 112)
    print("ENVELOPE RUN 2 -- held-out split and isotonic transfer")
    print("=" * 112)
    print("  NO REFIT. Every prediction here is run 1's, loaded from the cache or")
    print("  regenerated deterministically and then cached. No model is retrained, no")
    print("  iteration count is reselected, no hyperparameter is touched.")
    print()
    print("  THE DISCIPLINE BEND, STATED PLAINLY. The held-out block already had its")
    print("  one scoring touch, in run 1. This run goes back into it to test something")
    print("  new: whether the run-1 miscalibration is a stable offset or a moving")
    print("  target. That is a DELIBERATE, STATED EXCEPTION for this diagnostic, not an")
    print("  oversight. It is the second touch. A third needs a better reason than this")
    print("  one, and the recalibration map is fitted on Held Out 1 and tested on Held")
    print("  Out 2 precisely so the transfer claim is not scored on its own fitting set.")
    print()
    print("  WHY NO NEW MODEL TYPES. In run 1, Climatology (zero capacity) and QTREE")
    print("  (the most flexible model in the registry) missed by almost the same amount")
    print("  in the same direction. That is the signature of a timing problem, not a")
    print("  capacity problem, so adding capacity is not the experiment.")
    print()

    halves = {}
    for pop in pops:
        ctx = ctxs[pop]
        dte = ctx["day_test"]
        m1 = dte < HO_BOUNDARY
        halves[pop] = {
            "HO1": (np.flatnonzero(m1), day_boot(dte[m1])),
            "HO2": (np.flatnonzero(~m1), day_boot(dte[~m1])),
        }
        for hn, (ix, _) in halves[pop].items():
            d = dte[ix]
            print(f"  {pop:<9} {hn}: {len(ix):>6,} rows, {len(np.unique(d)):>3} days, "
                  f"{str(d.min())[:10]} -> {str(d.max())[:10]}")
    print()

    # ---------------- STEP 1 ----------------
    print("=" * 112)
    print("STEP 1 -- the same cells re-scored on each half separately")
    print("=" * 112)
    print("  Is the run-1 drift steady across the window, or concentrated in one half?")
    print("  gap  = mean |actual - nominal| over the five levels, percentage points.")
    print("  skill= pinball vs climatology, percent. POSITIVE means it beats doing")
    print("         nothing; negative means doing nothing was better.")
    print("  Every number carries a day-clustered 95% interval.")
    print()

    gaps, skills = {}, {}
    for pop in pops:
        for direction in DIRECTIONS:
            print("-" * 112)
            print(f"  {pop} / {direction}")
            print("-" * 112)
            for mname, _ in MODELS:
                for k in HORIZONS:
                    pred = P[(pop, direction, mname, k)]
                    y = targets[(direction, k)][ctxs[pop]["sub"]][ctxs[pop]["test"]]
                    print(f"  {mname} / {HLABEL[k]}")
                    print(f"    {'nominal':<14}{nomin}")
                    for hn in ("HO1", "HO2"):
                        ix, bt = halves[pop][hn]
                        pt, lo, hi = coverage_ci(y[ix], pred[ix], bt)
                        g = gap_ci(y[ix], pred[ix], bt)
                        sk = skill_ci(y[ix], pred[ix],
                                      P[(pop, direction, "Climatology", k)][ix], bt)
                        gaps[(pop, direction, mname, k, hn)] = g
                        skills[(pop, direction, mname, k, hn)] = sk
                        print(f"    {hn+' actual':<14}"
                              + "".join(f"{100*v:>8.1f}" for v in pt)
                              + f"   gap {g[0]:>5.2f}pp [{g[1]:>4.2f},{g[2]:>4.2f}]"
                              + f"   skill {sk[0]:>+6.2f}% [{sk[1]:>+6.2f},{sk[2]:>+6.2f}]")
            print()

    # ---------------- STEP 2 ----------------
    print("=" * 112)
    print("STEP 2 -- isotonic recalibration, FITTED ON HELD OUT 1, TESTED ON HELD OUT 2")
    print("=" * 112)
    print("  The map is fitted only on HO1 and only ever applied to HO2, so the")
    print("  transfer claim is never scored on its own fitting set.")
    print()
    print("  If the correction closes the gap, the miscalibration is a STABLE OFFSET")
    print("  and a static correction is worth having. If it does not, the")
    print("  miscalibration is still MOVING and no static correction fixes it.")
    print()
    recal_gap = {}
    for pop in pops:
        for direction in DIRECTIONS:
            print("-" * 112)
            print(f"  {pop} / {direction}")
            print("-" * 112)
            for mname, _ in MODELS:
                # one map per (model, direction, horizon), then re-enforce the
                # running-max constraint across horizons on the corrected set
                corr = {}
                for k in HORIZONS:
                    pred = P[(pop, direction, mname, k)]
                    y = targets[(direction, k)][ctxs[pop]["sub"]][ctxs[pop]["test"]]
                    i1, _ = halves[pop]["HO1"]
                    i2, b2 = halves[pop]["HO2"]
                    grid, fitted = isotonic_map(pit_positions(y[i1], pred[i1]))
                    corr[k] = apply_isotonic(pred[i2], grid, fitted)
                stack = np.stack([corr[k][0] for k in HORIZONS])
                s2, _, _ = enforce_two_pass(stack)
                reb = float((s2 != stack).mean())
                for i, k in enumerate(HORIZONS):
                    y = targets[(direction, k)][ctxs[pop]["sub"]][ctxs[pop]["test"]]
                    i2, b2 = halves[pop]["HO2"]
                    before = P[(pop, direction, mname, k)][i2]
                    after = s2[i]
                    gb = gap_ci(y[i2], before, b2)
                    ga = gap_ci(y[i2], after, b2)
                    cb, _, _ = coverage_ci(y[i2], before, b2)
                    ca, _, _ = coverage_ci(y[i2], after, b2)
                    recal_gap[(pop, direction, mname, k)] = (gb, ga)
                    print(f"  {mname} / {HLABEL[k]}      "
                          f"(enforcement moved {100*reb:.3f}% of corrected predictions)")
                    print(f"    {'nominal':<16}{nomin}")
                    print(f"    {'HO2 before':<16}" + "".join(f"{100*v:>8.1f}" for v in cb)
                          + f"   gap {gb[0]:>5.2f}pp [{gb[1]:>4.2f},{gb[2]:>4.2f}]")
                    print(f"    {'HO2 after':<16}" + "".join(f"{100*v:>8.1f}" for v in ca)
                          + f"   gap {ga[0]:>5.2f}pp [{ga[1]:>4.2f},{ga[2]:>4.2f}]"
                          + ("   CLOSED" if ga[2] < gb[1] else
                             "   not closed" if ga[1] > gb[2] else "   indistinguishable"))
            print()

    # ---------------- SUMMARY ----------------
    print("=" * 112)
    print("SUMMARY -- calibration gap in pp, and the isotonic transfer")
    print("=" * 112)
    print(f"  {'population':<10}{'dir':<5}{'model':<13}{'h':>5}"
          f"{'HO1 gap':>10}{'HO2 gap':>10}{'HO2 recal':>11}{'HO1 skill':>11}{'HO2 skill':>11}")
    for pop in pops:
        for direction in DIRECTIONS:
            for mname, _ in MODELS:
                for k in HORIZONS:
                    g1 = gaps[(pop, direction, mname, k, "HO1")][0]
                    g2 = gaps[(pop, direction, mname, k, "HO2")][0]
                    gr = recal_gap[(pop, direction, mname, k)][1][0]
                    s1 = skills[(pop, direction, mname, k, "HO1")][0]
                    s2v = skills[(pop, direction, mname, k, "HO2")][0]
                    print(f"  {pop:<10}{direction:<5}{mname:<13}{HLABEL[k]:>5}"
                          f"{g1:>9.2f} {g2:>9.2f} {gr:>10.2f} {s1:>+10.2f} {s2v:>+10.2f}")
    print()

    # ---------------- APPENDIX ----------------
    print("=" * 112)
    print("APPENDIX -- pass/fail, DEMOTED. Not the headline, and never was useful as one")
    print("=" * 112)
    ncell = len(pops) * len(DIRECTIONS) * len(MODELS) * len(HORIZONS)
    p_pass = 0.95 ** len(QUANTILES)
    print(f"  The same screen as run 1, on the FULL held-out block: all {len(QUANTILES)}")
    print(f"  aggregate quantile intervals must contain their target, and counted slices")
    print(f"  must stay within {SLICE_TOL:g}x the 5% expected by chance.")
    print()
    print(f"  IT IS KEPT FOR CONTINUITY, NOT BECAUSE IT INFORMS ANYTHING. {ncell} cells,")
    print(f"  and {len(QUANTILES)} interval checks at 95% means a PERFECTLY calibrated")
    print(f"  cell clears the aggregate screen only {100*p_pass:.1f}% of the time -- about")
    print(f"  {ncell*(1-p_pass):.0f} of {ncell} cells fail on chance alone. A binary verdict")
    print(f"  built on that cannot separate a 1.8pp gap from a 9pp one, which is exactly")
    print(f"  why the gap and the skill number lead this report instead.")
    print()
    print(f"  {'population':<10}{'dir':<5}{'model':<13}{'h':>5}{'agg':>7}{'slices':>10}{'verdict':>9}")
    npass = 0
    for pop in pops:
        ctx = ctxs[pop]
        boot = ctx["sp"].boot
        dte = ctx["day_test"]
        udays = np.sort(np.unique(dte))
        tchunk = (dte >= udays[len(udays) // 2]).astype(int)
        for direction in DIRECTIONS:
            for mname, _ in MODELS:
                for k in HORIZONS:
                    pred = P[(pop, direction, mname, k)]
                    y = targets[(direction, k)][ctx["sub"]]
                    yte = y[ctx["test"]]
                    hits = yte[:, None] <= pred
                    pt, lo, hi = agg_coverage(hits, boot)
                    agg_ok = all(lo[j] <= QUANTILES[j] <= hi[j]
                                 for j in range(len(QUANTILES)))
                    bad = tot = 0
                    gp, ngp = deciles(pred[:, MEDIAN_IX])
                    for groups, ng in ((gp, ngp), (tchunk, 2)):
                        if ng < 2:
                            continue
                        spt, slo, shi, scnt = sliced_coverage(hits, groups, ng, boot)
                        for gi in range(ng):
                            if scnt[gi] == 0:
                                continue
                            for j, q in enumerate(QUANTILES):
                                tot += 1
                                if not (slo[gi, j] <= q <= shi[gi, j]):
                                    bad += 1
                    ok = agg_ok and bad <= SLICE_TOL * 0.05 * max(tot, 1)
                    npass += int(ok)
                    print(f"  {pop:<10}{direction:<5}{mname:<13}{HLABEL[k]:>5}"
                          f"{'ok' if agg_ok else 'no':>7}{str(bad)+'/'+str(tot):>10}"
                          f"{'PASS' if ok else 'fail':>9}")
    print()
    print(f"  {npass} of {ncell} cells pass. Read the gap and the skill tables above "
          f"instead.")
    print()
    print(f"[{time.time()-t0:.0f}s]  run 2, target source {args.target_source}.  "
          f"No refit. No new model types. Second and stated touch of held out.")
    print("=" * 112)


def stage_match1m(Y, meta, X, fnames, day, y_entry, args, t0):
    """30-minute vs 1-minute target, SAME episodes, same split, same models.

    WHY MATCHED. Comparing a 9,240-row 1-minute result against the existing
    60,000-row 30-minute result would confound two things: the target's bar
    resolution and which episodes are in the sample. Running both target sources
    on the identical rows isolates exactly one variable -- whether removing the
    close-versus-true understatement changes the description.

    THIS SCORES ALREADY-SCORED HELD-OUT EPISODES AGAIN, and that is a deliberate,
    named exception, not an oversight. The first envelope run fitted and scored
    the held-out block. The halves analysis re-read that run's CACHED predictions
    and refitted nothing. This stage fits new models and scores them on the same
    held-out episodes with a different target source, so it is the SECOND
    independent scoring of those rows. There is no unscored block with 1-minute
    coverage, so the measurement question cannot be asked any other way.

    WHICH NUMBERS ARE WHICH, AND THE DISTINCTION IS NOT COSMETIC:

      LEVELS -- the gap, the skill and the coverage columns. These are a THIRD
      look at rows already scored twice. Confirmatory only. Nothing here
      promotes a level to a finding, and a level that disagrees with run 1
      is a reason to distrust this stage, not run 1.

      THE 1m - 30m DIFFERENCE -- gap_paired_ci. This is the NEW measurement and
      it stands on its own. It is a within-row contrast: identical rows,
      identical split, identical day resamples, only the target changing. A
      paired contrast is far more robust to block reuse than a level is,
      because whatever the reuse did to the level it did to both sides of the
      subtraction equally.

    So the headline of this stage is a difference, never a level.
    """
    print("=" * 118)
    print("MATCHED 30-MINUTE vs 1-MINUTE TARGET -- same episodes, same split")
    print("=" * 118)
    print("  THE QUESTION: the 30-minute target reads bar CLOSES, so it never sees the")
    print("  worst point inside a bar. Earlier work put the understatement near 0.3")
    print("  sigma, one-sided. Climatology is biased the same way, which is why the")
    print("  skill numbers were assumed largely unaffected. That was an ASSUMPTION.")
    print("  This stage tests it on the episodes where the minutes exist.")
    print()
    print("  HELD-OUT REUSE, STATED PLAINLY. These held-out episodes were already")
    print("  scored by the first envelope run. The halves analysis reused that run's")
    print("  cached predictions and refitted nothing; this stage fits new models and")
    print("  scores them on the same rows with a different target. That is the SECOND")
    print("  independent scoring of those episodes. It is a deliberate, named")
    print("  exception: there is no unscored block with 1-minute coverage, so the")
    print("  measurement question cannot be asked any other way. Confirmatory only.")
    print()

    cov = scan_1m_coverage(meta, verbose=True)
    mask_used, mask_alt = select_1m_subset(meta, cov, verbose=True)
    rows = np.flatnonzero(mask_used)

    print("=" * 118)
    print(f"POPULATION -- the {len(rows):,}-episode measurable subset, ALL only")
    print("=" * 118)
    print("  NO ALL/TRENDING SPLIT this round, as specified. Trending is a refinement")
    print("  and the question here is whether the measurement fix matters at all; a")
    print("  terciled subset answers a narrower question on a third of the rows. Under")
    print("  rule B thinness is no longer the binding reason -- the sample is 53,757 --")
    print("  but the question still does not need the split.")
    Xs, days, ys = X[rows], day[rows], y_entry[rows]
    ctx = build_context(np.ones(len(rows), bool), Xs, days, ys, verbose=True)
    sp = ctx["sp"]
    print(f"  real counts after filtering: fit {int(sp.fit.sum()):,}  "
          f"train {int(sp.train.sum()):,}  val {int(sp.val.sum()):,}  "
          f"HELD OUT {sp.n_test:,}   held-out days {len(sp.test_days):,}")
    print()

    # ---- both targets, same rows ----
    print("=" * 118)
    print("TARGETS -- built twice on the same rows")
    print("=" * 118)
    T30, _ = build_targets_30m(Y[rows])
    print(f"  30-minute target built on {len(rows):,} rows.")
    T1M, tinfo = build_targets_1m(Y, meta, rows=rows, verbose=True)
    assert_1m_dominates(T30, T1M, Y[rows], verbose=True)
    print()
    print("  THE UNDERSTATEMENT, measured. How much the 1-minute target adds, in sigma.")
    print("  This is the quantity the 30-minute run could not see; if it is small the")
    print("  rest of this table has nothing to find.")
    print(f"  {'dir':<5}{'h':>6}{'mean add':>11}{'p50':>9}{'p95':>9}"
          f"{'mean 30m':>11}{'mean 1m':>10}{'add %':>8}")
    for d in DIRECTIONS:
        for k in HORIZONS:
            a = T1M[(d, k)] - T30[(d, k)]
            m30 = float(np.mean(np.abs(T30[(d, k)])))
            print(f"  {d:<5}{HLABEL[k]:>6}{a.mean():>11.4f}"
                  f"{np.percentile(a, 50):>9.4f}{np.percentile(a, 95):>9.4f}"
                  f"{T30[(d,k)].mean():>11.4f}{T1M[(d,k)].mean():>10.4f}"
                  f"{100*a.mean()/max(m30, 1e-12):>7.1f}%")
    print()

    # ---- fit both, same split, same models. CACHED. ----
    SRC = ("30m", "1m")
    TGT = {"30m": T30, "1m": T1M}
    cache = paths.envelope_preds("match1m")
    FN = ALL_FITTERS
    keys = [(sc, d, mn, k) for sc in SRC for d in DIRECTIONS
            for mn, _ in MODELS for k in HORIZONS]

    def _fit_one(key):
        sc, d, mn, k = key
        return FN[mn](ctx, TGT[sc][(d, k)], f"{sc}/{d}/{HLABEL[k]}")

    fp = cache_fingerprint([rows], flat_targets(TGT), Xs)
    evid = lambda: {"rows": short_hash(rows), "Ztr": short_hash(ctx["Ztr"]),
                    "Zte": short_hash(ctx["Zte"]),
                    "knn_sorted": short_hash(np.sort(ctx["knn"], axis=1)),
                    "knn_raw": short_hash(ctx["knn"]),
                    "train": short_hash(ctx["train"])}
    P, n_loaded, n_fitted, needs_save = load_or_fit(cache, keys, _fit_one, fp,
                                                    evidence=evid)
    print()

    # ---- enforce the hard constraints, exactly as the 30-minute run does ----
    print("=" * 118)
    print("STRUCTURAL CORRECTNESS -- enforced, not gated")
    print("=" * 118)
    print(f"  {'src':<5}{'dir':<5}{'model':<13}{'quantile enforce':>17}"
          f"{'horizon enforce':>19}")
    for sc in SRC:
        for d in DIRECTIONS:
            for mn, _ in MODELS:
                stack = np.stack([P[(sc, d, mn, k)] for k in HORIZONS])
                s2, rate_q, rate_k = enforce_two_pass(stack)
                for i, k in enumerate(HORIZONS):
                    P[(sc, d, mn, k)] = s2[i]
                print(f"  {sc:<5}{d:<5}{mn:<13}{100*rate_q:>16.3f}%{100*rate_k:>18.3f}%")
    print()
    if needs_save:
        carried = save_cache(cache, fp, P, keys)
        print(f"  [CACHE] wrote {os.path.basename(cache)} -- {n_fitted} new cell(s) "
              f"plus {n_loaded} reloaded, all post-enforcement, fingerprinted; "
              f"{carried} retired-model key(s) carried unchanged.")
        print()

    # ---- the report: side by side, same rows ----
    boot = sp.boot
    yte = {s: {dk: TGT[s][dk][sp.test] for dk in TGT[s]} for s in SRC}
    nomin = "".join(f"{100*q:>8.1f}" for q in QUANTILES)

    print("=" * 118)
    print("COVERAGE -- actual, at each nominal level. 30m and 1m on the SAME rows")
    print("=" * 118)
    print(f"  nominal{'':<31}{nomin}")
    for d in DIRECTIONS:
        for k in HORIZONS:
            for mn, _ in MODELS:
                for s in SRC:
                    c, lo, hi = coverage_ci(yte[s][(d, k)], P[(s, d, mn, k)], boot)
                    print(f"  {d:<5}{HLABEL[k]:>5}{mn:<13}{s:>5}   " +
                          "".join(f"{100*v:>8.1f}" for v in c))
    print()

    print("=" * 118)
    print("CALIBRATION GAP -- mean |actual - nominal| over the 5 levels, pp")
    print("=" * 118)
    print("  The headline. 1m-30m is PAIRED: identical rows, identical split,")
    print("  identical day resamples. Negative = the 1-minute target is better")
    print("  calibrated, i.e. the understatement was doing real damage.")
    print()
    print(f"  {'dir':<5}{'h':>6}{'model':<13}{'30m gap':>9}{'[95% CI]':>17}"
          f"{'1m gap':>9}{'[95% CI]':>17}{'1m-30m':>9}{'[95% CI]':>17}{'':>6}")
    better = closed = 0
    ncell = 0
    for d in DIRECTIONS:
        for k in HORIZONS:
            for mn, _ in MODELS:
                g0, l0, h0 = gap_ci(yte["30m"][(d, k)], P[("30m", d, mn, k)], boot)
                g1, l1, h1 = gap_ci(yte["1m"][(d, k)], P[("1m", d, mn, k)], boot)
                dd, dl, dh = gap_paired_ci(yte["30m"][(d, k)], P[("30m", d, mn, k)],
                                           yte["1m"][(d, k)], P[("1m", d, mn, k)], boot)
                ncell += 1
                better += dd < 0
                tag = ""
                if dh < 0:
                    tag = "SHRINKS"; closed += 1
                elif dl > 0:
                    tag = "GROWS"
                print(f"  {d:<5}{HLABEL[k]:>6}{mn:<13}{g0:>9.2f}"
                      f"{f'[{l0:.2f},{h0:.2f}]':>17}{g1:>9.2f}"
                      f"{f'[{l1:.2f},{h1:.2f}]':>17}{dd:>+9.2f}"
                      f"{f'[{dl:+.2f},{dh:+.2f}]':>17}{tag:>9}")
    print()
    print(f"  {ncell} cells. 1-minute gap smaller (point estimate): {better} of {ncell}.")
    print(f"  Interval excludes zero on the better side: {closed} of {ncell}.")
    print("  A point estimate is not a result. The second line is the one that counts.")
    print()
    print("  THE TWO GAP COLUMNS ARE LEVELS and are a THIRD look at rows already")
    print("  scored twice -- confirmatory only. The 1m-30m COLUMN IS THE NEW")
    print("  MEASUREMENT: a within-row contrast on identical rows, split and day")
    print("  resamples, with only the target changing, so whatever the reuse did to")
    print("  the levels it did to both sides of the subtraction equally. Read the")
    print("  difference as the result of this stage and the levels as context.")
    print()

    print("=" * 118)
    print("PINBALL SKILL vs CLIMATOLOGY -- within each target source")
    print("=" * 118)
    print("  LEVELS, confirmatory only -- a third look at twice-scored rows.")
    print("  Each model against the climatology fitted on the SAME target source, so")
    print("  the two columns are each internally consistent. Positive = better than")
    print("  doing nothing. Comparing skill ACROSS sources is comparing two different")
    print("  targets, so the columns are read side by side, not differenced.")
    print()
    print(f"  {'dir':<5}{'h':>6}{'model':<13}{'30m skill %':>13}{'[95% CI]':>19}"
          f"{'1m skill %':>13}{'[95% CI]':>19}")
    for d in DIRECTIONS:
        for k in HORIZONS:
            for mn, _ in MODELS:
                if mn == "Climatology":
                    continue
                out = []
                for s in SRC:
                    out.append(skill_ci(yte[s][(d, k)], P[(s, d, mn, k)],
                                        P[(s, d, "Climatology", k)], boot))
                print(f"  {d:<5}{HLABEL[k]:>6}{mn:<13}"
                      f"{out[0][0]:>+13.2f}{f'[{out[0][1]:+.2f},{out[0][2]:+.2f}]':>19}"
                      f"{out[1][0]:>+13.2f}{f'[{out[1][1]:+.2f},{out[1][2]:+.2f}]':>19}")
    print()
    print(f"  [{time.time()-t0:.0f}s]")
    print("=" * 118)
    print("WHAT THIS DOES AND DOES NOT SETTLE")
    print("=" * 118)
    npair = meta.iloc[rows].groupby(["ticker_a", "ticker_b"]).ngroups
    print(f"  Settles: on these {len(rows):,} episodes, {npair:,} pairs, whether the")
    print("  close-versus-true understatement changes the calibration gap. Same rows,")
    print("  same split, same models, same day resamples on both sides.")
    print(f"  The held-out arm is all {sp.n_test:,} rows the first envelope run scored, so")
    print("  the 30-minute column is directly comparable to the published numbers.")
    print("  Does NOT settle: anything about the full 60,000. The fit block loses its")
    print("  first nine months to the backfill wall, so this describes the envelope over")
    print("  a shorter history. A null here is evidence the fix does not matter ON THESE")
    print("  ROWS, not that the understatement is small -- it is 0.46 to 0.68 sigma at")
    print("  10 hours, twice what this project assumed.")
    print("=" * 118)


# ------------------------------------------------------------- enforcement
def enforce_two_pass(stack):
    """The two hard constraints, in the order every cache was written with.

    stack is (horizons, rows, quantiles). Quantile axis first -- a running max
    makes q5 <= ... <= q95 -- then the horizon axis, which preserves the first
    because a max of non-decreasing functions is non-decreasing. Returns
    (enforced, rate_q, rate_k): the share of predictions each pass MOVED.

    ONE DEFINITION, BECAUSE TWO DIVERGED ONCE. The CQR refit check compared its
    refit against the cache after the quantile pass only, while the cache had
    been written after both. Horizon enforcement had moved 0.16-0.68% of
    QTREE's predictions, so the check disagreed in every QTREE group and would
    have aborted with advice to delete a cache that was correct. Every caller
    that compares against a cache, or writes one, goes through this.
    """
    s1 = np.maximum.accumulate(stack, axis=2)
    rate_q = float((s1 != stack).mean())
    s2 = np.maximum.accumulate(s1, axis=0)
    rate_k = float((s2 != s1).mean())
    return s2, rate_q, rate_k


# ------------------------------------------------------------- fingerprint
FP_KEY = "__fp__"
CHEAP_MODELS = ("Climatology", "kNN", "QTREE")   # deterministic and fast to refit


def short_hash(a):
    """12 hex chars of sha256 over an array's bytes -- evidence, not security.

    Same construction as the six-process determinism test recorded in
    NUMBERS.md (rows d44f98ff9b33, Ztr 5537bd6787e8, Zte c4fb641ffc3f, sorted
    knn eb5efce82982, raw knn 70450c9ef957), so a value printed here can be
    compared against those directly.
    """
    return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()[:12]


def flat_targets(T):
    """{src: {(dir, k): arr}} or {(dir, k): arr} -> one flat dict, for hashing."""
    out = {}
    for a, v in T.items():
        if isinstance(v, dict):
            for b, arr in v.items():
                out[(a,) + tuple(b)] = arr
        else:
            out[tuple(a)] = v
    return out


def cache_fingerprint(rows, targets, X):
    """A hash of everything a cached prediction depends on, except model code.

    Covered: the row indices (one array per population), every target array,
    the feature matrix, harness.TREE, KNN_K, the quantile and horizon sets and
    the split boundaries. NOT covered: the model REGISTRY -- adding a model must
    not invalidate the others, which is what load_or_fit's gap-filling is for --
    and the source code of the fit functions, which no hash of data can see. A
    change to fit_linear's internals is therefore still the caller's job to
    notice. A change to the data under the same row count was not, before this:
    it would have been silently reused for four models while a fifth was fitted
    fresh against the new data.
    """
    h = hashlib.sha256()

    def add(a):
        a = np.ascontiguousarray(a)
        h.update(repr((a.dtype.str, a.shape)).encode())
        h.update(a.tobytes())

    for r in rows:
        add(np.asarray(r))
    for key in sorted(targets, key=repr):
        add(targets[key])
    add(X)
    h.update(repr((sorted(harness.TREE.items()), KNN_K, tuple(QUANTILES),
                   tuple(HORIZONS), str(harness.CUT), harness.VAL_FRAC)).encode())
    return h.hexdigest()


# ------------------------------------------------------------------ cache
def load_or_fit(cache, keys, fit_one, fingerprint, evidence=None, verbose=True):
    """Load cached predictions, fit ONLY what is missing, return the lot.

    Returns (P, n_loaded, n_fitted, needs_save). Keys are tuples ending
    (..., model, horizon).

    ADDING A MODEL TO THE REGISTRY MUST NOT INVALIDATE EVERY EXISTING FIT. The
    previous loader was all-or-nothing, so adding a model would have raised a
    KeyError on every cached run, and the obvious workaround -- delete the cache
    -- would have thrown away 1,232s of Linear QR solves to add one model.

    BUT A CACHE MUST KNOW WHAT IT WAS FITTED ON. Gap-filling alone trusted any
    key it found, so the same rows with different targets or features would
    have been reused for the cached models while a new one was fitted against
    the new data -- a silent mixed-vintage scoreboard. So the cache carries a
    fingerprint (cache_fingerprint) and this refuses to load on a mismatch.

    A LEGACY CACHE -- no fingerprint, written before this existed -- is neither
    trusted blindly nor thrown away. The deterministic, cheap models
    (Climatology, kNN, QTREE) are refitted, put through the same two-pass
    enforcement the cache received, and compared. Between them they depend on
    the rows, the targets, the features and harness.TREE, so an exact match is
    evidence the ground has not moved, and the fingerprint is then stamped.
    Linear QR, the expensive one, is adopted on that evidence rather than
    re-solved. Any mismatch refuses.

    Saving re-writes every key, not only new ones: enforcement is a running
    maximum and therefore idempotent, so an already-clean cell passes through
    unchanged.

    THE VERIFIER LEAVES EVIDENCE, WHETHER IT PASSES OR FAILS. It refused this
    cache twice on 2026-10-11 -- kNN off by 7-9 sigma -- and then matched at
    0.000 in ten later checks on unchanged inputs, with no cause found. The
    failure mode can only produce FALSE REFUSALS: a refit matching the cache at
    0.000 across 60 cells cannot happen by chance if the inputs differ, so a
    pass is proof and a fail is a question. To answer the question next time,
    `evidence` (a callable returning {name: short_hash}) is evaluated BEFORE
    and AFTER the refits -- a change between the two means something mutated
    process state during verification -- and every group's worst disagreement
    is printed, plus the worst cell's row count and first differing row.
    """
    P, present, z = {}, set(), None
    needs_save = False
    if os.path.exists(cache):
        z = np.load(cache, allow_pickle=False)
        present = set(z.files) - {FP_KEY}
        if FP_KEY in z.files:
            stored = str(z[FP_KEY])
            if stored != fingerprint:
                raise SystemExit(
                    f"\n[CACHE] REFUSING {os.path.basename(cache)}: its fingerprint "
                    f"does not match the current inputs.\n"
                    f"        stored {stored[:16]}...   current {fingerprint[:16]}...\n"
                    f"        Something it depends on -- rows, targets, features, "
                    f"harness.TREE, KNN_K,\n"
                    f"        the quantile or horizon set, or the split -- changed "
                    f"since it was written.\n"
                    f"        Reusing it would score models fitted on different data "
                    f"side by side. If the\n"
                    f"        change was intended, delete the file and refit; if not, "
                    f"find it first.")
            if verbose:
                print(f"  cache fingerprint matches ({fingerprint[:16]}...).")
        elif present:
            # Verify on every cheap model the CACHE holds, not only those
            # requested: since REGISTRY-CONSOLIDATED, QTREE and kNN are no longer
            # requested, and Climatology alone does not depend on the features,
            # so it could not catch a feature change. fit_one must resolve
            # retired names (callers pass ALL_FITTERS).
            req = {k[:-1] for k in keys}
            groups = {g for g in req if g[-1] in CHEAP_MODELS}
            for g in req:
                for mn in CHEAP_MODELS:
                    g2 = g[:-1] + (mn,)
                    if all("|".join(str(x) for x in g2 + (h,)) in present
                           for h in HORIZONS):
                        groups.add(g2)
            groups = sorted(groups, key=repr)
            worst, n_cmp, wcell, per_group = 0.0, 0, None, []
            if verbose:
                print(f"  LEGACY CACHE: {os.path.basename(cache)} has no "
                      f"fingerprint. Verifying by refitting")
                print(f"  {', '.join(CHEAP_MODELS)} and comparing after the same "
                      f"two-pass enforcement.")
            ev0 = evidence() if evidence else {}
            if verbose and ev0:
                print("  evidence BEFORE refit: "
                      + "  ".join(f"{k}={v}" for k, v in ev0.items()))
            for g in groups:
                ks = [g + (h,) for h in HORIZONS]
                names = ["|".join(str(x) for x in k) for k in ks]
                if not all(n in present for n in names):
                    continue
                enf, _, _ = enforce_two_pass(np.stack([fit_one(k) for k in ks]))
                gw = 0.0
                for i, n in enumerate(names):
                    dmat = np.abs(enf[i] - z[n])
                    e = float(np.max(dmat))
                    gw = max(gw, e)
                    n_cmp += 1
                    if e > worst:
                        worst = e
                        rowmax = dmat.max(axis=1)
                        r = int(np.argmax(rowmax))
                        wcell = (n, int((rowmax > 1e-12).sum()), r,
                                 enf[i][r].copy(), np.asarray(z[n][r]).copy())
                per_group.append(("/".join(str(x) for x in g), gw))
            ev1 = evidence() if evidence else {}
            if verbose:
                for gname, gw in per_group:
                    print(f"    {gname:<30} worst {gw:.3e}")
                if ev1:
                    print("  evidence AFTER refit:  "
                          + "  ".join(f"{k}={v}" for k, v in ev1.items()))
                    moved = [k for k in ev0 if ev0[k] != ev1.get(k)]
                    print(f"  state changed during verification: "
                          f"{', '.join(moved) if moved else 'nothing'}")
                print(f"  {n_cmp} cells compared, worst |refit - cache| {worst:.3e}")
                if wcell is not None and worst > 1e-12:
                    n, nrows, r, a, b = wcell
                    print(f"  worst cell {n}: {nrows:,} rows differ; first worst "
                          f"row {r}")
                    print(f"    refit {np.array2string(a, precision=4)}")
                    print(f"    cache {np.array2string(b, precision=4)}")
            if n_cmp == 0 or worst > 1e-12:
                why = ("no deterministic cell to verify it against."
                       if n_cmp == 0 else
                       f"the deterministic refit disagrees by {worst:.3e} after "
                       f"the same two-pass\n        enforcement the cache received, "
                       f"so its inputs have changed.")
                raise SystemExit(
                    f"\n[CACHE] REFUSING legacy {os.path.basename(cache)}: {why}\n"
                    f"        Delete it and refit, or find what changed first.")
            if verbose:
                print("  Verified. Adopting it and stamping the fingerprint; Linear "
                      "QR is not re-solved.")
            needs_save = True
        for k in keys:
            name = "|".join(str(x) for x in k)
            if name in present:
                P[k] = z[name]
    missing = [k for k in keys if k not in P]
    if verbose:
        if z is None:
            print(f"  no cache at {os.path.basename(cache)} -- fitting all "
                  f"{len(keys)} cells.")
        elif missing:
            print(f"  CACHE PARTIAL: {len(P)} of {len(keys)} cells loaded, "
                  f"{len(missing)} missing and being fitted now.")
        else:
            print(f"  LOADED all {len(keys)} cells from "
                  f"{os.path.basename(cache)} -- nothing refitted.")
    tf = time.time()
    for i, k in enumerate(missing, 1):
        P[k] = fit_one(k)
        if verbose:
            print(f"  fitted {'/'.join(str(x) for x in k):<32} "
                  f"[{i}/{len(missing)}]  {time.time()-tf:.0f}s", flush=True)
    return P, len(keys) - len(missing), len(missing), needs_save or bool(missing)


def save_cache(cache, fingerprint, P, keys):
    """Write the requested cells, CARRYING FORWARD every other key the file holds.

    Since REGISTRY-CONSOLIDATED a stage requests three models, but its cache
    file also holds the retired QTREE and kNN predictions that other scripts
    read as history. Writing only the requested keys would silently delete
    them on the next refit. Carrying them is safe: load_or_fit has already
    refused any file whose fingerprint differs from `fingerprint`, so every
    carried key was fitted on the same inputs as the ones being written.
    Returns the number of keys carried.
    """
    out = {"|".join(str(x) for x in k): P[k] for k in keys}
    carried = 0
    if os.path.exists(cache):
        z = np.load(cache, allow_pickle=False)
        for n in z.files:
            if n != FP_KEY and n not in out:
                out[n] = z[n]
                carried += 1
    np.savez_compressed(cache, **{FP_KEY: np.array(fingerprint)}, **out)
    return carried


# ------------------------------------------------------- conformalized QR
# CQR (Romano, Patterson & Candes 2019) wrapped around QTREE only. The plain
# quantile loss gives calibration that is asymptotic at best and, on this data,
# measurably wrong; CQR replaces that with a finite-sample coverage guarantee --
# under an assumption this project has already measured to be false, which is
# exactly why it is worth running.
#
# THE GUARANTEE AND ITS TWO LEAKS, both stated before any number is read:
#
#   1. EXCHANGEABILITY. CQR guarantees P(y in [lo', hi']) >= 1 - alpha when
#      calibration and test rows are exchangeable. The HALVES ANALYSIS measured
#      that they are not: the gap was 1.06pp on the near half of the held-out
#      block and 3.05pp on the far half, worse in 80 of 80 cells. So the
#      prediction here is that a val-calibrated correction holds on HO1, which
#      sits next to val in time, and decays on HO2. That is not a surprise to be
#      explained away afterwards; it is the hypothesis.
#
#   2. VAL CHOSE QTREE'S ITERATION COUNT, so the calibration residuals are
#      mildly optimistic. This is NOT a new discipline exception -- val has
#      always been the iteration-count block and is still never scored -- but it
#      does bias the conformal width DOWNWARD, because the model was stopped at
#      the iteration that minimised pinball on these very rows. The correction
#      is therefore a slight under-correction, and the honest reading of a
#      failure on HO1 is "at least this bad".
#
# WHAT IS GUARANTEED IS THE PAIR, NOT THE LEVEL. CQR corrects a two-sided
# interval, so the quantity with a guarantee is the (q5, q95) interval at 90%
# and the (q25, q75) interval at 50%. The 5-level calibration gap the rest of
# this project tracks is reported alongside, but it is not what CQR promises.
CQR_PAIRS = ((0, 4, 0.10), (1, 3, 0.50))    # (lo index, hi index, alpha)


def conformal_width(y_cal, lo_cal, hi_cal, alpha):
    """The CQR correction: the ceil((n+1)(1-alpha))-th smallest conformity score.

    E_i = max(lo(x_i) - y_i, y_i - hi(x_i)) is negative when the episode falls
    strictly inside its interval and positive when it falls outside, so a
    NEGATIVE width is legitimate and means the interval was too wide and gets
    tightened. The (n+1) is the finite-sample correction and is not cosmetic:
    without it the guarantee is asymptotic only.
    """
    E = np.maximum(lo_cal - y_cal, y_cal - hi_cal)
    n = len(E)
    k = int(np.ceil((n + 1) * (1.0 - alpha)))
    if k > n:
        return float(np.max(E)), True
    return float(np.sort(E)[k - 1]), False


def apply_cqr(pred, widths, med_shift):
    """Widen each pair by its own conformal width, shift the median, re-order.

    CQR CORRECTS EACH PAIR INDEPENDENTLY AND THAT CAN CROSS THE LEVELS. If the
    inner pair's width is large and the outer pair's is small, q25 - w_inner can
    fall below q5 - w_outer, so the running maximum along q is applied here and
    its rate is reported.

    The median has no two-sided interval, so it gets a one-sided shift instead:
    the median of the calibration residuals y - q50, which forces val's median
    coverage to exactly 0.50. That is the building session's call among several
    defensible ones, and it is the only one that leaves q50 interpretable as a
    median rather than as half of an interval.
    """
    out = pred.copy()
    for (jl, jh, _), w in zip(CQR_PAIRS, widths):
        out[:, jl] = pred[:, jl] - w
        out[:, jh] = pred[:, jh] + w
    out[:, MEDIAN_IX] = pred[:, MEDIAN_IX] + med_shift
    fixed = np.maximum.accumulate(out, axis=1)
    return fixed, float((fixed != out).mean())


def qtree_val_test(ctx, y):
    """QTREE's val AND held-out predictions at the val-chosen iteration.

    A REFIT IS UNAVOIDABLE AND THE ASSERTION IS WHAT MAKES IT SAFE. Only
    held-out predictions were ever persisted, and CQR needs predictions on the
    calibration block, so the model has to exist again. Every input is
    deterministic -- seeded split, random_state=0, a fixed iteration count
    chosen by pinball on val -- so the refit must reproduce the cached held-out
    predictions bit for bit. The caller asserts exactly that, and a mismatch
    means something in the pipeline has drifted since the cache was written,
    which is worth knowing immediately rather than discovering in the numbers.
    """
    ytr, yva = y[ctx["train"]], y[ctx["val"]]
    va = np.empty((int(ctx["val"].sum()), len(QUANTILES)))
    te = np.empty((ctx["n_test"], len(QUANTILES)))
    iters = []
    for j, q in enumerate(QUANTILES):
        m = HistGradientBoostingRegressor(loss="quantile", quantile=q,
                                          random_state=0, **harness.TREE)
        m.fit(ctx["Xtr"], ytr)
        sv = list(m.staged_predict(ctx["Xva"]))
        best = int(np.argmin([_pinball(yva, p, q) for p in sv]))
        va[:, j] = sv[best]
        te[:, j] = list(m.staged_predict(ctx["Xte"]))[best]
        iters.append(best + 1)
    return va, te, iters


def level_breakdown(y, raw, cqr, boot):
    """Per-level paired change, raw -> CQR, on identical rows and resamples.

    Two readings per level, each with a day-clustered interval:

      dabs  |cov_cqr - q| - |cov_raw - q|, in pp. Negative = closer to nominal.
            The 5-level gap's change is exactly the mean of these, so this
            says WHICH LEVELS carry a gap reduction. That matters because
            apply_cqr moves q50 by the median shift and moves the other four
            levels only by their pair's width; a gain concentrated in q50 is a
            location correction, a gain in the outer levels is the tightening.
      dsig  cov_cqr - cov_raw, in pp, SIGNED. It does not fold at zero, which
            the absolute gap does: near nominal a bootstrap draw crosses zero
            and |.| reflects it back, widening and skewing the interval. HO1
            sits near nominal, so HO1 is read on this.
    """
    q = np.asarray(QUANTILES)
    hr = y[:, None] <= raw
    hc = y[:, None] <= cqr

    def stats(ix):
        cr, cc = hr[ix].mean(0), hc[ix].mean(0)
        return 100 * (np.abs(cc - q) - np.abs(cr - q)), 100 * (cc - cr)

    dabs, dsig = stats(slice(None))
    A = np.empty((len(boot), len(q)))
    S = np.empty((len(boot), len(q)))
    for r, ix in enumerate(boot):
        A[r], S[r] = stats(ix)
    return dict(dabs=dabs, dabs_lo=np.percentile(A, 2.5, axis=0),
                dabs_hi=np.percentile(A, 97.5, axis=0),
                sraw=100 * (hr.mean(0) - q), scqr=100 * (hc.mean(0) - q),
                dsig=dsig, dsig_lo=np.percentile(S, 2.5, axis=0),
                dsig_hi=np.percentile(S, 97.5, axis=0))


def stage_cqr(Y, meta, X, fnames, day, y_entry, args, t0):
    """CQR on QTREE, calibrated on val, tested on HO1 and HO2 separately.

    POPULATION. The 1-minute-measurable subset and BOTH target sources, which is
    the same ground the matched comparison stands on. Both arms are kept because
    they answer different halves of the question: the 30-minute arm is directly
    comparable to the isotonic recalibration already recorded, and the 1-minute
    arm is the better-measured target. Neither is a flag; the stage reports both
    the way the matched stage does.
    """
    print("=" * 118)
    print("CONFORMALIZED QUANTILE REGRESSION -- QTREE only, calibrated on val")
    print("=" * 118)
    print("  WHY QTREE AND NOTHING ELSE. One base model, not four. QTREE carries")
    print("  the strongest point-estimate skill on MFE, so it is the one worth")
    print("  asking whether that skill can be paired with a formal coverage")
    print("  guarantee instead of the quantile loss's unguaranteed calibration.")
    print()
    print("  THE GUARANTEE ASSUMES EXCHANGEABILITY AND THIS DATA IS NOT")
    print("  EXCHANGEABLE. The halves analysis measured a 1.06pp gap next to the")
    print("  cut and 3.05pp further out, worse in 80 of 80 cells. So the")
    print("  hypothesis, stated before the numbers: the val-fitted correction")
    print("  holds on HO1, which abuts val in time, and decays on HO2. A failure")
    print("  on HO2 confirms the drift mechanism through a more rigorous tool --")
    print("  it is not a defect of CQR.")
    print()
    print("  SECOND LEAK, SMALLER AND EASY TO MISS. Val chose QTREE's iteration")
    print("  count. That is not a new discipline exception -- val has always been")
    print("  the iteration block and is still never scored -- but the model was")
    print("  stopped where pinball was lowest ON THESE ROWS, so the calibration")
    print("  residuals are optimistic and the conformal width is biased DOWNWARD.")
    print("  Every correction below is therefore a slight under-correction, and a")
    print("  failure reads as 'at least this bad', never as 'at most'.")
    print()
    print("  WHAT CQR GUARANTEES IS THE PAIR, NOT THE LEVEL: the (q5,q95)")
    print("  interval at 90% and (q25,q75) at 50%. The 5-level gap is reported")
    print("  next to it because the rest of this project tracks it, but it is not")
    print("  what the method promises.")
    print()

    cov = scan_1m_coverage(meta, verbose=True)
    mask_used, _ = select_1m_subset(meta, cov, verbose=False)
    rows = np.flatnonzero(mask_used)
    Xs, days, ys = X[rows], day[rows], y_entry[rows]
    ctx = build_context(np.ones(len(rows), bool), Xs, days, ys, verbose=True)
    sp = ctx["sp"]
    print(f"  calibration block (val): {int(sp.val.sum()):,} rows, "
          f"{pd.Timestamp(sp.vcut).date()} .. {pd.Timestamp(harness.CUT).date()}")

    T30, _ = build_targets_30m(Y[rows])
    T1M, _ = build_targets_1m(Y, meta, rows=rows, verbose=False)
    assert_1m_dominates(T30, T1M, Y[rows], verbose=True)
    TGT = {"30m": T30, "1m": T1M}

    # held-out halves, same boundary as the halves analysis
    dte = ctx["day_test"]
    h1 = dte < HO_BOUNDARY
    h2 = ~h1
    boot = {"HO1": day_boot(dte[h1]), "HO2": day_boot(dte[h2])}
    sel = {"HO1": h1, "HO2": h2}
    print(f"  HO1 {int(h1.sum()):,} rows / {len(np.unique(dte[h1])):,} days   "
          f"HO2 {int(h2.sum()):,} rows / {len(np.unique(dte[h2])):,} days   "
          f"boundary {pd.Timestamp(HO_BOUNDARY).date()}")
    print()

    cache = paths.envelope_preds("match1m")
    cached = np.load(cache, allow_pickle=False) if os.path.exists(cache) else None

    print("=" * 118)
    print("REFIT CHECK -- the cached held-out predictions must come back identical")
    print("=" * 118)
    print("  Only held-out predictions were persisted and CQR needs the")
    print("  calibration block, so QTREE is refitted. Everything feeding it is")
    print("  deterministic, so the refit must reproduce the cache exactly.")
    print()
    print("  THE CACHE HOLDS PREDICTIONS AFTER BOTH ENFORCEMENT PASSES -- quantile")
    print("  axis, then horizon axis -- so the refit gets the same two passes,")
    print("  across all five horizons of each group, BEFORE it is compared. An")
    print("  earlier version applied only the quantile pass. Horizon enforcement")
    print("  had moved 0.16-0.68% of QTREE's predictions in every group, so that")
    print("  version would have aborted on every run, blaming a drift that never")
    print("  happened and advising deletion of a cache that was correct.")
    print()

    # the fingerprint first: it catches a data change the refit could miss
    fp = cache_fingerprint([rows], flat_targets(TGT), Xs)
    if cached is not None:
        if FP_KEY in cached.files:
            if str(cached[FP_KEY]) != fp:
                raise SystemExit(
                    f"[CQR ] ABORT -- {os.path.basename(cache)}'s fingerprint does "
                    f"not match these inputs.\n"
                    f"        Rows, targets, features or harness.TREE changed since "
                    f"it was written, so its\n"
                    f"        held-out predictions are not this population's. Rerun "
                    f"--stage match1m.")
            print(f"  cache fingerprint matches ({fp[:16]}...).")
        else:
            print("  LEGACY cache with no fingerprint: the refit comparison below is")
            print("  the only guard. Running --stage match1m once stamps one.")
    print()

    print(f"  {'src':<5}{'dir':<5}{'h':>6}{'val rows':>10}{'iters chosen':>26}"
          f"{'max |refit - cache|':>22}")
    RAW_VA, RAW_TE = {}, {}
    worst = 0.0
    for src in ("30m", "1m"):
        for d in DIRECTIONS:
            vas, tes, its = [], [], []
            for k in HORIZONS:
                va, te, iters = qtree_val_test(ctx, TGT[src][(d, k)])
                vas.append(va)
                tes.append(te)
                its.append(iters)
            # the SAME two passes match1m applied before it cached
            te_enf, _, _ = enforce_two_pass(np.stack(tes))
            # and val gets them too: conformal scores must be computed on the
            # same prediction function that is then applied to held-out rows,
            # or the width is calibrated for a different predictor
            va_enf, _, _ = enforce_two_pass(np.stack(vas))
            for i, k in enumerate(HORIZONS):
                RAW_VA[(src, d, k)] = va_enf[i]
                RAW_TE[(src, d, k)] = te_enf[i]
                err = np.nan
                name = f"{src}|{d}|QTREE|{k}"
                if cached is not None and name in cached.files:
                    err = float(np.max(np.abs(te_enf[i] - cached[name])))
                    worst = max(worst, err)
                print(f"  {src:<5}{d:<5}{HLABEL[k]:>6}{len(va_enf[i]):>10,}"
                      f"{str(its[i]):>26}{err:>22.3e}", flush=True)
    print()
    if cached is not None:
        print(f"  worst disagreement across all 20 cells: {worst:.3e}")
        if worst > 1e-12:
            raise SystemExit(
                f"[CQR ] ABORT -- the QTREE refit does not reproduce the cached "
                f"held-out predictions\n"
                f"        (worst {worst:.3e}), and this is AFTER the same two-pass "
                f"enforcement the cache\n"
                f"        received, so the comparison is like for like. Nothing in "
                f"the path is stochastic.\n"
                f"        If the fingerprint check above passed, the data is "
                f"unchanged: suspect a\n"
                f"        harness.TREE edit or an sklearn version change. Do NOT "
                f"delete the cache on this\n"
                f"        message alone -- it holds 1,232s of Linear QR solves. Find "
                f"what changed first.")
        print("  Identical. The held-out predictions below are run match1m's, not a")
        print("  re-estimate; only the val block is new.")
    else:
        print(f"  NO CACHE at {os.path.basename(cache)} -- nothing to check "
              f"against. Run --stage match1m first if you want this guard.")
    print()

    # ---- fit the correction on val, apply it to each half ----
    print("=" * 118)
    print("THE CORRECTION -- one set of widths per cell, fitted on val only")
    print("=" * 118)
    print("  A NEGATIVE width is legitimate: it means the raw interval was too")
    print("  wide on val and conformalisation TIGHTENS it. The outer pair targets")
    print("  90% coverage and the inner pair 50%.")
    print("  q-reorder: CQR widens each pair independently, which can cross the")
    print("  levels. h-reorder: each horizon has its own widths, which can break")
    print("  the running max in k, so it is re-applied -- every other model in the")
    print("  table is horizon-enforced and this one must be too. The horizon pass")
    print("  only RAISES predictions, so it can erode a pair's guarantee slightly")
    print("  at its lower bound; the rate says by how much it touched.")
    print()
    print(f"  {'src':<5}{'dir':<5}{'h':>6}{'w(5,95)':>10}{'w(25,75)':>10}"
          f"{'median shift':>14}{'q-reorder':>11}{'h-reorder':>11}")
    CORR = {}
    for src in ("30m", "1m"):
        for d in DIRECTIONS:
            cq = []
            for k in HORIZONS:
                va, te = RAW_VA[(src, d, k)], RAW_TE[(src, d, k)]
                yva = TGT[src][(d, k)][ctx["val"]]
                widths, exhausted = [], []
                for jl, jh, alpha in CQR_PAIRS:
                    w, ex = conformal_width(yva, va[:, jl], va[:, jh], alpha)
                    widths.append(w)
                    exhausted.append(ex)
                shift = float(np.median(yva - va[:, MEDIAN_IX]))
                corrected, rate_q = apply_cqr(te, widths, shift)
                cq.append(corrected)
                CORR[(src, d, k)] = dict(raw=te, widths=widths, shift=shift,
                                         rate_q=rate_q, exhausted=any(exhausted))
            stack = np.stack(cq)
            s2 = np.maximum.accumulate(stack, axis=0)
            rate_k = float((s2 != stack).mean())
            for i, k in enumerate(HORIZONS):
                c = CORR[(src, d, k)]
                c["cqr"], c["rate_k"] = s2[i], rate_k
                flag = "  <- n too small for the level" if c["exhausted"] else ""
                print(f"  {src:<5}{d:<5}{HLABEL[k]:>6}{c['widths'][0]:>+10.4f}"
                      f"{c['widths'][1]:>+10.4f}{c['shift']:>+14.4f}"
                      f"{100*c['rate_q']:>10.3f}%{100*rate_k:>10.3f}%{flag}")
    print()

    # ---- what CQR actually guarantees: pair interval coverage, per half ----
    print("=" * 118)
    print("GUARANTEED QUANTITY -- two-sided interval coverage, per held-out half")
    print("=" * 118)
    print("  This is the number CQR promises to hold at or above nominal. Read")
    print("  HO1 against HO2: the correction was fitted on val, which abuts HO1.")
    print()
    print(f"  {'src':<5}{'dir':<5}{'h':>6}{'pair':>10}{'nominal':>9}"
          f"{'HO1 raw':>9}{'HO1 CQR':>9}{'HO2 raw':>9}{'HO2 CQR':>9}{'':>12}")
    held = {"HO1": 0, "HO2": 0}
    tot = 0
    for src in ("30m", "1m"):
        for d in DIRECTIONS:
            for k in HORIZONS:
                c = CORR[(src, d, k)]
                y = TGT[src][(d, k)][ctx["test"]]
                for jl, jh, alpha in CQR_PAIRS:
                    nom = 1.0 - alpha
                    cells = {}
                    for half in ("HO1", "HO2"):
                        m = sel[half]
                        for nm, pr in (("raw", c["raw"]), ("cqr", c["cqr"])):
                            inside = ((y[m] >= pr[m, jl]) & (y[m] <= pr[m, jh]))
                            cells[(half, nm)] = float(inside.mean())
                    tot += 1
                    for half in ("HO1", "HO2"):
                        held[half] += cells[(half, "cqr")] >= nom - 1e-12
                    verdict = ""
                    if cells[("HO1", "cqr")] >= nom and cells[("HO2", "cqr")] < nom:
                        verdict = "HO1 only"
                    elif cells[("HO1", "cqr")] >= nom and cells[("HO2", "cqr")] >= nom:
                        verdict = "both"
                    elif cells[("HO1", "cqr")] < nom:
                        verdict = "neither"
                    print(f"  {src:<5}{d:<5}{HLABEL[k]:>6}"
                          f"{f'q{int(100*QUANTILES[jl])}-q{int(100*QUANTILES[jh])}':>10}"
                          f"{100*nom:>8.0f}%{100*cells[('HO1','raw')]:>9.1f}"
                          f"{100*cells[('HO1','cqr')]:>9.1f}"
                          f"{100*cells[('HO2','raw')]:>9.1f}"
                          f"{100*cells[('HO2','cqr')]:>9.1f}{verdict:>12}")
    print()
    print(f"  {tot} (cell, pair) combinations. Conformalised coverage at or above")
    print(f"  nominal:  HO1 {held['HO1']} of {tot}   HO2 {held['HO2']} of {tot}.")
    print("  NOT EVIDENCE EITHER WAY. Raw interval coverage already sits within")
    print("  ~1pp of nominal, CQR moves it by tenths of a point, and this table")
    print("  carries NO intervals, so a strict >= count on numbers that close is")
    print("  near a coin flip. The guarantee is therefore UNTESTED by this run.")
    print("  An earlier version of this line called the HO1-HO2 difference 'the")
    print("  exchangeability failure, measured through the guarantee'. It was not.")
    print()

    # ---- the project's usual gap, before and after, paired per half ----
    print("=" * 118)
    print("5-LEVEL CALIBRATION GAP -- before and after, paired within each half")
    print("=" * 118)
    print("  NOT the guaranteed quantity. Reported because every other number in")
    print("  this project is in these units. Paired: identical rows and day")
    print("  resamples on both sides, only the prediction changing. Negative =")
    print("  CQR improved it.")
    print()
    print(f"  {'src':<5}{'dir':<5}{'h':>6}{'half':>5}{'raw':>8}{'CQR':>8}"
          f"{'CQR-raw':>9}{'[95% CI]':>18}{'':>10}")
    better = {"HO1": 0, "HO2": 0}
    closed = {"HO1": 0, "HO2": 0}
    ncell = 0
    for src in ("30m", "1m"):
        for d in DIRECTIONS:
            for k in HORIZONS:
                c = CORR[(src, d, k)]
                y = TGT[src][(d, k)][ctx["test"]]
                ncell += 1
                for half in ("HO1", "HO2"):
                    m = sel[half]
                    g0, _, _ = gap_ci(y[m], c["raw"][m], boot[half])
                    g1, _, _ = gap_ci(y[m], c["cqr"][m], boot[half])
                    dd, dl, dh = gap_paired_ci(y[m], c["raw"][m],
                                               y[m], c["cqr"][m], boot[half])
                    better[half] += dd < 0
                    tag = ""
                    if dh < 0:
                        tag = "IMPROVES"; closed[half] += 1
                    elif dl > 0:
                        tag = "WORSENS"
                    print(f"  {src:<5}{d:<5}{HLABEL[k]:>6}{half:>5}{g0:>8.2f}"
                          f"{g1:>8.2f}{dd:>+9.2f}"
                          f"{f'[{dl:+.2f},{dh:+.2f}]':>18}{tag:>10}")
    print()
    for half in ("HO1", "HO2"):
        print(f"  {half}: gap smaller after CQR (point estimate) "
              f"{better[half]} of {ncell};  interval excludes zero "
              f"{closed[half]} of {ncell}.")
    print("  The second number in each line is the one that counts.")
    exp_chance = 0.025 * ncell
    print(f"  Chance alone puts about {exp_chance:.1f} of {ncell} intervals past zero on")
    print(f"  the improving side per half (2.5% each), so read the counts against")
    print(f"  that, not against zero.")
    print()

    # ---- which LEVELS carry the change ----
    print("=" * 118)
    print("PER-LEVEL BREAKDOWN -- which levels carry the gap change")
    print("=" * 118)
    print("  apply_cqr moves q50 by the median shift and moves q5/q95 and q25/q75")
    print("  ONLY by their pair's width, so this separates a location correction")
    print("  (q50) from the tightening (the four pair levels). Each entry is")
    print("  |cov_CQR - q| - |cov_raw - q| in pp; negative = closer to nominal.")
    print("  '*' = interval excludes zero on the improving side, '!' = worsening.")
    print()
    print(f"  {'src':<5}{'dir':<5}{'h':>6}{'half':>5}" +
          "".join(f"{'q'+str(int(100*q)):>10}" for q in QUANTILES))
    LB = {}
    for src in ("30m", "1m"):
        for d in DIRECTIONS:
            for k in HORIZONS:
                c = CORR[(src, d, k)]
                y = TGT[src][(d, k)][ctx["test"]]
                for half in ("HO1", "HO2"):
                    m = sel[half]
                    b = level_breakdown(y[m], c["raw"][m], c["cqr"][m], boot[half])
                    LB[(src, d, k, half)] = b
                    cells = []
                    for j in range(len(QUANTILES)):
                        mk = ("*" if b["dabs_hi"][j] < 0 else
                              "!" if b["dabs_lo"][j] > 0 else " ")
                        cells.append(f"{b['dabs'][j]:>+9.2f}{mk}")
                    print(f"  {src:<5}{d:<5}{HLABEL[k]:>6}{half:>5}" + "".join(cells))
    print()
    print("  SUMMARY over the 20 cells of each half:")
    print(f"  {'half':<6}{'level':>7}{'mean change':>13}{'improves*':>11}"
          f"{'worsens!':>10}{'share of total':>16}")
    for half in ("HO1", "HO2"):
        allv = np.array([[LB[(s_, d_, k_, half)]["dabs"][j]
                          for j in range(len(QUANTILES))]
                         for s_ in ("30m", "1m") for d_ in DIRECTIONS
                         for k_ in HORIZONS])
        total = float(allv.sum())
        for j, q in enumerate(QUANTILES):
            his = [LB[(s_, d_, k_, half)] for s_ in ("30m", "1m")
                   for d_ in DIRECTIONS for k_ in HORIZONS]
            imp = sum(h_["dabs_hi"][j] < 0 for h_ in his)
            wor = sum(h_["dabs_lo"][j] > 0 for h_ in his)
            share = (100 * allv[:, j].sum() / total) if total != 0 else float("nan")
            print(f"  {half:<6}{'q'+str(int(100*q)):>7}{allv[:, j].mean():>+13.3f}"
                  f"{imp:>11}{wor:>10}{share:>15.1f}%")
        print(f"  {half:<6}{'q50 vs the four pair levels':>40}:  "
              f"{100*allv[:, MEDIAN_IX].sum()/total:.1f}% from the median shift, "
              f"{100*(total-allv[:, MEDIAN_IX].sum())/total:.1f}% from the widths"
              if total != 0 else "")
    print("  'share of total' is each level's part of the summed gap change; a")
    print("  negative share means that level moved AWAY from nominal on balance.")
    print()

    # ---- HO1 on signed deviation, which does not fold at zero ----
    print("=" * 118)
    print("HO1 ON SIGNED DEVIATION -- read where the absolute gap folds at zero")
    print("=" * 118)
    print("  raw and CQR are actual - nominal coverage in pp, signed. change is")
    print("  CQR - raw with a day-clustered interval. 'T' = it moves TOWARD")
    print("  nominal and the interval excludes zero; 'A' = moves AWAY, same test.")
    print("  Toward means the change has the opposite sign to the raw deviation.")
    print()
    print(f"  {'src':<5}{'dir':<5}{'h':>6}" +
          "".join(f"{'q'+str(int(100*q))+' raw>CQR':>18}" for q in QUANTILES))
    tally = {h_: {"T": np.zeros(len(QUANTILES), int),
                  "A": np.zeros(len(QUANTILES), int)} for h_ in ("HO1", "HO2")}
    for src in ("30m", "1m"):
        for d in DIRECTIONS:
            for k in HORIZONS:
                for half in ("HO1", "HO2"):
                    b = LB[(src, d, k, half)]
                    for j in range(len(QUANTILES)):
                        sig = b["dsig_lo"][j] > 0 or b["dsig_hi"][j] < 0
                        toward = b["dsig"][j] * b["sraw"][j] < 0
                        if sig:
                            tally[half]["T" if toward else "A"][j] += 1
                b = LB[(src, d, k, "HO1")]
                cells = []
                for j in range(len(QUANTILES)):
                    sig = b["dsig_lo"][j] > 0 or b["dsig_hi"][j] < 0
                    toward = b["dsig"][j] * b["sraw"][j] < 0
                    mk = ("T" if toward else "A") if sig else " "
                    cells.append(f"{b['sraw'][j]:>+7.2f}>{b['scqr'][j]:>+6.2f} {mk}  ")
                print(f"  {src:<5}{d:<5}{HLABEL[k]:>6}" + "".join(f"{c_:>18}" for c_ in cells))
    print()
    print(f"  {'half':<6}{'level':>7}{'toward T':>10}{'away A':>9}   (of 20 cells)")
    for half in ("HO1", "HO2"):
        for j, q in enumerate(QUANTILES):
            print(f"  {half:<6}{'q'+str(int(100*q)):>7}{tally[half]['T'][j]:>10}"
                  f"{tally[half]['A'][j]:>9}")
    print()

    # ---- persist, so the next breakdown needs no refit ----
    cqr_cache = paths.envelope_preds("cqr")
    np.savez_compressed(cqr_cache, **{FP_KEY: np.array(fp)},
                        **{f"cqr|{s_}|{d_}|{k_}": CORR[(s_, d_, k_)]["cqr"]
                           for s_ in ("30m", "1m") for d_ in DIRECTIONS
                           for k_ in HORIZONS},
                        **{f"corr|{s_}|{d_}|{k_}": np.array(
                               CORR[(s_, d_, k_)]["widths"]
                               + [CORR[(s_, d_, k_)]["shift"]])
                           for s_ in ("30m", "1m") for d_ in DIRECTIONS
                           for k_ in HORIZONS})
    print(f"  [CACHE] wrote {os.path.basename(cqr_cache)}: the CQR-corrected held-out")
    print(f"  predictions and each cell's (w_outer, w_inner, median shift), with the")
    print(f"  same fingerprint as the match1m cache. A later breakdown reads these")
    print(f"  and refits nothing; until now they existed only in process memory.")
    print()
    print(f"  [{time.time()-t0:.0f}s]")
    print("=" * 118)
    print("WHAT IS AND IS NOT DEMONSTRATED")
    print("=" * 118)
    print("  NOT TESTED: CQR's guarantee. The interval-coverage table carries no")
    print("  intervals and sits within ~1pp of nominal before any correction, so")
    print("  it cannot say whether the guarantee holds on either half.")
    print("  DEMONSTRATED, where the counts above say so: a correction fitted on")
    print("  val shrinks the 5-level calibration gap, by paired intervals that")
    print("  exclude zero, against the ~1 per half chance would produce. The")
    print("  isotonic recalibration managed 0 of 80 on the same kind of test.")
    print("  THE MECHANISM is whatever the per-level breakdown shows -- location")
    print("  (q50) or tightening (the pair levels) -- and is not asserted beyond it.")
    print("  Levels here are a later look at rows already scored; the raw-versus-")
    print("  CQR differences are within-row contrasts and are the new measurement.")
    print("=" * 118)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target-source", choices=("30m", "1m"), default="30m")
    # NAMING, because the previous brief used "run 2" for something else: this
    # flag selects the ANALYSIS stage. --target-source selects the TARGET's bar
    # resolution. They are orthogonal axes; the 1-minute rerun is
    # --target-source 1m, not --stage run2.
    ap.add_argument("--stage", choices=("run1", "run2", "match1m", "cqr"),
                    default="run1",
                    help="run1 = the full fit and calibration report. "
                         "run2 = the HALVES ANALYSIS: split the held-out block, "
                         "test isotonic transfer, reorder the report; reuses "
                         "run1's cached predictions and refits nothing. "
                         "match1m = the 1-MINUTE RERUN: 30-minute and 1-minute "
                         "targets on the identical measurable subset, same split, "
                         "same models. Ignores --target-source, which it sets "
                         "both ways by construction. "
                         "cqr = conformalize QTREE on val and test the "
                         "correction on HO1 and HO2 separately; same population "
                         "and both target sources as match1m.")
    args = ap.parse_args()
    t0 = time.time()

    z = np.load(paths.DISLOC)
    Y = z["outcomes"].astype(np.float64)
    meta = pd.read_parquet(paths.META)
    f = np.load(paths.ENVFEAT, allow_pickle=False)
    X = f["X"].astype(np.float64)
    fnames = [str(x) for x in f["names"]]
    day = meta.day.to_numpy()
    y_entry = Y[:, 0]

    print("=" * 112)
    print(f"ENVELOPE DESCRIPTION -- target source {args.target_source}")
    print("=" * 112)
    print(f"  {len(meta):,} episodes, {X.shape[1]} features: {', '.join(fnames)}")
    print(f"  target: running MAE and MFE, sign-folded, UNCLAMPED (see docstring)")
    print(f"  quantiles {QUANTILES}   horizons {[HLABEL[k] for k in HORIZONS]}")
    print()
    if args.stage == "cqr":
        stage_cqr(Y, meta, X, fnames, day, y_entry, args, t0)
        return

    if args.stage == "match1m":
        # Routed before the whole-population target build: that build aborts on
        # the 1-minute path by design, and this stage's whole point is to run on
        # the subset where it does not. --target-source is ignored here because
        # the stage sets both sources by construction.
        stage_match1m(Y, meta, X, fnames, day, y_entry, args, t0)
        return

    if args.target_source == "30m":
        print("  THIS RUN USES 30-MINUTE CLOSES. The true envelope is strictly worse:")
        print("  the worst point inside a bar is never observed. Earlier work puts the")
        print("  understatement at roughly 0.3 sigma, one-sided, scaling with volatility.")
        print("  CLIMATOLOGY IS BIASED THE SAME WAY, so comparative skill should be")
        print("  largely unaffected -- an assumption, stated and not corrected for.")
        targets, tinfo = build_targets_30m(Y)
    else:
        targets, tinfo = build_targets_1m(Y, meta)
    print()

    # populations. The trending cutoff comes from the FIT BLOCK ONLY and is then
    # applied as a fixed number to fit and held-out rows alike.
    full_sp = harness.Split(day, y_entry)
    vratio = X[:, fnames.index("vratio")]
    cut = float(np.quantile(vratio[full_sp.fit], 1.0 / 3.0))
    pops = {
        "ALL": np.ones(len(X), bool),
        "TRENDING": vratio <= cut,
    }
    print(f"  TRENDING = bottom tercile of vratio. Cutoff {cut:.5f}, computed on the")
    print(f"  FIT BLOCK ONLY ({int(full_sp.fit.sum()):,} rows) and applied as a fixed")
    print(f"  number to both blocks -- never recomputed on held-out data.")
    for nm, m in pops.items():
        print(f"    {nm:<9} {int(m.sum()):>7,} episodes  "
              f"({int((m & full_sp.test).sum()):,} held out)")
    print()

    # ---- does the UNCONDITIONAL envelope even transfer out of sample? ----
    # Printed before any model, because if climatology drifts then every model
    # trained on the fit block inherits that drift, and a wall of calibration
    # failures below is attributable rather than mysterious.
    print("=" * 112)
    print("BASELINE TRANSFER -- climatology's own coverage, in-sample vs held out")
    print("=" * 112)
    print("  Climatology is the TRAIN block's empirical quantile -- the same 22,683 rows")
    print("  every model is fitted on -- so IN-SAMPLE coverage is exact by construction.")
    print("  Any gap on the held-out block is REGIME DRIFT in the envelope's level, not a")
    print("  modelling choice, and every model below inherits it.")
    print("  TRAIN, not train+val: this must use the same block as fit_climatology or the")
    print("  diagnostic disagrees with the model it is explaining. It did, briefly --")
    print("  0.265 against 0.262 at ALL/MAE/0.5h -- when climatology moved to train and")
    print("  this block was left on the fit block.")
    print()
    print(f"  {'dir':<5}{'h':>6}{'block':>12}" +
          "".join(f"{'q'+str(int(q*100)):>9}" for q in QUANTILES))
    for direction in DIRECTIONS:
        for k in HORIZONS:
            y = targets[(direction, k)]
            qv = np.quantile(y[full_sp.train], QUANTILES)
            cin = [float((y[full_sp.train] <= qv[j]).mean()) for j in range(len(QUANTILES))]
            cout = [float((y[full_sp.test] <= qv[j]).mean()) for j in range(len(QUANTILES))]
            print(f"  {direction:<5}{HLABEL[k]:>6}{'in-sample':>12}" +
                  "".join(f"{c:>9.3f}" for c in cin))
            print(f"  {'':<5}{'':>6}{'HELD OUT':>12}" +
                  "".join(f"{c:>9.3f}" for c in cout) +
                  "   <- gap here is drift, inherited by every model")
    print()

    ctxs = {}
    for nm, m in pops.items():
        print(f"  [{nm}]")
        ctxs[nm] = build_context(m, X, day, y_entry, verbose=True)
    print()

    # ---- fit everything, store predictions. CACHED, GAP-FILLED. ----
    cache = paths.envelope_preds(args.target_source)
    FN = ALL_FITTERS
    keys = [(pop, d, mn, k) for pop in pops for d in DIRECTIONS
            for mn, _ in MODELS for k in HORIZONS]

    def _fit_one(key):
        pop, d, mn, k = key
        ctx = ctxs[pop]
        return FN[mn](ctx, targets[(d, k)][ctx["sub"]], f"{pop}/{d}/{HLABEL[k]}")

    fp = cache_fingerprint([ctxs[pop]["sub"] for pop in sorted(pops)],
                           flat_targets(targets), X)
    P, n_loaded, n_fitted, needs_save = load_or_fit(cache, keys, _fit_one, fp)

    # ---- structural checks ----
    print()
    print("=" * 112)
    print("STRUCTURAL CORRECTNESS -- bug-catchers, not judgment calls")
    print("=" * 112)
    print("  The target is a running max in k, and quantiles are ordered in q. Both are")
    print("  HARD constraints, so both are now ENFORCED rather than gated on.")
    print()
    print("  THIS WAS A GATE AND THE GATE WAS WRONG. It required zero violations, and")
    print("  it counted them across all five horizons at once, so a single violation")
    print("  anywhere disqualified every horizon of that model. Each horizon is an")
    print("  INDEPENDENT fit -- nothing forces the 10h fit above the 5h fit on a given")
    print("  episode -- so cross-horizon violations are normal behaviour, not a bug.")
    print("  Measured on val: QTREE/MAE had 7,060 monotonicity violations of 385,060")
    print("  (1.833%) and 8 quantile crossings (0.002%). Climatology cannot violate")
    print("  either. The rule therefore failed every conditional model BY CONSTRUCTION")
    print("  and would have retired the feature set on an artifact.")
    print()
    print(f"  {'population':<10}{'dir':<5}{'model':<13}"
          f"{'quantile enforce':>17}{'horizon enforce':>19}")
    struct = {}
    for pop in pops:
        for direction in DIRECTIONS:
            for mname, _ in MODELS:
                stack = np.stack([P[(pop, direction, mname, k)] for k in HORIZONS])
                s2, rate_q, rate_k = enforce_two_pass(stack)
                for i, k in enumerate(HORIZONS):
                    P[(pop, direction, mname, k)] = s2[i]
                struct[(pop, direction, mname)] = (rate_q, rate_k)
                print(f"  {pop:<10}{direction:<5}{mname:<13}"
                      f"{100*rate_q:>16.3f}%{100*rate_k:>18.3f}%")
    print("  Rates are the share of (episode, horizon, quantile) predictions that")
    print("  enforcement MOVED. 0.000% means the model already satisfied the")
    print("  constraint. Climatology and kNN cannot violate either: np.quantile is")
    print("  non-decreasing in q, and the quantile of a running maximum is")
    print("  non-decreasing in k. Independent per-horizon fits have no such guarantee.")
    print()

    # ---- persist the ENFORCED predictions so no rerun ever refits ----
    if needs_save:
        carried = save_cache(cache, fp, P, keys)
        print(f"  [CACHE] wrote {os.path.basename(cache)} -- {n_fitted} new cell(s) "
              f"plus {n_loaded} reloaded, all post-enforcement, fingerprinted; "
              f"{carried} retired-model key(s) carried unchanged.")
        print(f"  Re-saving the reloaded cells is harmless: enforcement is a running")
        print(f"  maximum and is idempotent, so a clean cell passes through unchanged.")
        print()

    if args.stage == "run2":
        stage_run2(targets, pops, ctxs, P, full_sp, meta, args, t0)
        return

    # ---- calibration ----
    print("=" * 112)
    print("CALIBRATION -- this decides which models get their sharpness compared")
    print("=" * 112)
    print("  A coverage number is CONSISTENT if its day-clustered 95% interval contains")
    print("  the quantile it targets. Slices: predicted-magnitude decile, realized-")
    print("  magnitude decile, and early/late half of the held-out period.")
    print(f"  Admissible = all 5 aggregate quantiles consistent AND inconsistent slices")
    print(f"  no more than {SLICE_TOL:g}x the 5% expected by chance. The monotonicity and")
    print(f"  crossing constraints are ENFORCED above and are NOT part of this rule.")
    print()

    ncell = len(pops) * len(DIRECTIONS) * len(MODELS) * len(HORIZONS)
    nagg = len(QUANTILES)
    p_pass_agg = 0.95 ** nagg
    print(f"  CELL COUNT: {len(pops)} populations x {len(DIRECTIONS)} directions x "
          f"{len(MODELS)} models x {len(HORIZONS)} horizons = {ncell} cells.")
    print(f"  Each prints a PASS/fail and, below, a ratio against climatology. BOTH")
    print(f"  WILL BE READ AS FINDINGS whatever this run calls itself, so the chance")
    print(f"  rates are stated here rather than left to be worked out later.")
    print(f"  The aggregate screen is {nagg} interval checks at 95%, so a PERFECTLY")
    print(f"  calibrated cell clears it only {100*p_pass_agg:.1f}% of the time: about")
    print(f"  {ncell*(1-p_pass_agg):.0f} of {ncell} cells would fail on chance alone.")
    print(f"  This screen's error runs toward FALSE FAILURE, not false discovery.")
    print(f"  On the slice side, 5% of slices are expected inconsistent by chance and")
    print(f"  the tolerance is {SLICE_TOL:g}x that.")
    print()
    verdict, sharp, spread, realized_rows, yte_store = {}, {}, {}, {}, {}
    for pop in pops:
        ctx = ctxs[pop]
        boot = ctx["sp"].boot
        dte = ctx["day_test"]
        half = np.sort(np.unique(dte))[len(np.unique(dte)) // 2]
        tchunk = (dte >= half).astype(int)
        for direction in DIRECTIONS:
            print("-" * 112)
            print(f"  {pop} / {direction}")
            print("-" * 112)
            print(f"  {'model':<13}{'h':>6}" +
                  "".join(f"{'q'+str(int(q*100)):>14}" for q in QUANTILES) +
                  f"{'bad/tot':>10}{'worst':>8}{'realzd':>10}{'verdict':>8}")
            for mname, _ in MODELS:
                for k in HORIZONS:
                    pred = P[(pop, direction, mname, k)]
                    y = targets[(direction, k)][ctx["sub"]]
                    yte = y[ctx["test"]]
                    hits = yte[:, None] <= pred
                    pt, lo, hi = agg_coverage(hits, boot)
                    agg_ok = all(lo[j] <= QUANTILES[j] <= hi[j] for j in range(len(QUANTILES)))

                    bad = tot = 0
                    worst = 0.0
                    gp, ngp = deciles(pred[:, MEDIAN_IX])
                    gr, ngr = deciles(yte)
                    # A CONSTANT predictor has no predicted-magnitude spread, so
                    # deciles() returns one group and that slice family is skipped.
                    # That is legitimate -- there is nothing to slice on -- but it
                    # means climatology is judged on FEWER tests than the
                    # conditional models (15 against 65). Named in the output
                    # rather than left as a silent asymmetry.
                    const_pred = ngp < 2
                    # COUNTED: predicted-magnitude decile and time chunk.
                    for groups, ng in ((gp, ngp), (tchunk, 2)):
                        if ng < 2:
                            continue
                        spt, slo, shi, scnt = sliced_coverage(hits, groups, ng, boot)
                        for gi in range(ng):
                            if scnt[gi] == 0:
                                continue
                            for j, q in enumerate(QUANTILES):
                                tot += 1
                                if not (slo[gi, j] <= q <= shi[gi, j]):
                                    bad += 1
                                worst = max(worst, abs(spt[gi, j] - q))
                    # DIAGNOSTIC ONLY, never counted -- mechanically monotone.
                    dbad = dtot = 0
                    if ngr >= 2:
                        rpt, rlo, rhi, rcnt = sliced_coverage(hits, gr, ngr, boot)
                        for gi in range(ngr):
                            if rcnt[gi] == 0:
                                continue
                            for j, q in enumerate(QUANTILES):
                                dtot += 1
                                if not (rlo[gi, j] <= q <= rhi[gi, j]):
                                    dbad += 1
                        realized_rows[(pop, direction, mname, k)] = rpt[:, MEDIAN_IX]
                    chance = SLICE_TOL * 0.05 * max(tot, 1)
                    slice_ok = bad <= chance
                    # The structural constraints are ENFORCED above, not gated on.
                    ok = agg_ok and slice_ok
                    verdict[(pop, direction, mname, k)] = ok
                    cells = "".join(
                        f"{pt[j]:>8.3f}{'*' if not (lo[j] <= QUANTILES[j] <= hi[j]) else ' '}     "
                        for j in range(len(QUANTILES)))
                    print(f"  {mname:<13}{HLABEL[k]:>6}{cells}"
                          f"{bad:>5,}/{tot:<4,}{worst:>8.3f}"
                          f"{str(dbad)+'/'+str(dtot):>10}{'PASS' if ok else 'fail':>8}"
                          f"{'  const pred: no predicted-decile slice' if const_pred else ''}")
                    sharp[(pop, direction, mname, k)] = float(np.mean(
                        [_pinball(yte, pred[:, j], QUANTILES[j])
                         for j in range(len(QUANTILES))]))
                    yte_store[(pop, direction, k)] = yte
                    spread[(pop, direction, mname, k)] = float(
                        np.subtract(*np.percentile(pred[:, MEDIAN_IX], [75, 25])))
            print("  * = this aggregate coverage's day-clustered interval excludes its target")
            print("  bad/tot = COUNTED slices (predicted-magnitude decile + time chunk)")
            print("  worst   = largest |coverage - target| over the counted slices")
            print("  realzd  = realized-magnitude decile slices, DIAGNOSTIC, never counted")
            print("  NOTE the asymmetry: a constant predictor has no predicted-magnitude")
            print("  spread, so climatology is judged on 10 counted slices where the")
            print("  conditional models are judged on 60. Fewer tests is an easier screen.")
            print()

    # ---- sharpness, admissible models only ----
    print("=" * 112)
    print("SHARPNESS -- mean pinball across the 5 quantiles, as % of climatology")
    print("=" * 112)
    print("  ONLY among models that passed calibration at that cell. A model that")
    print("  failed calibration is omitted rather than shown losing or winning: a")
    print("  pinball number from a miscalibrated model is not interpretable.")
    print("  Below 100% = sharper than the unconditional envelope.")
    print("  EVERY RATIO CARRIES A DAY-CLUSTERED 95% INTERVAL. A ratio whose interval")
    print("  contains 100% is not distinguishable from climatology at this sample size.")
    print()
    for pop in pops:
        ctx = ctxs[pop]
        for direction in DIRECTIONS:
            print(f"  {pop} / {direction}")
            print(f"    {'model':<13}" +
                  "".join(f"{HLABEL[k]:>26}" for k in HORIZONS))
            for mname, _ in MODELS:
                row = ""
                for k in HORIZONS:
                    if not verdict[(pop, direction, mname, k)]:
                        row += f"{'(fail)':>26}"
                        continue
                    rt, rlo, rhi = pinball_ratio(
                        yte_store[(pop, direction, k)],
                        P[(pop, direction, mname, k)],
                        P[(pop, direction, "Climatology", k)],
                        ctx["sp"].boot)
                    row += f"{100*rt:>11.1f}% [{100*rlo:>5.1f},{100*rhi:>5.1f}] "
                print(f"    {mname:<13}{row}")
            print()

    # ---- prediction spread ----
    print("=" * 112)
    print("PREDICTION SPREAD -- does the model actually vary episode to episode?")
    print("=" * 112)
    print("  IQR of the predicted MEDIAN quantile across held-out episodes, in sigma.")
    print("  Climatology is 0.000 by construction: it predicts one number for every")
    print("  episode. A conditional model with a near-zero IQR is reproducing")
    print("  climatology with extra steps, however well it scores.")
    print()
    print("  REPORTED UNGATED, and deliberately. The brief gated this on calibration,")
    print("  but with no conditional model admissible anywhere the gated table is empty")
    print("  and the primary question -- do these five features describe the envelope")
    print("  at all -- goes unanswered. Spread is a property of the model's OUTPUT, not")
    print("  a skill claim: it says how much the prediction moves, never whether it")
    print("  moves correctly. A miscalibrated model with real spread and a miscalibrated")
    print("  model with none are different objects and the difference is worth seeing.")
    print("  Sharpness above stays gated, because pinball from a miscalibrated model")
    print("  genuinely is not interpretable as sharpness.")
    print("  cal = did that cell pass calibration.")
    print()
    for pop in pops:
        for direction in DIRECTIONS:
            print(f"  {pop} / {direction}")
            print(f"    {'model':<13}" + "".join(f"{HLABEL[k]:>14}" for k in HORIZONS))
            for mname, _ in MODELS:
                row = ""
                for k in HORIZONS:
                    v = spread[(pop, direction, mname, k)]
                    flag = "" if verdict[(pop, direction, mname, k)] else "~"
                    row += f"{v:>13.4f}{flag:<1}"
                print(f"    {mname:<13}{row}")
            print(f"    {'':<13}~ = that cell failed calibration; the spread is still "
                  f"what the model predicted")
            print()

    print("=" * 112)
    print("SOLVER FALLBACKS -- named, not absorbed")
    print("=" * 112)
    if not LINEAR_FALLBACKS:
        print("  none. Every Linear QR cell solved unpenalised (alpha=0).")
    else:
        print(f"  {len(LINEAR_FALLBACKS)} of {len(QUANTILES)*len(HORIZONS)*len(DIRECTIONS)*2}"
              f" Linear QR cells needed alpha=1e-8 to solve. Those cells are a")
        print(f"  very slightly penalised model, not the unpenalised one:")
        for tag, q, al in LINEAR_FALLBACKS:
            print(f"    {tag}  q={q}  alpha={al:g}")
    print()
    print("=" * 112)
    print(f"[{time.time()-t0:.0f}s]  target source {args.target_source}.  "
          f"No gate, no null, no direction claim, no strategy.")
    print("=" * 112)


if __name__ == "__main__":
    main()
