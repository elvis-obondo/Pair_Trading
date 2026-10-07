"""Phase 2, item 1: the dislocation set over the full 753 days.

Straight from the 30-minute panel -- no backtest, no paths.npz. The panel's
holes are entirely staggered listing dates: all 212 tickers have ONE contiguous
finite region ending at the last bar, so each pair's overlap is a single slice
and the 30-minute fit grid stays uniform.

GEOMETRY, and the two windows are different:
  entry trigger + frozen geometry : 96 bars  (rolling_spread.ENTRY_WINDOW_DAYS=2)
  SDE fit window                  : 336 bars (7 days -- Phase 1's largest win)

NO LOOK-AHEAD. Bars are labelled by OPEN and carry the CLOSE price, so bar i
labelled T_i is observed at T_i+30. Geometry at index i uses bars (i-96, i],
all observed by T_i+30, and the fill is at T_i+30 = the price panel[i]. So the
fit window is indices [i-335, i] inclusive and horizon h is index i+h. The
assertion at the bottom is what enforces this: (spread[i]-mu_i)/sigma_i IS
z[i] by definition, so W[:,-1] must equal z_at_entry exactly. If the window is
off by one bar that identity breaks.

SAMPLING. The population is 3.45M fresh crossings (154 per pair). Taking all of
them is 4.9GB, so pairs are drawn at random and each contributes up to 20
triggers, stride-sampled across its own history. Depth 20 per pair is what the
per-pair parameters (k_r, theta_0, v_0 with shrinkage) need; 3,000 pairs is the
breadth the pooled ones need. The true per-pair trigger count is recorded so
the thinning is never invisible.
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
import paths
import universe_panel, rolling_spread as rs

FIT_BARS   = 336      # 7 days at 30m -- the SDE fit window
HORIZONS   = 20       # 10 hours ahead, in 30-minute steps
ENTRY_SIG  = 3.0
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
first = np.array([ok[:,j].argmax() for j in range(V.shape[1])])
assert all(ok[first[j]:,j].all() for j in range(V.shape[1])), "a finite region is not contiguous"
EW    = rs.entry_window_bars(0.5)
MINB  = rs.min_bars_required(0.5)
pairs = universe_panel.tradeable_pairs(cols)
ix    = {c:j for j,c in enumerate(cols)}
print(f"[INFO] panel {n} bars x {len(cols)} tickers, {idx[0]} -> {idx[-1]} "
      f"({(idx[-1]-idx[0]).days} days)", flush=True)
print(f"[INFO] {len(pairs)} pairs; entry window {EW} bars, fit window {FIT_BARS} bars, "
      f"min_bars_required {MINB}", flush=True)

order = np.random.default_rng(20261004).permutation(len(pairs))
Wl, Yl, meta = [], [], []
t0 = time.time(); seen = 0; skipped = 0
for k in order:
    if len(Wl) >= TARGET: break
    a, b = pairs[k]; ja, jb = ix[a], ix[b]
    f = max(first[ja], first[jb])
    # need FIT_BARS of prices before the entry bar, MINB for finite geometry,
    # and HORIZONS bars after it
    if n - f < max(FIT_BARS, MINB) + HORIZONS + 1:
        skipped += 1; continue
    va = V[f:, ja]; vb = V[f:, jb]
    r = rs.rolling_spread_stats(va, vb, 0.5)
    z = r.z; fin = np.isfinite(z) & np.isfinite(r.sigma) & (r.sigma > 0)
    hit = np.zeros(len(z), bool)
    hit[1:] = fin[1:] & fin[:-1] & (np.abs(z[1:]) >= ENTRY_SIG) & (np.abs(z[:-1]) < ENTRY_SIG)
    cand = np.flatnonzero(hit)
    cand = cand[(cand >= FIT_BARS - 1) & (cand + HORIZONS <= len(z) - 1)]
    seen += 1
    if len(cand) == 0: continue
    ntrue = len(cand)
    take = cand if ntrue <= PER_PAIR else cand[np.linspace(0, ntrue-1, PER_PAIR).round().astype(int)]
    for i in take:
        be, al = r.beta[i], r.alpha[i]
        mu, sg = r.mu[i], r.sigma[i]
        lo = i - FIT_BARS + 1
        w = (va[lo:i+1] - be*vb[lo:i+1] - al - mu) / sg
        y = (va[i:i+HORIZONS+1] - be*vb[i:i+HORIZONS+1] - al - mu) / sg
        if not (np.isfinite(w).all() and np.isfinite(y).all()): continue
        Wl.append(w.astype(np.float32)); Yl.append(y.astype(np.float32))
        meta.append((a, b, idx[f+i], f+i, float(z[i]), float(be), float(al),
                     float(mu), float(sg), float(r.r2[i]), ntrue))
    if seen % 250 == 0:
        print(f"  {seen} pairs scanned, {len(Wl)} dislocations, {time.time()-t0:.0f}s", flush=True)

Wa = np.asarray(Wl); Ya = np.asarray(Yl)
M = pd.DataFrame(meta, columns=["ticker_a","ticker_b","entry_time","bar_index","z_at_entry",
                                "beta","alpha","mu","sigma","r2","pair_triggers_true"])
M["day"] = pd.to_datetime(M.entry_time).dt.floor("D")

# THE INVARIANT. (spread[i]-mu_i)/sigma_i is z[i] by definition, so the last
# column of the fit window and the first outcome must both BE z_at_entry. An
# off-by-one bar in either window breaks this and nothing else would.
e1 = np.abs(Wa[:,-1] - M.z_at_entry.to_numpy(np.float32)).max()
e2 = np.abs(Ya[:,0]  - M.z_at_entry.to_numpy(np.float32)).max()
print(f"\n[INVARIANT] max |W[:,-1] - z_entry| {e1:.3e}   max |Y[:,0] - z_entry| {e2:.3e}")
assert e1 < 1e-4 and e2 < 1e-4, "ALIGNMENT BUG: the fit or outcome window is off by a bar"
assert (np.abs(M.z_at_entry) >= ENTRY_SIG - 1e-9).all(), "a trigger is below the threshold"

np.savez_compressed(OUT+".npz", windows=Wa, outcomes=Ya)
M.to_parquet(OUT+"_meta.parquet")
days = M.day.sort_values().unique()
print(f"\n[DONE] {len(M):,} dislocations, {M.ticker_a.str.cat(M.ticker_b,sep='/').nunique():,} distinct pairs, "
      f"{len(days)} days, {seen} pairs scanned ({skipped} too short)")
print(f"       {M.day.min().date()} -> {M.day.max().date()}   {time.time()-t0:.0f}s")
print(f"       per pair: median {M.groupby(['ticker_a','ticker_b']).size().median():.0f}, "
      f"true triggers per pair median {M.pair_triggers_true.median():.0f}")
print(f"       long {100*(M.z_at_entry>0).mean():.1f}%  short {100*(M.z_at_entry<0).mean():.1f}%")
cut = days[int(0.7*len(days))]
print(f"       70/30 day split at {pd.Timestamp(cut).date()}: "
      f"fit {(M.day<cut).sum():,}  held-out {(M.day>=cut).sum():,}")
print(f"       windows {Wa.shape} {Wa.nbytes/1e6:.0f}MB   outcomes {Ya.shape}")
