"""REACH-MU Step 0: how far the mover moved, past dislocation history, breadth.

    OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 .venv/bin/python -u \
        research/dislocation_model/reachfeat.py > research/dislocation_model/logs/reachfeat.log 2>&1

Writes research/datasets/reachfeat.npz (rows aligned to disloc_meta, all 60,000)
and research/datasets/breadth_counts.npz (the bars x coins count table, built
once, reused). Nothing reads past the entry bar; audited per family, stop on
failure. pair_triggers_true is NOT read (it counts the pair's whole history,
future included).

1. HOW FAR THE MOVING LEG MOVED, lookbacks L = 4 and 12 bars (2h, 6h), bars
   i-L+1 .. i. The dominant leg is whyfeat's: the larger |contribution| to the
   spread a - beta*b, contribution of A = sum resid_A, of B = -beta * sum
   resid_B, residuals from the same trailing-PCA market factor
   (whyfeat.market_factor, recomputed, identical code). Weight in the spread
   w = 1 for A, -beta for B. Signed so POSITIVE = the move WIDENED the spread
   (pushed it toward sign(z_at_entry)):
     mover_resid_z_L = sign(z) * sign(w) * sum resid_d / (sd_d * sqrt(L))
     mover_ret_L     = sign(z) * sign(w) * (logclose_d[i] - logclose_d[i-L])
   Gap filled: sd_d, "its trailing 7-day residual sd", is taken over the 336
   bars BEFORE the lookback window (i-L-335 .. i-L), as whyfeat's volume
   baselines are, so the move does not inflate its own yardstick; ddof=1, and
   missing when fewer than 168 of the 336 residuals are finite. Missing
   wherever the dominant leg is undefined (a leg outside the factor fit).

2. PAST DISLOCATION HISTORY. Every pair's z recomputed on its own rolling
   geometry exactly as mkdisloc.py does (rolling_spread_stats on the slice from
   the pair's first common finite bar; a fresh crossing at t = z finite at t
   and t-1, |z_t| >= 3, |z_{t-1}| < 3). Only crossings at bars STRICTLY BEFORE
   the entry bar count (the entry is itself a crossing). Gap filled: every
   crossing counts, not only those mkdisloc could have sampled (it also needs
   336 bars of history and 20 bars after; the 20 after would be look-ahead).
     triggers_past_rate  crossings from the pair's first finite z to entry /
                         days of history (bars / 48)
     triggers_past_30d   crossings in the 1,440 bars before entry
   The number of episodes with under 30 days of history is reported.
   GATE: the recomputed z at every episode's entry bar must equal z_at_entry
   (1e-6) and the entry bar must be a fresh crossing. Otherwise STOP: the
   geometry is not mkdisloc's.

3. BREADTH AT THE ENTRY BAR, from every tradeable pair's |z| on its own
   geometry (22,366 pairs). Count table, per bar and coin: pairs at |z| >= 3,
   pairs with finite z; per bar: the same over all pairs.
     leg_a_breadth, leg_b_breadth  that leg's dislocated pairs / its pairs with
                                   finite z
     breadth_ratio                 (larger count + 1) / (smaller count + 1)
     market_breadth                all dislocated pairs / all finite pairs
   Gap filled: the episode's OWN pair is excluded from the leg counts (it is
   dislocated at entry by construction, so it carries no information and would
   inflate thinly-paired legs); market_breadth keeps it (1 of ~20,000).

CHECKS: look-ahead per family; coverage; median/p5/p95; Spearman against
vol_48 and vol_48_1m on the 53,757 set, > 0.8 flagged "restates volatility".
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd

import paths
import rolling_spread as rs
import universe_panel
from whyfeat import WIN, LOOKS, market_factor, take

ENTRY_SIG = 3.0
DAY_BARS = 48
BASE_30D = 30 * DAY_BARS
MIN_SD = WIN // 2
OUT = os.path.join(paths.DATASETS, "reachfeat.npz")
COUNTS = os.path.join(paths.DATASETS, "breadth_counts.npz")


def main():
    t0 = time.time()
    M = pd.read_parquet(paths.META)
    N_ep = len(M)
    panel = universe_panel.drop_forming_bars(universe_panel.load_panel())
    pidx = pd.to_datetime(panel.index)
    cols = list(panel.columns)
    ixc = {c: k for k, c in enumerate(cols)}
    LC = panel.to_numpy(float)
    n, N = LC.shape
    J = M.bar_index.to_numpy(int)
    if not (pidx[J] == pd.to_datetime(M.entry_time)).all():
        raise SystemExit("[REACHF] meta.bar_index does not resolve to entry_time.")
    ja = M.ticker_a.map(ixc).to_numpy(int)
    jb = M.ticker_b.map(ixc).to_numpy(int)
    beta = M.beta.to_numpy(float)
    s = np.sign(M.z_at_entry.to_numpy(float))
    s[s == 0] = 1.0
    print("=" * 112)
    print("REACH-MU STEP 0 -- mover size, past dislocation history, breadth")
    print("=" * 112)
    print(f"  panel {n:,} bars x {N} tickers; {N_ep:,} episodes")
    feats, touch = {}, {}

    # ---------------- 1. mover ----------------
    _, resid, _, _, _, _ = market_factor(LC)
    print(f"  market factor recomputed (whyfeat.market_factor)   [{time.time()-t0:.0f}s]", flush=True)
    for L in LOOKS:
        I = J[:, None] + np.arange(-L + 1, 1)[None, :]
        ra, rb = resid[I, ja[:, None]], resid[I, jb[:, None]]
        cA, cB = ra.sum(1), -beta * rb.sum(1)
        undef = ~(np.isfinite(ra).all(1) & np.isfinite(rb).all(1))
        domA = np.abs(cA) >= np.abs(cB)
        jd = np.where(domA, ja, jb)
        sw = np.where(domA, 1.0, np.sign(-beta))
        sres = np.where(domA, ra.sum(1), rb.sum(1))
        Ib = J[:, None] + np.arange(-L - WIN + 1, -L + 1)[None, :]
        rbase = take(resid, Ib, jd[:, None])
        nfin = np.isfinite(rbase).sum(1)
        with np.errstate(invalid="ignore", divide="ignore"):
            sd = np.nanstd(rbase, axis=1, ddof=1)
            sd[nfin < MIN_SD] = np.nan
            rz = s * sw * sres / (sd * np.sqrt(L))
        p_now = LC[J, jd]
        p_then = take(LC, (J - L)[:, None], jd[:, None])[:, 0]
        ret = s * sw * (p_now - p_then)
        for nm, v in ((f"mover_resid_z_{L}", rz), (f"mover_ret_{L}", ret)):
            v = np.where(np.isfinite(v) & ~undef, v, np.nan)
            feats[nm] = v
        touch[f"mover L={L}"] = np.maximum(I.max(1), Ib.max(1))
        # whyfeat's own check, reproduced: the dominant contribution's sign
        cd = np.where(domA, cA, cB)
        agree = np.isfinite(rz) & ((rz > 0) == (s * cd > 0))
        print(f"  L={L:>2}: mover_resid_z > 0 exactly when the dominant contribution widened the spread: "
              f"{agree.sum():,} of {int(np.isfinite(rz).sum()):,}")
    del resid
    print()

    # ---------------- 2 + 3. every pair's z ----------------
    V = panel.to_numpy(float)
    ok = np.isfinite(V)
    first = np.array([ok[:, j].argmax() for j in range(N)])
    pairs = universe_panel.tradeable_pairs(cols)
    ndis = np.zeros((n, N), np.int32)
    nfin = np.zeros((n, N), np.int32)
    mdis = np.zeros(n, np.int64)
    mfin = np.zeros(n, np.int64)
    key = M.ticker_a + "|" + M.ticker_b
    ep_of = key.groupby(key).indices
    pairset = {f"{a}|{b}" for a, b in pairs}
    missing_pairs = set(ep_of) - pairset
    if missing_pairs:
        raise SystemExit(f"[REACHF] {len(missing_pairs)} episode pairs are not tradeable pairs.")
    rate = np.full(N_ep, np.nan)
    p30 = np.full(N_ep, np.nan)
    hist_bars = np.full(N_ep, -1)
    z_err = np.full(N_ep, np.nan)
    is_hit = np.zeros(N_ep, bool)
    trig_touch = np.full(N_ep, -10 ** 9)
    for pi, (a, b) in enumerate(pairs):
        xa, xb = ixc[a], ixc[b]
        f = max(first[xa], first[xb])
        r = rs.rolling_spread_stats(V[f:, xa], V[f:, xb], 0.5)
        z = r.z
        fin = np.isfinite(z) & np.isfinite(r.sigma) & (r.sigma > 0)
        dis = fin & (np.abs(np.where(fin, z, 0.0)) >= ENTRY_SIG)
        ndis[f:, xa] += dis
        ndis[f:, xb] += dis
        nfin[f:, xa] += fin
        nfin[f:, xb] += fin
        mdis[f:] += dis
        mfin[f:] += fin
        eps = ep_of.get(f"{a}|{b}")
        if eps is not None:
            hit = np.zeros(len(z), bool)
            hit[1:] = fin[1:] & fin[:-1] & dis[1:] & ~dis[:-1]
            cross = np.flatnonzero(hit) + f                 # absolute bar indices
            ff = f + int(fin.argmax())                      # first finite z
            Je = J[eps]
            z_err[eps] = np.abs(z[Je - f] - M.z_at_entry.to_numpy()[eps])
            is_hit[eps] = hit[Je - f]
            k_all = np.searchsorted(cross, Je, side="left")   # crossings strictly before entry
            k_30 = k_all - np.searchsorted(cross, Je - BASE_30D, side="left")
            hb = Je - ff
            hist_bars[eps] = hb
            with np.errstate(divide="ignore", invalid="ignore"):
                rate[eps] = np.where(hb > 0, k_all / (hb / DAY_BARS), np.nan)
            p30[eps] = k_30
            # the latest crossing counted must sit strictly before the entry bar
            last_used = np.where(k_all > 0, cross[np.maximum(k_all - 1, 0)], -10 ** 9)
            trig_touch[eps] = last_used
        if (pi + 1) % 4000 == 0:
            print(f"    {pi+1:,} of {len(pairs):,} pairs   [{time.time()-t0:.0f}s]", flush=True)
    print(f"  every pair's z on its own geometry: {len(pairs):,} pairs   [{time.time()-t0:.0f}s]")
    zmax = float(np.nanmax(z_err))
    print(f"  GATE -- recomputed z at entry vs z_at_entry: max |diff| {zmax:.2e} (must be <= 1e-6); "
          f"entry bar is a fresh crossing on {int(is_hit.sum()):,} of {N_ep:,}")
    if not (zmax <= 1e-6 and is_hit.all()):
        raise SystemExit("[REACHF] STOP -- the recomputed geometry is not mkdisloc's.")
    feats["triggers_past_rate"] = rate
    feats["triggers_past_30d"] = p30
    touch["past triggers (latest crossing used)"] = np.where(trig_touch < 0, J - 1, trig_touch)
    print(f"  episodes with under 30 days of history before entry: {int((hist_bars < BASE_30D).sum()):,} "
          f"of {N_ep:,} (triggers_past_30d counts only the history they have)")
    np.savez_compressed(COUNTS, ndis=ndis, nfin=nfin, mdis=mdis, mfin=mfin, tickers=np.array(cols),
                        bars=pidx.to_numpy("datetime64[ns]"))
    print(f"  [WROTE] {os.path.relpath(COUNTS, paths.RESEARCH)}  ({n:,} bars x {N} coins)")
    ca = ndis[J, ja] - 1                      # own pair excluded
    cb = ndis[J, jb] - 1
    fa = nfin[J, ja] - 1
    fb = nfin[J, jb] - 1
    if (ca < 0).any() or (cb < 0).any():
        raise SystemExit("[REACHF] own pair not counted as dislocated at entry.")
    with np.errstate(divide="ignore", invalid="ignore"):
        feats["leg_a_breadth"] = np.where(fa > 0, ca / fa, np.nan)
        feats["leg_b_breadth"] = np.where(fb > 0, cb / fb, np.nan)
        feats["breadth_ratio"] = (np.maximum(ca, cb) + 1.0) / (np.minimum(ca, cb) + 1.0)
        feats["market_breadth"] = np.where(mfin[J] > 0, mdis[J] / mfin[J], np.nan)
    touch["breadth (count table row read)"] = J.copy()
    print()

    # ---------------- checks ----------------
    print("=" * 112)
    print("CHECKS")
    print("=" * 112)
    bad = False
    print("  LOOK-AHEAD -- max 30m index touched minus the entry index, per family:")
    for k, v in touch.items():
        d = int((v - J).max())
        print(f"    {k:<40} max {d:+d} (must be <= 0)")
        bad |= d > 0
    if bad:
        raise SystemExit("[REACHF] STOP -- a feature reads past the entry bar.")
    print("    -> PASS")
    print()
    from envelope import scan_1m_coverage, select_1m_subset
    cov = scan_1m_coverage(M, verbose=False)
    used, _ = select_1m_subset(M, cov, verbose=False)
    r1 = np.flatnonzero(used)
    names = list(feats)
    print(f"  COVERAGE and DISTRIBUTION (all {N_ep:,}; and on the 53,757 set)")
    print(f"    {'feature':<22}{'finite':>8}{'finite 53,757':>15}{'median':>11}{'p5':>11}{'p95':>11}")
    for nm in names:
        v = feats[nm]
        print(f"    {nm:<22}{int(np.isfinite(v).sum()):>8,}{int(np.isfinite(v[r1]).sum()):>15,}"
              f"{np.nanmedian(v):>11.4g}{np.nanpercentile(v, 5):>11.4g}{np.nanpercentile(v, 95):>11.4g}")
    print()
    fz = np.load(paths.ENVFEAT, allow_pickle=False)
    v48 = np.load(os.path.join(paths.DATASETS, "vol48_1m.npz"))
    if not np.array_equal(v48["rows"], r1):
        raise SystemExit("[REACHF] vol48_1m rows differ from the 53,757 set.")
    ref = {"vol_48": fz["X"][r1, 0].astype(float), "vol_48_1m": v48["vol_48_1m"]}
    print("  SPEARMAN on the 53,757 set, flag > 0.8 against vol_48 or vol_48_1m")
    flags = []
    for nm in names:
        v = feats[nm][r1]
        row = []
        for w in ref.values():
            m_ = np.isfinite(v) & np.isfinite(w)
            row.append(pd.Series(v[m_]).corr(pd.Series(w[m_]), method="spearman"))
        fl = max(abs(row[0]), abs(row[1])) > 0.8
        if fl:
            flags.append(nm)
        print(f"    {nm:<22} vol_48 {row[0]:+.3f}   vol_48_1m {row[1]:+.3f}"
              + ("   RESTATES VOLATILITY" if fl else ""))
    print(f"  flagged 'restates volatility': {', '.join(flags) if flags else 'none'}")
    np.savez_compressed(OUT, names=np.array(names), X=np.column_stack([feats[k] for k in names]),
                        restates=np.array(flags), ticker_a=M.ticker_a.to_numpy(str),
                        ticker_b=M.ticker_b.to_numpy(str),
                        entry_time=pd.to_datetime(M.entry_time).to_numpy("datetime64[ns]"))
    print(f"  [WROTE] {os.path.relpath(OUT, paths.RESEARCH)}  ({N_ep:,} x {len(names)})")
    print(f"  [{time.time()-t0:.0f}s]")
    print("=" * 112)


if __name__ == "__main__":
    main()
