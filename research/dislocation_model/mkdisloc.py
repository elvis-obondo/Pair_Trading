"""The dislocation set, on Hyperliquid's trade-built 30-minute bars (HL-BUILD2).

Straight from the 30-minute panel -- no backtest, no paths.npz. Coins list and
delist at different dates, so each pair is sliced to the overlap of its two
coins' finite regions, [max(first), min(last)].

ARCHIVE GAPS (user, 2026-10-15). A 30m close is NaN only when it is unknown: a
hole lies after the bar's last trade (rule iii, build2_assemble.py). For the
NaN closes that remain, each pair's overlap is split into maximal NaN-free
segments (option i) and every segment runs on its own: geometry, adaptive
threshold and windows restart after a NaN close and none spans one. Nothing is
filled. Each segment pays its own warm-up.

GEOMETRY, and the two windows are different:
  entry trigger + frozen geometry : 96 bars  (rolling_spread.ENTRY_WINDOW_DAYS=2)
  SDE fit window                  : 336 bars (7 days -- Phase 1's largest win)

TRIGGER (user, 2026-10-15; replaces the fixed |z| >= 3.0, which came from a
2026-09 profit sweep on the old 7-day OLS geometry and was never re-checked on
the symmetric 2-day geometry). "Unusual for this pair over its own 2 days":
  threshold_i = 99th percentile (numpy linear) of |z| over bars i-96..i-1
                (excludes bar i, so the bar cannot set its own bar);
  fire at i when |z_i| > threshold_i and |z_{i-1}| <= threshold_{i-1}, with all
                96 prior z and both thresholds finite (a fresh crossing).
No absolute |z| floor; |z| at entry is recorded so one can be studied later.

NO LOOK-AHEAD. Bars are labelled by OPEN and carry the CLOSE price, so bar i
labelled T_i is observed at T_i+30. Geometry at index i uses bars (i-96, i], the
threshold uses z at bars i-96..i-1, all observed by T_i+30, and the fill is at
T_i+30 = the price panel[i]. The fit window is indices [i-335, i] inclusive and
horizon h is index i+h. The assertion at the bottom enforces the alignment:
(spread[i]-mu_i)/sigma_i IS z[i] by definition, so W[:,-1] must equal
z_at_entry exactly. If the window is off by one bar that identity breaks.

SAMPLING. Pairs are drawn at random (seed 20261004) and each contributes up to
20 triggers, evenly spaced across its own history; the true per-pair trigger
count is recorded so the thinning is never invisible. Stops at 60,000.

META (record only, no filtering -- user, 2026-10-15): threshold_at_entry, r2,
beta_stab = std/|mean| of the rolling beta over the 336-bar fit window ending at
the trigger bar, and mins_since_trade of each leg at the trigger bar (the 30m
bar's value = its last minute's, from the 1m bars).
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
import paths
import universe_panel, rolling_spread as rs
from adapters.hyperliquid_futures import bar_file

FIT_BARS   = 336      # 7 days at 30m -- the SDE fit window
HORIZONS   = 20       # 10 hours ahead, in 30-minute steps
THR_BARS   = 96       # the adaptive threshold's look-back: bars i-96..i-1
THR_PCT    = 99.0
PER_PAIR   = 20
TARGET     = 60_000
OUT        = paths.DISLOC_PREFIX

panel = universe_panel.load_panel()
panel = universe_panel.drop_forming_bars(panel)
idx   = pd.to_datetime(panel.index)
V     = panel.to_numpy(float)
cols  = list(panel.columns)
n     = len(panel)
ok    = np.isfinite(V)
first = np.array([ok[:, j].argmax() for j in range(V.shape[1])])
last  = np.array([n - 1 - ok[::-1, j].argmax() for j in range(V.shape[1])])
EW    = rs.entry_window_bars(0.5)
MINB  = rs.min_bars_required(0.5)
assert EW == THR_BARS
# first possible trigger: i >= FIT_BARS-1 (fit window) and i >= MINB-1+THR_BARS (96 finite prior z);
# it needs i + HORIZONS <= len-1, so this is the shortest segment that can hold one trigger
SEG_MIN = max(FIT_BARS - 1, MINB - 1 + THR_BARS) + HORIZONS + 1
pairs = universe_panel.tradeable_pairs(cols)
ix    = {c: j for j, c in enumerate(cols)}
inlife_nan = {c: int((~ok[first[j]:last[j] + 1, j]).sum()) for j, c in enumerate(cols)}
print(f"[INFO] panel {n} bars x {len(cols)} tickers, {idx[0]} -> {idx[-1]} ({(idx[-1]-idx[0]).days} days)", flush=True)
print(f"[INFO] {len(pairs)} pairs; entry window {EW} bars, threshold look-back {THR_BARS}, fit window {FIT_BARS}, "
      f"min_bars_required {MINB}, shortest usable segment {SEG_MIN}", flush=True)
print(f"[INFO] in-life NaN 30m bars per coin: median {np.median(list(inlife_nan.values())):.0f}, "
      f"max {max(inlife_nan.values())}", flush=True)
delisted = [c for j, c in enumerate(cols) if last[j] < n - 1]
print(f"[INFO] coins ending before the panel end (delisted): {len(delisted)}", flush=True)

# mins_since_trade per coin on the panel's 30m grid (the 30m bar's value is its last minute's)
mst = {}
for c in cols:
    m = pd.read_feather(bar_file(c, "30m"), columns=["date", "mins_since_trade"])
    s = pd.Series(m.mins_since_trade.to_numpy(float),
                  index=pd.to_datetime(m.date, utc=True).dt.tz_localize(None))
    mst[c] = s.reindex(idx).to_numpy()


def segments(fin):
    """Maximal runs of True in fin, as (start, end_exclusive)."""
    e = np.diff(np.r_[0, fin.astype(np.int8), 0])
    return list(zip(np.flatnonzero(e == 1), np.flatnonzero(e == -1)))


def adaptive_threshold(absz):
    """thr[i] = 99th pct of absz[i-96 .. i-1]; NaN where any of those is NaN or i < 96."""
    thr = np.full(len(absz), np.nan)
    if len(absz) > THR_BARS:
        w = np.lib.stride_tricks.sliding_window_view(absz, THR_BARS)[: len(absz) - THR_BARS]
        good = np.isfinite(w).all(axis=1)
        q = np.full(len(w), np.nan)
        if good.any():
            q[good] = np.percentile(w[good], THR_PCT, axis=1)
        thr[THR_BARS:] = q
    return thr


order = np.random.default_rng(20261004).permutation(len(pairs))
Wl, Yl, meta = [], [], []
from collections import Counter
true_pm = Counter()                              # TRUE triggers per (pair, month), before thinning
t0 = time.time(); seen = 0; skipped = 0; nseg_short = 0; nseg_used = 0; split_pairs = 0; nan_windows = 0
WARM = SEG_MIN - HORIZONS - 1      # bars a segment spends before its first possible trigger
warm_lost = []; fully_lost = 0
for k in order:
    if len(Wl) >= TARGET: break
    a, b = pairs[k]; ja, jb = ix[a], ix[b]
    f, l = max(first[ja], first[jb]), min(last[ja], last[jb])
    if l - f + 1 < SEG_MIN:
        skipped += 1; continue
    fin = ok[f:l + 1, ja] & ok[f:l + 1, jb]
    segs = segments(fin)
    if len(segs) > 1:
        split_pairs += 1
        warm_lost.append(sum(min(e - b0, WARM) for b0, e in segs[1:]))   # warm-up paid again after each NaN close
    if not any(e - b0 >= SEG_MIN for b0, e in segs):
        fully_lost += 1
    cands = []                                   # (absolute bar, segment arrays) per trigger
    for s0, s1 in segs:
        if s1 - s0 < SEG_MIN:
            nseg_short += 1; continue
        nseg_used += 1
        g0 = f + s0
        va = V[g0:f + s1, ja]; vb = V[g0:f + s1, jb]
        r = rs.rolling_spread_stats(va, vb, 0.5)
        z = r.z; absz = np.abs(z)
        fz = np.isfinite(z) & np.isfinite(r.sigma) & (r.sigma > 0)
        thr = adaptive_threshold(np.where(fz, absz, np.nan))
        hit = np.zeros(len(z), bool)
        hit[1:] = (fz[1:] & fz[:-1] & np.isfinite(thr[1:]) & np.isfinite(thr[:-1])
                   & (absz[1:] > thr[1:]) & (absz[:-1] <= thr[:-1]))
        c = np.flatnonzero(hit)
        c = c[(c >= FIT_BARS - 1) & (c + HORIZONS <= len(z) - 1)]
        cands += [(g0, i, va, vb, r, thr) for i in c]
    seen += 1
    for g0, i, *_ in cands:
        true_pm[(a, b, idx[g0 + i].strftime("%Y-%m"))] += 1
    if not cands: continue
    ntrue = len(cands)
    take = cands if ntrue <= PER_PAIR else [cands[q] for q in np.linspace(0, ntrue - 1, PER_PAIR).round().astype(int)]
    for g0, i, va, vb, r, thr in take:
        be, al = r.beta[i], r.alpha[i]
        mu, sg = r.mu[i], r.sigma[i]
        lo = i - FIT_BARS + 1
        w = (va[lo:i + 1] - be * vb[lo:i + 1] - al - mu) / sg
        y = (va[i:i + HORIZONS + 1] - be * vb[i:i + HORIZONS + 1] - al - mu) / sg
        if not (np.isfinite(w).all() and np.isfinite(y).all()):
            nan_windows += 1; continue
        bw = r.beta[lo:i + 1]
        bstab = float(np.std(bw) / abs(np.mean(bw))) if np.isfinite(bw).all() and np.mean(bw) != 0 else np.nan
        gi = g0 + i
        Wl.append(w.astype(np.float32)); Yl.append(y.astype(np.float32))
        meta.append((a, b, idx[gi], gi, float(r.z[i]), float(thr[i]), float(be), float(al),
                     float(mu), float(sg), float(r.r2[i]), bstab, float(mst[a][gi]), float(mst[b][gi]), ntrue))
    if seen % 250 == 0:
        print(f"  {seen} pairs scanned, {len(Wl)} dislocations, {time.time()-t0:.0f}s", flush=True)

# inside a NaN-free segment every window is finite; a skip would mean the segment code is wrong
assert nan_windows == 0, f"{nan_windows} candidate windows non-finite inside finite segments"
Wa = np.asarray(Wl); Ya = np.asarray(Yl)
M = pd.DataFrame(meta, columns=["ticker_a", "ticker_b", "entry_time", "bar_index", "z_at_entry",
                                "threshold_at_entry", "beta", "alpha", "mu", "sigma", "r2", "beta_stab",
                                "mins_since_trade_a", "mins_since_trade_b", "pair_triggers_true"])
M["day"] = pd.to_datetime(M.entry_time).dt.floor("D")

# THE INVARIANT. (spread[i]-mu_i)/sigma_i is z[i] by definition, so the last
# column of the fit window and the first outcome must both BE z_at_entry. An
# off-by-one bar in either window breaks this and nothing else would.
e1 = np.abs(Wa[:, -1] - M.z_at_entry.to_numpy(np.float32)).max()
e2 = np.abs(Ya[:, 0] - M.z_at_entry.to_numpy(np.float32)).max()
print(f"\n[INVARIANT] max |W[:,-1] - z_entry| {e1:.3e}   max |Y[:,0] - z_entry| {e2:.3e}")
assert e1 < 1e-4 and e2 < 1e-4, "ALIGNMENT BUG: the fit or outcome window is off by a bar"
assert (np.abs(M.z_at_entry) > M.threshold_at_entry).all(), "a trigger is not above its adaptive threshold"

np.savez_compressed(OUT + ".npz", windows=Wa, outcomes=Ya)
M.to_parquet(OUT + "_meta.parquet")
days = M.day.sort_values().unique()
az = M.z_at_entry.abs()
q = lambda s: "  ".join(f"p{p} {s.quantile(p/100):.3f}" for p in (5, 25, 50, 75, 95))
print(f"\n[DONE] {len(M):,} dislocations, {M.ticker_a.str.cat(M.ticker_b, sep='/').nunique():,} distinct pairs, "
      f"{len(days)} days, {seen} pairs scanned ({skipped} too short)")
print(f"       {M.day.min().date()} -> {M.day.max().date()}   {time.time()-t0:.0f}s")
print(f"       per pair: median {M.groupby(['ticker_a','ticker_b']).size().median():.0f}, "
      f"true triggers per pair median {M.pair_triggers_true.median():.0f}")
print(f"       long {100*(M.z_at_entry>0).mean():.1f}%  short {100*(M.z_at_entry<0).mean():.1f}%")
cut = days[int(0.7 * len(days))]
print(f"       70/30 day split at {pd.Timestamp(cut).date()}: fit {(M.day<cut).sum():,}  held-out {(M.day>=cut).sum():,}")
print(f"       windows {Wa.shape} {Wa.nbytes/1e6:.0f}MB   outcomes {Ya.shape}")
print(f"\n[SEGMENTS] pairs split by archive gaps {split_pairs}; segments used {nseg_used}, "
      f"too short {nseg_short}; shortest usable segment {SEG_MIN} bars, warm-up {WARM}")
wl = pd.Series(warm_lost, dtype=float)
print(f"[SEGMENTS] warm-up bars lost per split pair: median {wl.median():.0f}, mean {wl.mean():.0f}, max {wl.max():.0f}; "
      f"pairs with an overlap >= {SEG_MIN} but no usable segment (fully lost): {fully_lost}")
# NaN closes common to the panel: bars where >= half of the coins alive at that bar are NaN
alive = (np.arange(n)[:, None] >= first[None, :]) & (np.arange(n)[:, None] <= last[None, :])
nan_share = ((~ok) & alive).sum(1) / np.maximum(alive.sum(1), 1)
seam = idx[nan_share >= 0.5]
print(f"[SEAMS] 30m bars where >= half the live coins have a NaN close: {len(seam)}")
et = pd.to_datetime(M.entry_time)
for ts in seam:
    pre = int(((et >= ts - pd.Timedelta(days=14)) & (et < ts)).sum()); post = int(((et > ts) & (et <= ts + pd.Timedelta(days=14))).sum())
    print(f"  {ts}  NaN in {nan_share[idx.get_loc(ts)]:.0%} of live coins; dislocations 14d before {pre:,}, 14d after {post:,}")
print(f"[TRIGGER] threshold_at_entry: {q(M.threshold_at_entry)}")
print(f"[TRIGGER] |z_at_entry|:       {q(az)}")
print(f"[TRIGGER] |z| < 2: {100*(az<2).mean():.1f}%   2-3: {100*((az>=2)&(az<3)).mean():.1f}%   >= 3: {100*(az>=3).mean():.1f}%")
pm = pd.Series(list(true_pm.values()), dtype=float)
print(f"[TRIGGER] true triggers per pair per month (pair-months with >= 1, all scanned pairs): "
      f"median {pm.median():.1f}, mean {pm.mean():.2f}, p95 {pm.quantile(.95):.1f}")
stale = (M.mins_since_trade_a >= 30) | (M.mins_since_trade_b >= 30)
print(f"[STALE] either leg mins_since_trade >= 30 at the trigger bar: {100*stale.mean():.2f}% ({int(stale.sum()):,})")
nb = int(M.beta_stab.isna().sum())
print(f"[BETA_STAB] {q(M.beta_stab)}  (finite rows only; NaN for {nb:,} = {100*nb/len(M):.1f}% -- triggers whose "
      f"336-bar fit window starts before the segment's first finite beta, bar MINB-1 = {MINB-1})")
used = sorted(set(M.ticker_a) | set(M.ticker_b))
print(f"[COINS] used {len(used)}; delisted coins included {len(set(used) & set(delisted))}")
print("[MONTH] dislocations per month:")
print(M.day.dt.to_period("M").value_counts().sort_index().to_string())
