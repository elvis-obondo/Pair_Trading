"""HL-MODEL1 S1: preprocessing fitted on the fit rows only (R4, R8).

Shared by the sizing script (s1_sizing.py) and the full run (Step 2) -- one implementation, so Step 2
times and fits exactly what Step 1 measured.

Order (R8c): drop degenerate columns on the RAW fit rows (harness.drop_degenerate_for_fold's rule), then
clip (0.1%/99.9% quantiles of finite values), then standardise (mean/SD of finite values). A column whose
SD is 0 after clipping is also dropped, logged separately. NaN is set to 0 last; every column with any NaN
in the fit rows gets a missing indicator (0/1, not clipped/standardised, but penalised -- R8b). ticker_a
and ticker_b are never part of this numeric pipeline (R5): they are one-hot only, levels = the coins seen
in the fit rows for that leg, an unseen coin is the all-zero "unseen" level (A6). All preprocessing
statistics are computed at EVENT level (R8a) -- this module operates on one row per event throughout, the
hazard-row expansion happens only in s1_model.py's fit, never here.

MEMORY (planner's finding, S1 review round 3 -- the sizing run's own numbers): fold 7's train set has
2,368 OUTPUT features (904 of the 1,068 surviving numeric columns carry at least one NaN, so get their
own indicator column, plus 198+198 ticker one-hot levels). The PREVIOUS version took `fit_preprocessing`/
`apply_preprocessing` a pre-loaded (n x 1,091) raw matrix; holding that (17.4 GB) alongside
apply_preprocessing's (n x 2,368) float32 output (37.7 GB) pushed peak RSS to 55.25 GB on train alone --
the refit (train+val, ~1.27x rows) would scale toward ~70 GB, over this machine's 62 GB.

FIX (v1): both functions took `event_ids` + `cols` and loaded ONE raw column at a time directly from the
cache (harness.load_features_cached), never a (n x len(cols)) matrix.

FIX (v2, checker's finding, S1 review round 4 -- BLOCKING): the cache's .npy is row-major, (6,697,756 x
1,091) float32 -- every row is one contiguous ~4.3 KB span. Reading a SINGLE column for ~4M scattered
event_ids (`mm[np.ix_(ids, [j])]`) therefore touches a page of EVERY one of those rows -- about 17 GB of
page-table work -- and doing that 1,091 times (for fit) and again (for apply) would cost hours, not
minutes, and call harness.check_inputs (a csv read + sha256) 1,091+ times over. Columns are now read in
BLOCKS (BLOCK_SIZE=64, ~1 GB per block at fold 7's row count) via one `load_features_cached` call per
block instead of per column -- about 17 calls instead of 1,091+, each one doing the SAME whole-row page
walk but for 64 columns' worth of use instead of 1's. Exact quantiles, mean, SD, degenerate check and
indicator are still computed per COLUMN, just sliced out of the block instead of loaded alone -- same
numbers either way, this only changes how many cache calls fetch them.

Either version's peak RSS is bounded by the OUTPUT array plus one block's worth of raw data (~1 GB), not
by holding the whole raw matrix (17.4 GB) alongside the whole output (37.7 GB on fold 7's train set, which
is what pushed peak RSS to 55.25 GB before this module existed in its current form). Same statistics, same
output, same column order throughout -- a memory/IO restructuring only, never a rule change.

`drop_degenerate_numpy` (used only by s1_preprocess_proof.py's small-matrix proof) and `_is_degenerate`
(the column-at-a-time rule both it and `fit_preprocessing` apply) share the exact same decision: degenerate
if the column has zero finite values, or at most one distinct finite value -- harness.drop_degenerate_for_
fold's rule. s1_preprocess_proof.py proves `_is_degenerate` matches harness.drop_degenerate_for_fold
exactly on a small shared frame.
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import harness as H  # noqa: E402

TICKER_COLS = ("ticker_a", "ticker_b")
BLOCK_SIZE = 64   # columns per cache call -- ~1 GB at fold 7's row count (checker's ruling, S1 review round 4)


def _is_degenerate(col):
    finite = ~np.isnan(col)
    return finite.sum() == 0 or len(np.unique(col[finite])) <= 1


def drop_degenerate_numpy(X, cols, col_indices=None):
    """Same rule as `_is_degenerate` / harness.drop_degenerate_for_fold's numeric branch, for a small,
    already-in-memory matrix (s1_preprocess_proof.py's proof only -- fit_preprocessing itself streams
    columns from the cache and never calls this). `col_indices[k]` is column `cols[k]`'s position within
    `X` (defaults to 0..len(cols)-1)."""
    if col_indices is None:
        col_indices = np.arange(len(cols))
    dropped = [c for k, c in enumerate(cols) if _is_degenerate(X[:, col_indices[k]])]
    kept = [c for c in cols if c not in dropped]
    print(f"[S1-PREPROCESS] degenerate-on-raw-fit-rows columns dropped: {len(dropped)} of {len(cols)}"
          + (f" ({dropped})" if dropped else ""), flush=True)
    return kept, dropped


def _blocks(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


def fit_preprocessing(event_ids, cols, q_lo=0.001, q_hi=0.999, block_size=BLOCK_SIZE):
    """Fits every statistic on the rows named by `event_ids` (train for grid selection, train+val for the
    refit -- R1, R4): reads numeric columns in BLOCKS of `block_size` from the cache (one
    harness.load_features_cached call per block, not per column -- checker's ruling, S1 review round 4),
    computes each column's degenerate check and (if kept) its clip/mean/SD/has-NaN by slicing it out of
    the block, then discards the block before the next -- never holds the raw matrix's full width at once.
    Returns a `stats` dict consumed by `apply_preprocessing`; never apply one fold's/split's stats to
    another fold's rows."""
    numeric_cols = [c for c in cols if c not in TICKER_COLS]
    degenerate_dropped = []
    kept_numeric, clip_lo, clip_hi, mean, sd, has_nan = [], [], [], [], [], []
    for block_cols in _blocks(numeric_cols, block_size):
        block, _ = H.load_features_cached(event_ids, block_cols)
        for j, c in enumerate(block_cols):
            col = block[:, j]
            if _is_degenerate(col):
                degenerate_dropped.append(c)
                continue
            finite = ~np.isnan(col)
            has_nan_c = not finite.all()
            vals = col[finite]
            lo, hi = np.quantile(vals, [q_lo, q_hi])
            clipped = np.clip(vals, lo, hi)
            kept_numeric.append(c)
            clip_lo.append(lo); clip_hi.append(hi)
            mean.append(clipped.mean()); sd.append(clipped.std())
            has_nan.append(has_nan_c)
        del block
    print(f"[S1-PREPROCESS] degenerate-on-raw-fit-rows columns dropped: {len(degenerate_dropped)} of "
          f"{len(numeric_cols)}" + (f" ({degenerate_dropped})" if degenerate_dropped else ""), flush=True)
    clip_lo, clip_hi, mean, sd = map(np.array, (clip_lo, clip_hi, mean, sd))
    has_nan = np.array(has_nan)

    sd0 = sd == 0
    sd0_dropped = [c for c, bad in zip(kept_numeric, sd0) if bad]
    print(f"[S1-PREPROCESS] SD-0-after-clip columns dropped: {len(sd0_dropped)} of {len(kept_numeric)}"
          + (f" ({sd0_dropped})" if sd0_dropped else ""), flush=True)
    keep2 = ~sd0
    final_numeric = [c for c, k in zip(kept_numeric, keep2) if k]
    clip_lo, clip_hi, mean, sd = clip_lo[keep2], clip_hi[keep2], mean[keep2], sd[keep2]
    has_nan = has_nan[keep2]
    nan_indicator_cols = [c for c, hn in zip(final_numeric, has_nan) if hn]

    ticker_block, _ = H.load_features_cached(event_ids, list(TICKER_COLS))
    ticker_levels = {}
    for j, tcol in enumerate(TICKER_COLS):
        raw = ticker_block[:, j]
        finite = raw[~np.isnan(raw)]
        ticker_levels[tcol] = sorted(int(v) for v in np.unique(finite))
    del ticker_block

    return {
        "fit_cols": list(cols),
        "final_numeric": final_numeric,
        "clip_lo": clip_lo, "clip_hi": clip_hi, "mean": mean, "sd": sd,
        "nan_indicator_cols": nan_indicator_cols,
        "degenerate_dropped": degenerate_dropped,
        "sd0_dropped": sd0_dropped,
        "ticker_levels": ticker_levels,
    }


def apply_preprocessing(event_ids, cols, stats, block_size=BLOCK_SIZE):
    """Transforms the rows named by `event_ids` with stats' FIXED, already-fitted values -- never refit
    here. Output column order: standardised numeric columns, missing indicators, ticker_a one-hot, ticker_b
    one-hot. An unseen coin code (not in `stats`'s fit-rows levels for that leg) gets all-zero one-hot
    columns (A6's "unseen" level). Numeric columns are read in BLOCKS of `block_size` (one
    load_features_cached call per block, not per column -- checker's ruling, S1 review round 4); each
    column is used for BOTH its standardised value and (if applicable) its missing indicator from the same
    block, never a second read for the indicator. The output array is preallocated once; no raw matrix of
    the full column width is ever held alongside it."""
    assert list(cols) == stats["fit_cols"], "apply_preprocessing: column order does not match the fitted stats"
    n = len(event_ids)
    final_numeric = stats["final_numeric"]
    nan_indicator_cols = stats["nan_indicator_cols"]
    levels_a = stats["ticker_levels"]["ticker_a"]
    levels_b = stats["ticker_levels"]["ticker_b"]
    n_final = len(final_numeric)
    n_ind = len(nan_indicator_cols)
    n_out = n_final + n_ind + len(levels_a) + len(levels_b)

    out_cols = (list(final_numeric) + [f"{c}__isnan" for c in nan_indicator_cols]
                + [f"ticker_a__code{lv}" for lv in levels_a] + [f"ticker_b__code{lv}" for lv in levels_b])
    X_out = np.empty((n, n_out), dtype=np.float32)
    ind_out_pos = {c: n_final + i for i, c in enumerate(nan_indicator_cols)}

    k0 = 0
    for block_cols in _blocks(final_numeric, block_size):
        block, _ = H.load_features_cached(event_ids, block_cols)
        for j, c in enumerate(block_cols):
            k = k0 + j
            col = block[:, j]
            nan_mask = np.isnan(col)
            clipped = np.clip(col, stats["clip_lo"][k], stats["clip_hi"][k])
            z = (clipped.astype(np.float64) - stats["mean"][k]) / stats["sd"][k]
            z[nan_mask] = 0.0
            X_out[:, k] = z
            if c in ind_out_pos:
                X_out[:, ind_out_pos[c]] = nan_mask
        del block
        k0 += len(block_cols)

    base = n_final + n_ind
    ticker_block, _ = H.load_features_cached(event_ids, list(TICKER_COLS))
    for j, (tcol, levels) in enumerate((("ticker_a", levels_a), ("ticker_b", levels_b))):
        raw_codes = ticker_block[:, j]
        for level in levels:
            X_out[:, base] = (raw_codes == level)
            base += 1
    del ticker_block

    return X_out, out_cols
