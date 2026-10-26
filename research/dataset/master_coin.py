"""HL-MASTER1 coin unit: build 4's 74,607 coin-vs-market events in the master schema, their G0 labels and their G2 (hedge quality) analogues.

    python -u research/dataset/master_coin.py > research/dataset/logs/master_coin.log

The coin's "spread" is its 30m log price against the benchmark LEVEL L (equal-weight mean of the OTHER coins' returns, >= 30 others, accumulated segment-wise from 0;
build 4, coinevents.coin_stats); the "leg B" of every pair definition is that benchmark. Events are exactly ev_events.parquet (same event_id); ticker_a = the coin,
ticker_b = 'MKT'.  pair_index = 100000 + coin_j (the chance seed key and the grouping key).
LABELS: the SAME definitions as master_labels.py, computed by that module's chunk_labels on the coin's 1-minute path against the BRIDGED 1-minute benchmark level
(eventflow.build_LV: the 30m level path with a linear correction inside each bar; it reproduces the 30m z at every checked mark). fee_sigma uses the coin-vs-benchmark beta:
'the fee if the benchmark leg could be traded as one instrument at the taker rate: a LOWER BOUND on the real cost, which needs about 200 orders on thin coins'; the net_*
columns carry the same flag. Reproduction (asserted): reach_10h and the first minute at mu equal build 4's ev_targets for its finite-path events.
G2: master_g2.kernel with leg B = the benchmark level L (30m) and the bridged 1-minute benchmark for corr_1m_24h; sandwich has NO analogue (no high/low for a synthetic
level): NaN. both_traded_share_24h is the coin's own traded share (the benchmark always trades). The bridged benchmark minute inside a bar uses that bar's end level,
observed at the bar's close; for the trigger bar that close is t0, so every minute of the 24 h window is known at t0.
OUTPUT: research/datasets/master/work/coin/{events,labels,g2}.parquet
"""
import os, sys, time
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "research"))
sys.path.insert(0, os.path.join(ROOT, "research", "dislocation_model"))
sys.path.insert(0, HERE)
import paths
import coinevents as ce
import evmarket as em
import eventflow as ef
import flowfeat as ff
from adapters.hyperliquid_futures import bar_file
import master_labels as L
import master_g2 as G

OUTDIR = os.path.join(paths.DATASETS, "master", "work", "coin")


def main():
    t0 = time.time()
    os.makedirs(OUTDIR, exist_ok=True)
    EV = pd.read_parquet(ce.EVENTS)
    T = np.load(ef.OUT_TARGET)
    panel, idx, V, cols = ce.load_panel()
    mk = np.load(em.OUT)
    Smk, nmk = mk["S1m"], mk["n1m"].astype(np.int64)
    cidx = {c: j for j, c in enumerate(cols)}
    n = len(EV)
    # ------------------------------------------------------------ events in the master schema
    seg0 = np.zeros(n, np.int64)
    seg1 = np.zeros(n, np.int64)
    stats = {}
    for c in sorted(EV.coin.unique()):
        st = np.load(os.path.join(ce.STATS_DIR, f"{c}.npz"))
        stats[c] = {k: st[k] for k in ("L", "ir", "seg", "segend", "beta")}
        m = (EV.coin == c).to_numpy()
        sid = EV.seg.to_numpy()[m]
        first = {s: int(np.flatnonzero(st["seg"] == s)[0]) for s in np.unique(sid)}
        seg0[m] = [first[s] for s in sid]
        seg1[m] = st["segend"][EV.bar.to_numpy()[m]] + 1
    C = pd.DataFrame({
        "event_id": EV.event_id.to_numpy(), "ticker_a": EV.coin.to_numpy(), "ticker_b": "MKT", "entry_time": pd.to_datetime(EV["T"]).to_numpy(),
        "bar_index": EV.bar.to_numpy(np.int32), "z": EV.z.to_numpy(float), "threshold": EV.thr.to_numpy(float), "beta": EV.beta.to_numpy(float),
        "alpha": EV.alpha.to_numpy(float), "mu": EV.mu.to_numpy(float), "sigma": EV.sigma.to_numpy(float), "r2": EV.r2.to_numpy(float),
        "seg_start_bar": seg0.astype(np.int32), "seg_end_bar": seg1.astype(np.int32), "pair_index": (100000 + EV.coin_j.to_numpy()).astype(np.int32)})
    C["bars_into_segment"] = (C.bar_index - C.seg_start_bar).astype(np.int32)
    C["d"] = np.where(C.z >= 0, 1, -1).astype(np.int8)
    assert not C.duplicated(["ticker_a", "entry_time"]).any()
    assert (C.event_id.to_numpy() == np.arange(n)).all()
    assert (C.z.abs() > C.threshold).all()
    C.to_parquet(os.path.join(OUTDIR, "events.parquet"), index=False)
    print(f"[COIN] {n:,} events over {C.ticker_a.nunique()} coins {C.entry_time.min()} -> {C.entry_time.max()}  [{time.time() - t0:.0f}s]", flush=True)
    # ------------------------------------------------------------ the 1-minute paths (float64) and the bridged benchmark
    PM = np.full((n, 601), np.nan)
    A1s, B1s, TAs, ta = {}, {}, {}, np.zeros(n, np.int64)
    errs = []
    for k, c in enumerate(sorted(C.ticker_a.unique())):
        j = cidx[c]
        sel = np.flatnonzero((C.ticker_a == c).to_numpy())
        ev = EV.iloc[sel]
        lc = em.load_lc(c)
        r1 = em.ret1m(lc)
        fin1 = np.isfinite(r1)
        no = nmk - fin1
        with np.errstate(invalid="ignore", divide="ignore"):
            i1 = (Smk - np.where(fin1, r1, 0.0)) / no
        idx1 = np.where(fin1 & (no >= ce.MIN_OTHER), i1, np.nan)
        obar = ff.minute_index(idx + pd.Timedelta(minutes=30))
        LV = ef.build_LV(len(lc), idx1, stats[c]["L"], stats[c]["ir"], obar)
        eo = ff.minute_index(pd.to_datetime(ev["T"]) + pd.Timedelta(minutes=30))
        taus = eo[:, None] + np.arange(0, 601)[None, :]
        okp = (taus >= 1) & (taus <= ff.N)
        tk = np.clip(taus, 1, ff.N)
        Xp = np.where(okp, lc[np.clip(tk - 1, 0, ff.N - 1)], np.nan)
        Lp = np.where(okp, LV[tk], np.nan)
        P = (Xp - ev.beta.to_numpy(float)[:, None] * Lp - ev.alpha.to_numpy(float)[:, None] - ev.mu.to_numpy(float)[:, None]) / ev.sigma.to_numpy(float)[:, None]
        PM[sel] = P
        errs.append(np.nanmax(np.abs(P[:, 0] - ev.z.to_numpy(float))) if np.isfinite(P[:, 0]).any() else 0.0)
        # price-time axis arrays for the 1-minute correlation: A1[tau] = log close at price time tau, B1[tau] = bridged benchmark level
        tr = pd.read_feather(bar_file(c, "1m"), columns=["date", "mins_since_trade"])
        trd = np.zeros(ff.N)
        ix = ff.minute_index(tr["date"].dt.tz_localize(None))
        okx = (ix >= 0) & (ix < ff.N)
        trd[ix[okx]] = (tr["mins_since_trade"].to_numpy(float)[okx] == 0).astype(float)
        A1s[c], B1s[c], TAs[c] = np.r_[np.nan, lc], LV, np.r_[0.0, trd]
        ta[sel] = eo
        if (k + 1) % 40 == 0:
            print(f"  paths: coin {k + 1}  [{time.time() - t0:.0f}s]", flush=True)
    print(f"[COIN] max |1-minute path at t = 0 - z| {np.nanmax(errs):.2e} (must be < 1e-9)")
    assert np.nanmax(errs) < 1e-9
    # ------------------------------------------------------------ labels, by master_labels.chunk_labels on these paths
    L.E = C
    L.paths_for = lambda ev: PM[ev.index.to_numpy()]
    L.Y_CHECK = False
    nchunk = (n + L.CHUNK - 1) // L.CHUNK
    LB = pd.concat([L.chunk_labels(c) for c in range(nchunk)], ignore_index=True)
    LB = LB.drop(columns=["_p0err", "_yerr"])
    LB.to_parquet(os.path.join(OUTDIR, "labels.parquet"), index=False)
    ok = LB.label_gap == 0
    print(f"[COIN LABELS] {n:,} events; label_gap {int((~ok).sum()):,} ({100 * (~ok).mean():.2f}%); reach 2h/5h/10h {LB.reach_2h[ok].mean():.4f} / "
          f"{LB.reach_5h[ok].mean():.4f} / {LB.reach_10h[ok].mean():.4f}; mean chance {LB.chance_10h[ok].mean():.4f}  [{time.time() - t0:.0f}s]")
    # reproduction against build 4's own targets (finite-path events)
    fin = T["fin"].astype(bool)
    r_new = LB.reach_10h.to_numpy()
    assert not np.isnan(r_new[fin]).any(), "build 4 finite-path events with NaN master labels"
    dr = int((r_new[fin].astype(bool) != T["reach"][fin]).sum())
    tm = np.nan_to_num(LB.minutes_to_mu.to_numpy(), nan=-1)
    dt = int((tm[fin] != T["t_reach"][fin]).sum())
    dd = float(np.abs(LB.depth_10h.to_numpy()[fin] - T["depth"][fin]).max())
    print(f"[REPRODUCE build 4] finite-path events {int(fin.sum()):,}: reach differs on {dr}; first minute at mu differs on {dt}; max |depth diff| {dd:.2e}; "
          f"master finite but build 4 not: {int((ok.to_numpy() & ~fin).sum())}")
    assert dr == 0 and dt == 0 and dd < 1e-6
    for nm, h in (("2h", 120), ("5h", 300), ("10h", 600)):
        pass
    assert (LB.reach_2h[ok] <= LB.reach_5h[ok]).all() and (LB.reach_5h[ok] <= LB.reach_10h[ok]).all()
    # ------------------------------------------------------------ G2 analogues
    G.E = C
    out_ids, out_rows = [], []
    for c in sorted(C.ticker_a.unique()):
        j = cidx[c]
        g_ = C[C.ticker_a == c]
        for (g0, g1), g in g_.groupby(["seg_start_bar", "seg_end_bar"]):
            a = V[g0:g1, j]
            b = stats[c]["L"][g0:g1]
            nan = np.full(len(a), np.nan)
            eo = ta[g.index.to_numpy()]
            o, r2chk = G.kernel(a, b, nan, nan, nan, nan, g.bars_into_segment.to_numpy(), g.z.to_numpy(), g.beta.to_numpy(), g.alpha.to_numpy(), g.mu.to_numpy(),
                                g.sigma.to_numpy(), np.full(len(g), np.nan), eo, eo, A1s[c], B1s[c], TAs[c], np.ones(len(TAs[c])))
            assert np.allclose(r2chk, g.r2.to_numpy(), equal_nan=True, atol=1e-12), "r2_2d differs from the event table's r2"
            out_ids.append(g.event_id.to_numpy()); out_rows.append(o)
    X = np.concatenate(out_rows)
    G2 = pd.DataFrame(X.astype(np.float32), columns=G.NAMES)
    G2.insert(0, "event_id", np.concatenate(out_ids))
    G2 = G2.sort_values("event_id").reset_index(drop=True)
    assert len(G2) == n and (G2.event_id.to_numpy() == C.event_id.to_numpy()).all()
    # beta_stab for the coin unit: std/|mean| of the rolling beta over the 336 bars to the trigger (the coin's own beta series)
    bs = np.full(n, np.nan)
    for c in sorted(C.ticker_a.unique()):
        beta_c = stats[c]["beta"]
        sel = np.flatnonzero((C.ticker_a == c).to_numpy())
        for i in sel:
            gi = int(C.bar_index.iloc[i])
            w = beta_c[gi - 335:gi + 1]
            if len(w) == 336 and np.isfinite(w).all() and np.mean(w) != 0:
                bs[i] = np.std(w) / abs(np.mean(w))
    G2["beta_stab"] = bs.astype(np.float32)
    G2["sandwich"] = np.float32(np.nan)
    G2.to_parquet(os.path.join(OUTDIR, "g2.parquet"), index=False)
    print(f"[COIN G2] {len(G2):,} rows x {len(G.NAMES)} columns; sandwich NaN by definition (no analogue)  [{time.time() - t0:.0f}s]")
    for nm in G.NAMES:
        v = G2[nm].to_numpy(float)
        print(f"  {nm:<22} NaN {100 * np.isnan(v).mean():6.2f}%  p5 {np.nanpercentile(v, 5) if np.isfinite(v).any() else np.nan:+.4g}  median {np.nanmedian(v) if np.isfinite(v).any() else np.nan:+.4g}")


if __name__ == "__main__":
    main()
