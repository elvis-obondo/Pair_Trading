"""Five environment features at entry, for the 60,000 existing dislocations.

    .venv/bin/python research/dislocation_model/envfeat.py

Writes research/datasets/envfeat.npz: X (60000, 5) float32 and names (5,).
No target, no model, no scoring. The deliverable is the matrix.

WHY FIVE. Feature count has already been falsified as the lever here: 18 -> 21 ->
41 -> 62, and the 62-feature combination scored ZERO hits on 33 cells against 1.7
expected false positives. These five are chosen for what they measure, not for
coverage.

    vol_48      SCALE      how big the 30-minute steps were
    vratio      SHAPE      choppy (long path, small displacement) vs trending
    vol_slope   TIMING     was volatility arriving or receding at entry
    sandwich    COHESION   how badly the two legs fail to tick together
    off_mark    BASIS      how far each leg traded from its own mark

HELD OUT DELIBERATELY, do not add them back:
  |z_entry|   cleanest null in the project (AUC 0.5101) and the input that
              manufactured the unfolded-AUC artifact
  a beta feature   absorbed -- vol_48 is the spread's volatility, already a
              function of both legs and the hedge ratio
  1-minute, open interest, funding rate   not available at usable coverage

THE JOIN IS BY POSITION, AND THAT IS NOT LAZINESS. `mkdisloc.py` permutes a
seeded draw over `universe_panel.tradeable_pairs(cols)`, so rebuilding
disloc.npz on today's panel returns a DIFFERENT 60,000 and nothing would be
comparable. So this joins row-for-row onto the existing disloc_meta.parquet and
never regenerates it. `meta.bar_index` was checked against today's panel for all
60,000 rows: the 43 bars the panel has gained since are all at the END, so the
indices still resolve. The validator re-asserts this on every run rather than
trusting it.

NO LOOKAHEAD, AUDITED NOT ASSUMED. Bars are labelled by OPEN time, so a 30-minute
bar labelled T is observed at T+30 and carries the close at T+30. The entry bar is
index `i` with label T; information is observable through T+30.

    features 1-3   read `windows`, which mkdisloc built from bars [i-335, i].
                   Max index touched = i.
    sandwich       reads 30m high/low at [i-95, i]. Max index touched = i.
    off_mark       reads 1h mark labelled <= T-60 and the 30m close one index
                   later, so its max index is strictly BEFORE the entry bar.
                   TWO CASES, because mark labels are hourly and the entry grid
                   is half-hourly:
                     T on the hour  -- T-60 IS a mark label. Last mark read is
                                       T-60; paired 30m close at i-1.
                     T on the :30   -- T-60 is also :30 and is NOT a mark label,
                                       so the code steps back one more slot to
                                       T-90. Last mark read is T-90; paired 30m
                                       close at i-2.
                   The :30 case gives up an hour of history. That is CONSERVATIVE,
                   not leaky, and it is deliberately left alone: widening it to
                   recover the hour would change the feature.

The script records the maximum panel index it touches PER ROW and asserts it
equals the entry index. `external.py` did this and it is the single most
important thing carried over from it.

SIGN FOLDING. Every feature is computed from the sign-folded spread, so the entry
dislocation is positive. Features 1-3 are built from |steps| or standard
deviations and are invariant to a global sign flip by construction. `sandwich`
and `off_mark` are made invariant explicitly: the folded spread's within-bar
MAXIMUM is the hi bound when s=+1 and the negated lo bound when s=-1, and
off_mark is an absolute deviation. The validator tests invariance numerically on
a flipped twin rather than taking the argument on trust.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd

import paths
import universe_panel

NAMES = ["vol_48", "vratio", "vol_slope", "sandwich", "off_mark"]

VOL_BARS = 48       # scale: recency beat precision in this project's own test
RATIO_BARS = 96     # the ENTRY geometry window, not the 336-bar model-input window
SLOPE_FAST = 16
SLOPE_SLOW = 32
SANDWICH_BARS = 96
MARK_HOURS = 48     # 96 x 30min of wall-clock time

RAW_DIR = os.path.join(os.path.dirname(paths.RESEARCH), "user_data", "data", "okx", "futures")


# Divisor that makes `vratio` equal 1 for iid increments, BY SIMULATION.
# 200,000 driftless gaussian walks of 96 points, seed 20261009, median of
# step_sd/level_sd = 0.294386, so the divisor is its reciprocal.
IID_VRATIO_DIVISOR = {96: 3.396899}


def iid_vratio_norm(n, draws=200_000, seed=20261009):
    """Divisor that makes the MEDIAN `vratio` equal 1 for iid increments.

    THE ANALYTIC CONSTANT IS WRONG FOR THIS PURPOSE AND WAS SHIPPED BRIEFLY.
    For a driftless random walk of n points with step sd s, the expected sample
    variance of the LEVELS about their own mean is s^2 (n^2-1)/(6n). (Derived:
    E[(1/n)SUM W_t^2] = s^2 (n-1)/2 and E[Wbar^2] = s^2 (n-1)(2n-1)/(6n).) That
    gives sqrt((n^2-1)/(6n)) = 3.999783 at n=96, and it is the right constant for
    the ratio of the EXPECTATIONS.

    The feature is the EXPECTATION OF A RATIO, which is not the same thing. A
    random walk's level sd is dominated by its own realised path and is highly
    variable, so E[1/level_sd] sits well above 1/E[level_sd]. Simulated, the
    analytic divisor leaves the iid ratio centred on 1.186 (median) / 1.241
    (mean) instead of 1.0 -- 17.7% too large. The simulation check in
    validate_dislocation_harness.py is what caught it.

    So the shipped constant is simulated, not derived. Median rather than mean:
    the ratio is right-skewed and the median is the stable centre.
    """
    if n in IID_VRATIO_DIVISOR:
        return IID_VRATIO_DIVISOR[n]
    rg = np.random.default_rng(seed)
    acc = []
    for _ in range(max(1, draws // 5000)):
        st = rg.standard_normal((5000, n - 1))
        lv = np.concatenate([np.zeros((5000, 1)), np.cumsum(st, axis=1)], axis=1)
        acc.append(np.diff(lv, axis=1).std(1) / lv.std(1))
    return 1.0 / float(np.median(np.concatenate(acc)))


def _raw_panel(field, panel_index, tickers, timeframe="30m", suffix="futures"):
    """One raw OHLC field, log-transformed and reindexed onto the panel's grid.

    The normalized store (user_data/normalized/) carries `close` only, so highs,
    lows and marks have to come from the raw feathers. 30-minute OKX data already
    lands exactly on the grid, so `_snap_to_grid` is a no-op for it and a plain
    reindex is equivalent -- but a reindex also inherits the FACTOR_ONLY lead trim
    and leaves genuine gaps as NaN instead of fabricating them.
    """
    out = pd.DataFrame(index=panel_index, columns=tickers, dtype=float)
    for t in tickers:
        f = os.path.join(RAW_DIR, f"{t}_USDT_USDT-{timeframe}-{suffix}.feather")
        if not os.path.exists(f):
            continue
        d = pd.read_feather(f, columns=["date", field])
        ix = pd.to_datetime(d["date"], utc=True).dt.tz_localize(None)
        s = pd.Series(np.log(d[field].to_numpy(float)), index=ix)
        s = s[~s.index.duplicated(keep="last")]
        out[t] = s.reindex(panel_index)
    return out.to_numpy(float)


def _mark_on_grid(panel_index, tickers):
    """1-hour mark close, log, placed on the 30-minute grid.

    A 1h bar labelled t spans t..t+60, so its close is observed at t+60. Only
    :00 grid slots carry a value; :30 slots stay NaN and are never filled, because
    forward-filling a mark would invent an observation.
    """
    out = pd.DataFrame(index=panel_index, columns=tickers, dtype=float)
    for t in tickers:
        f = os.path.join(RAW_DIR, f"{t}_USDT_USDT-1h-mark.feather")
        if not os.path.exists(f):
            continue
        d = pd.read_feather(f, columns=["date", "close"])
        ix = pd.to_datetime(d["date"], utc=True).dt.tz_localize(None)
        s = pd.Series(np.log(d["close"].to_numpy(float)), index=ix)
        s = s[~s.index.duplicated(keep="last")]
        out[t] = s.reindex(panel_index)
    return out.to_numpy(float)


def build(verbose=True, flip=False, W=None, M=None):
    """Returns (X, NAMES, audit) where audit carries the per-row index bounds.

    W and M default to disloc.npz's windows and disloc_meta.parquet. Passing
    them computes the SAME five features for any other set of entries -- e.g.
    backtest trades (meta_label.py) -- through this exact code, so there is one
    definition of every feature. M needs bar_index, entry_time, ticker_a,
    ticker_b, beta, sigma, z_at_entry; W the 336-bar sigma-unit window built as
    mkdisloc builds it.

    flip=True negates the SPREAD everywhere -- the window, the within-bar bounds
    (whose hi and lo swap under negation) and the close -- which also flips every
    row's entry sign. Folding is then (-s)*(-X) = s*X, so every feature must come
    back bit-identical. That is the sign-folding consistency test, and it runs
    through this same code path rather than a re-derivation that could agree with
    a shared mistake.
    """
    t0 = time.time()
    g = -1.0 if flip else 1.0
    if W is None:
        W = np.load(paths.DISLOC)["windows"]
    W = np.asarray(W).astype(np.float64)
    if M is None:
        M = pd.read_parquet(paths.META)
    N = len(M)

    panel = universe_panel.drop_forming_bars(universe_panel.load_panel())
    pidx = pd.to_datetime(panel.index)
    cols = list(panel.columns)
    ixc = {c: k for k, c in enumerate(cols)}
    CLOSE = panel.to_numpy(float)

    J = M.bar_index.to_numpy(int)
    entry = pd.to_datetime(M.entry_time)
    if not (pidx[J] == entry).all():
        bad = int((pidx[J] != entry).sum())
        raise SystemExit(
            f"JOIN BROKEN: meta.bar_index no longer resolves to entry_time on {bad} of "
            f"{N} rows. The panel's leading rows have changed. Do NOT rebuild "
            f"disloc.npz to fix this -- see the module docstring.")

    ja = M.ticker_a.map(ixc).to_numpy(int)
    jb = M.ticker_b.map(ixc).to_numpy(int)
    beta = M.beta.to_numpy(float)
    sig = M.sigma.to_numpy(float)
    s = np.sign(M.z_at_entry.to_numpy(float))
    s[s == 0] = 1.0
    s = g * s

    if verbose:
        print(f"[DATA] {N:,} dislocations, panel {CLOSE.shape}, "
              f"entry bars {J.min()}..{J.max()}", flush=True)
        print(f"[DATA] beta negative on {int((beta < 0).sum()):,} rows "
              f"({100*(beta < 0).mean():.1f}%) -- the sandwich bound is sign-corrected",
              flush=True)

    # Per-row maximum 30-minute panel index touched, CARRIED PER FEATURE FAMILY.
    # A single shared array was misleading: features 1-3 legitimately reach the
    # entry bar, so `max(touch) == entry` was true by construction the moment they
    # ran, and the aggregate check then read as proof that off_mark reaches the
    # entry bar too. It does not -- see the off_mark note below. The aggregate
    # "never exceeds" check stays; it is the live one.
    touch_win = np.full(N, -1, np.int64)      # features 1-3, from `windows`
    touch_sw = np.full(N, -1, np.int64)       # sandwich, from 30m high/low
    touch_om = np.full(N, -1, np.int64)       # off_mark, from 1h mark + 30m close

    # ---------------------------------------------------------------- 1-3
    # `windows` is already in sigma units of the entry bar's frozen geometry, and
    # mkdisloc built it from bars [i-335, i]. Sign folding cancels in every one of
    # these three (|s*d| = |d|, sd(s*x) = sd(x)), which is why they are invariant.
    Wf = (g * W) * s[:, None]
    dW = np.diff(Wf, axis=1)                      # 335 steps, index -1 = into bar i
    touch_win = np.maximum(touch_win, J)

    vol_48 = np.abs(dW[:, -VOL_BARS:]).mean(1)

    lvl = Wf[:, -RATIO_BARS:]                     # 96 levels
    stp = np.diff(lvl, axis=1)                    # the 95 steps within them
    vratio = (stp.std(1) / np.clip(lvl.std(1), 1e-12, None)) * iid_vratio_norm(RATIO_BARS)

    fast = dW[:, -SLOPE_FAST:].std(1)
    slow = dW[:, -(SLOPE_FAST + SLOPE_SLOW):-SLOPE_FAST].std(1)
    vol_slope = fast / np.clip(slow, 1e-12, None)

    if verbose:
        print(f"[1-3 ] from windows+meta, {time.time()-t0:.0f}s   "
              f"vratio iid divisor {iid_vratio_norm(RATIO_BARS):.5f}", flush=True)

    # ---------------------------------------------------------------- 4
    HI = _raw_panel("high", pidx, cols)
    LO = _raw_panel("low", pidx, cols)
    if verbose:
        print(f"[4   ] high/low panels loaded, {time.time()-t0:.0f}s", flush=True)

    # offsets i-95 .. i, inclusive
    off = np.arange(-(SANDWICH_BARS - 1), 1)
    sandwich = np.empty(N)
    bound_viol = 0
    worst_viol = 0.0
    c2c_mean = np.empty(N)
    CH = 5000
    for a in range(0, N, CH):
        b = min(a + CH, N)
        rows = slice(a, b)
        I = J[rows, None] + off[None, :]           # (chunk, 96)
        qa, qb = ja[rows, None], jb[rows, None]
        be = beta[rows, None]
        ha, la_ = HI[I, qa], LO[I, qa]
        hb, lb = HI[I, qb], LO[I, qb]
        ca, cb = CLOSE[I, qa], CLOSE[I, qb]
        # max/min of (a - beta*b) over the bar, correct for EITHER beta sign:
        # beta > 0 wants low_b for the max; beta < 0 wants high_b.
        other_hi = np.where(be > 0, lb, hb)
        other_lo = np.where(be > 0, hb, lb)
        sp_hi = ha - be * other_hi
        sp_lo = la_ - be * other_lo
        sp_cl = ca - be * cb
        if flip:
            sp_hi, sp_lo, sp_cl = -sp_lo, -sp_hi, -sp_cl
        ss = s[rows, None]
        # the FOLDED spread's within-bar maximum, and its close
        f_hi = np.where(ss > 0, sp_hi, -sp_lo)
        f_cl = ss * sp_cl
        gap = f_hi - f_cl
        fin = np.isfinite(gap)
        bad = fin & (gap < -1e-12)
        bound_viol += int(bad.sum())
        if bad.any():
            worst_viol = min(worst_viol, float(gap[bad].min()))
        sandwich[rows] = np.nanmean(gap, axis=1) / sig[rows]
        # reported diagnostic only, not a feature: the close-to-close lower bound
        c2c_mean[rows] = np.nanmean(np.abs(np.diff(f_cl, axis=1)), axis=1) / sig[rows]
        touch_sw[rows] = np.maximum(touch_sw[rows], I.max(axis=1))

    if verbose:
        print(f"[4   ] sandwich done, {time.time()-t0:.0f}s   "
              f"bound violations {bound_viol:,} (worst {worst_viol:.2e})", flush=True)

    # ---------------------------------------------------------------- 5
    MK = _mark_on_grid(pidx, cols)
    on_hour = np.asarray(pidx.minute) == 0
    if verbose:
        print(f"[5   ] mark panel loaded, {time.time()-t0:.0f}s   "
              f"{int(on_hour.sum()):,} of {len(pidx):,} grid slots are hourly labels",
              flush=True)

    # The last 1h mark label at or before T-60. A mark label is a :00 slot, so
    # from i-2 step back at most one slot to land on the hour.
    j0 = J - 2
    j0 = np.where(on_hour[np.clip(j0, 0, None)], j0, j0 - 1)
    hoff = -2 * np.arange(MARK_HOURS)              # 0, -2, -4, ... 48 hourly bars
    off_mark = np.empty(N)
    aw = 1.0 / (1.0 + np.abs(beta))
    bw = np.abs(beta) / (1.0 + np.abs(beta))
    for a in range(0, N, CH):
        b = min(a + CH, N)
        rows = slice(a, b)
        Km = j0[rows, None] + hoff[None, :]        # mark label slots
        Kc = Km + 1                                # the 30m bar that CLOSES with it
        qa, qb = ja[rows, None], jb[rows, None]
        da = np.abs(CLOSE[Kc, qa] - MK[Km, qa])
        db = np.abs(CLOSE[Kc, qb] - MK[Km, qb])
        # DIVIDED BY SIGMA, same as vol_48 and sandwich. Unscaled, 46.4% of this
        # column's variance was BETWEEN-PAIR against 5.5-21.4% for the other four.
        # The split is temporal, so all 3,000 pairs sit in both the fit and the
        # held-out block, and a tree can route on an unscaled off_mark to recover
        # pair identity -- which scores in held out and does not survive new
        # pairs. It is a basis feature and it should measure basis.
        off_mark[rows] = (np.nanmean(aw[rows, None] * da + bw[rows, None] * db, axis=1)
                          / sig[rows])
        touch_om[rows] = np.maximum(touch_om[rows], Kc.max(axis=1))

    X = np.column_stack([vol_48, vratio, vol_slope, sandwich, off_mark]).astype(np.float32)
    touch = np.maximum(np.maximum(touch_win, touch_sw), touch_om)
    audit = dict(touch=touch, touch_win=touch_win, touch_sw=touch_sw, touch_om=touch_om,
                 entry=J, bound_viol=bound_viol, worst_viol=worst_viol,
                 c2c_mean=c2c_mean, n_panel=len(pidx), on_hour=on_hour, j0=j0,
                 key_a=M.ticker_a.to_numpy(str), key_b=M.ticker_b.to_numpy(str),
                 key_t=entry.to_numpy("datetime64[ns]"))
    if verbose:
        print(f"[5   ] off_mark done, {time.time()-t0:.0f}s", flush=True)
    return X, list(NAMES), audit


def between_pair_share(X, names, meta):
    """Share of each column's variance that is BETWEEN pair, not within.

    Eta-squared on the pair grouping: SS_between / SS_total. This is the number
    that moved off_mark onto a sigma scale. The split is TEMPORAL, so every pair
    appears in both the fit and the held-out block; a column that is mostly
    between-pair is partly a pair label, and a tree can route on it to recover
    pair identity. That scores in held out and does not survive new pairs.

    Reported, not gated. A feature SHOULD carry some cross-sectional variation --
    the point is to know how much.
    """
    key = meta.ticker_a.astype(str) + "/" + meta.ticker_b.astype(str)
    codes, _ = pd.factorize(key)
    k = int(codes.max()) + 1
    out = {}
    for j, nm in enumerate(names):
        c = X[:, j].astype(np.float64)
        ok = np.isfinite(c)
        cc, co = c[ok], codes[ok]
        n = np.bincount(co, minlength=k).astype(float)
        tot = np.bincount(co, weights=cc, minlength=k)
        live = n > 0
        gm = cc.mean()
        grp = np.zeros(k)
        grp[live] = tot[live] / n[live]
        ss_between = float((n[live] * (grp[live] - gm) ** 2).sum())
        ss_total = float(((cc - gm) ** 2).sum())
        out[nm] = ss_between / ss_total if ss_total > 0 else np.nan
    return out, k


def report(X, names, audit, meta=None):
    """Finiteness counts and percentiles. Nothing is nan_to_num'd on the way in."""
    N = len(X)
    print()
    print("=" * 96)
    print("FINITENESS -- reported, never silently repaired")
    print("=" * 96)
    print(f"{'column':<12}{'NaN':>9}{'+inf':>7}{'-inf':>7}{'finite':>9}{'% finite':>10}")
    for k, nm in enumerate(names):
        c = X[:, k]
        nan = int(np.isnan(c).sum())
        pin = int(np.isposinf(c).sum())
        nin = int(np.isneginf(c).sum())
        fin = int(np.isfinite(c).sum())
        print(f"{nm:<12}{nan:>9,}{pin:>7,}{nin:>7,}{fin:>9,}{100*fin/N:>9.2f}%")

    print()
    print("=" * 96)
    print("PERCENTILES (finite rows only) -- a broken column is visible here and almost nowhere else")
    print("=" * 96)
    qs = [1, 5, 25, 50, 75, 95, 99]
    print(f"{'column':<12}" + "".join(f"{'p'+str(q):>12}" for q in qs) + f"{'mean':>12}{'sd':>12}")
    for k, nm in enumerate(names):
        c = X[:, k]
        c = c[np.isfinite(c)]
        if not len(c):
            print(f"{nm:<12}{'ALL NON-FINITE':>12}")
            continue
        v = np.percentile(c, qs)
        print(f"{nm:<12}" + "".join(f"{x:>12.5f}" for x in v)
              + f"{c.mean():>12.5f}{c.std():>12.5f}")

    if meta is not None:
        print()
        print("=" * 96)
        print("BETWEEN-PAIR VARIANCE SHARE -- eta-squared on the pair grouping")
        print("=" * 96)
        shares, npair = between_pair_share(X, names, meta)
        print(f"  {npair:,} distinct pairs. The split is TEMPORAL, so every pair sits in")
        print(f"  BOTH blocks: a mostly between-pair column is partly a pair label.")
        print(f"  {'column':<12}{'between-pair':>14}")
        for nm in names:
            print(f"  {nm:<12}{100*shares[nm]:>13.1f}%")

    print()
    print("=" * 96)
    print("NO LOOKAHEAD")
    print("=" * 96)
    touch, entry = audit["touch"], audit["entry"]
    over = int((touch > entry).sum())
    print(f"  rows where max index touched > entry index:        {over:,}  (must be 0)")
    print()
    print(f"  max index touched RELATIVE TO THE ENTRY BAR, per feature family:")
    for lbl, key in (("features 1-3 (windows)", "touch_win"),
                     ("sandwich (30m high/low)", "touch_sw"),
                     ("off_mark (1h mark + close)", "touch_om")):
        d = audit[key] - entry
        u, c = np.unique(d, return_counts=True)
        spread = "  ".join(f"i{v:+d}: {n:,}" for v, n in zip(u, c))
        print(f"    {lbl:<28}{spread}")
    print(f"  only features 1-3 and sandwich reach the entry bar. off_mark stops")
    print(f"  short, and that is the point of carrying these separately.")
    print(f"  max entry index {entry.max():,} of a {audit['n_panel']:,}-bar panel; "
          f"{audit['n_panel'] - 1 - entry.max():,} later bars exist and are UNUSED")
    print(f"  sandwich bound violations (upper < folded close):  {audit['bound_viol']:,}  (must be 0)")
    c2c = audit["c2c_mean"][np.isfinite(audit["c2c_mean"])]
    sw = X[:, names.index("sandwich")]
    sw = sw[np.isfinite(sw)]
    print()
    print(f"  the two bounds on within-bar travel, both in sigma:")
    print(f"    mean |close-to-close| move   {c2c.mean():.5f}   LOWER bound")
    print(f"    mean sandwich gap            {sw.mean():.5f}   UPPER bound minus close")


if __name__ == "__main__":
    X, names, audit = build()
    report(X, names, audit, meta=pd.read_parquet(paths.META))
    # The join key goes in the FILE, not just the audit. envfeat is joined onto
    # disloc_meta BY POSITION, and a positional join with no stored key is how
    # silent misalignment happens -- the validator asserts these three against
    # meta element-wise for all 60,000 rows, not on a sample.
    np.savez_compressed(paths.ENVFEAT, X=X, names=np.array(names),
                        ticker_a=audit["key_a"], ticker_b=audit["key_b"],
                        entry_time=audit["key_t"])
    print()
    print(f"[WROTE] {paths.ENVFEAT}  {X.shape} {X.dtype}")
    print(f"[NEXT ] .venv/bin/python research/validate_dislocation_harness.py")
