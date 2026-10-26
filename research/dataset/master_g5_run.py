"""HL-MASTER1 G5 orchestration: leg blocks per coin (parallel), net weights, price shape, parquet output.

    python -u research/dataset/master_g5_run.py > research/dataset/logs/master_g5.log
"""
import os, sys, time
from multiprocessing import Pool
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import master_g5 as G5
import flowfeat as ff
import evmarket as em
import eventflow as ef
import coinevents as ce
import paths

WORK = G5.WORK
UNITS = ("pair", "coin")


def event_tables():
    out = {}
    for u in UNITS:
        E = pd.read_parquet(os.path.join(WORK, u, "events.parquet"))
        t0 = pd.to_datetime(E.entry_time) + pd.Timedelta(minutes=30)
        o = ff.minute_index(t0)
        assert ((o - ff.CUT_PHASE) % 30 == 0).all()
        out[u] = (E, o)
    return out


def main():
    t0 = time.time()
    ev = event_tables()
    jobs = {}                                           # coin -> {key: (ix, o, s)}
    for u, (E, o) in ev.items():
        d = E.d.to_numpy(float)
        legs = {"a": (E.ticker_a, d)}
        if u == "pair":
            legs["b"] = (E.ticker_b, -d * np.sign(E.beta.to_numpy(float)))
        for lg, (names, s) in legs.items():
            names = names.to_numpy()
            for c in np.unique(names):
                ix = np.flatnonzero(names == c)
                jobs.setdefault(c, {})[(u, lg)] = (ix, o[ix], s[ix])
    print(f"[G5] {sum(len(v) for v in jobs.values())} (coin, unit, leg) blocks over {len(jobs)} coins  [{time.time() - t0:.0f}s]", flush=True)
    store = {(u, lg): np.full((len(ev[u][0]), len(G5.NAMES_LEG)), np.nan, np.float32) for u in UNITS for lg in (("a", "b") if u == "pair" else ("a",))}
    with Pool(int(os.environ.get("NPROC", 6))) as pool:
        for q, (c, res) in enumerate(pool.imap_unordered(G5.coin_job, [(c, r) for c, r in sorted(jobs.items())])):
            for key, (ix, mats) in res.items():
                store[key][ix] = mats
            if (q + 1) % 20 == 0:
                print(f"  coin {q + 1}/{len(jobs)}  [{time.time() - t0:.0f}s]", flush=True)
    # ---------------------------------------------------------------- price shape and net weights
    lc = {c: em.load_lc(c) for c in sorted(set(ev["pair"][0].ticker_a) | set(ev["pair"][0].ticker_b) | set(ev["coin"][0].ticker_a))}
    ps = {}
    for u, (E, o) in ev.items():
        n = len(E)
        cols = {k: np.full(n, np.nan, np.float32) for k in G5.PRICE_NAMES}
        ps[u] = cols
        d = E.d.to_numpy(float)
        beta, alpha, mu, sg = (E[c].to_numpy(float) for c in ("beta", "alpha", "mu", "sigma"))
        if u == "coin":
            continue
        for a in range(0, n, G5.CH):
            sl = slice(a, min(a + G5.CH, n))
            oo = o[sl]
            win = oo[:, None] - 1501 + np.arange(1501)[None, :]                    # minutes o-1501 .. o-1 ; column 1500 = o - 1
            win_ok = win >= 0
            wc = np.clip(win, 0, ff.N - 1)
            if u == "pair":
                la = np.where(win_ok, np.stack([lc[c][w] for c, w in zip(E.ticker_a.to_numpy()[sl], wc)]), np.nan)
                lb = np.where(win_ok, np.stack([lc[c][w] for c, w in zip(E.ticker_b.to_numpy()[sl], wc)]), np.nan)
                s_z = d[sl]
                cA = d[sl] * (la[:, -1] - la[:, -61])
                cB = -d[sl] * beta[sl] * (lb[:, -1] - lb[:, -61])
                pa, pb = np.maximum(cA, 0), np.maximum(cB, 0)
                with np.errstate(invalid="ignore", divide="ignore"):
                    wA = np.where((pa + pb) > 0, pa / (pa + pb), 0.5)
                wA = np.where(np.isfinite(cA) & np.isfinite(cB), wA, np.nan)
                cols["w_a"][sl], cols["contrib_a"][sl], cols["contrib_b"][sl] = wA, cA, cB
            r = G5.price_shape(la, lb, beta[sl], alpha[sl], mu[sl], sg[sl], s_z, oo, d[sl])
            for k, v in r.items():
                cols[k][sl] = v
    print(f"[G5] price shape and weights  [{time.time() - t0:.0f}s]", flush=True)
    # coin unit: the benchmark path is the bridged level, per coin
    E, o = ev["coin"]
    cols = ps["coin"]
    mk = np.load(em.OUT)
    panel_idx = ce.load_panel()[1]
    obar = ff.minute_index(pd.DatetimeIndex(panel_idx) + pd.Timedelta(minutes=30))
    d = E.d.to_numpy(float)
    beta, alpha, mu, sg = (E[c].to_numpy(float) for c in ("beta", "alpha", "mu", "sigma"))
    for c in np.unique(E.ticker_a):
        ix = np.flatnonzero((E.ticker_a == c).to_numpy())
        st = np.load(os.path.join(ce.STATS_DIR, f"{c}.npz"))
        r1 = em.ret1m(lc[c]); fin1 = np.isfinite(r1)
        no = mk["n1m"].astype(np.int64) - fin1
        with np.errstate(invalid="ignore", divide="ignore"):
            i1 = (mk["S1m"] - np.where(fin1, r1, 0.0)) / no
        idx1 = np.where(fin1 & (no >= ce.MIN_OTHER), i1, np.nan)
        LV = ef.build_LV(len(lc[c]), idx1, st["L"], st["ir"], obar)
        for a in range(0, len(ix), G5.CH):
            sub = ix[a:a + G5.CH]
            oo = o[sub]
            win = oo[:, None] - 1501 + np.arange(1501)[None, :]
            ok = win >= 0
            wc = np.clip(win, 0, ff.N - 1)
            la = np.where(ok, lc[c][wc], np.nan)
            lb = np.where(ok, LV[np.clip(wc + 1, 0, ff.N)], np.nan)                # price time tau = minute label + 1
            cA = d[sub] * (la[:, -1] - la[:, -61])
            cB = -d[sub] * beta[sub] * (lb[:, -1] - lb[:, -61])
            cols["contrib_a"][sub], cols["contrib_b"][sub] = cA, cB
            cols["w_a"][sub] = 1.0
            r = G5.price_shape(la, lb, beta[sub], alpha[sub], mu[sub], sg[sub], d[sub], oo, d[sub])
            for k, v in r.items():
                cols[k][sub] = v
    print(f"[G5] coin-unit price shape  [{time.time() - t0:.0f}s]", flush=True)
    # ---------------------------------------------------------------- net, write
    for u, (E, o) in ev.items():
        legs = ("a", "b") if u == "pair" else ("a",)
        Xa = store[(u, "a")]
        if u == "pair":
            Xb = store[(u, "b")]
            wA = ps[u]["w_a"].astype(np.float64)
            wB = 1 - wA
            net = np.full_like(Xa, np.nan)
            for q, nm in enumerate(G5.NAMES_LEG):
                if nm in G5.NO_NET:
                    continue
                xa, xb = Xa[:, q].astype(np.float64), Xb[:, q].astype(np.float64)
                a_ = np.where(wA > 0, wA * xa, 0.0); b_ = np.where(wB > 0, wB * xb, 0.0)
                bad = ((wA > 0) & ~np.isfinite(xa)) | ((wB > 0) & ~np.isfinite(xb)) | ~np.isfinite(wA)
                net[:, q] = np.where(bad, np.nan, a_ + b_)
        else:
            net = Xa.copy()
            for nm in G5.NO_NET:
                net[:, G5.NAMES_LEG.index(nm)] = np.nan
        for lg, X in (("a", Xa), ("b", store.get((u, "b"))), ("net", net)):
            if X is None:
                continue
            df = pd.DataFrame(X, columns=[f"{lg}_{nm}" for nm in G5.NAMES_LEG])
            df.insert(0, "event_id", E.event_id.to_numpy())
            df.to_parquet(os.path.join(WORK, u, f"g5_{lg}.parquet"), index=False)
        sh = pd.DataFrame({k: v for k, v in ps[u].items()})
        sh.insert(0, "event_id", E.event_id.to_numpy())
        sh.to_parquet(os.path.join(WORK, u, "g5_shape.parquet"), index=False)
        print(f"[G5 {u}] written: leg a/b/net x {len(G5.NAMES_LEG)} columns, price shape {len(G5.PRICE_NAMES)}  [{time.time() - t0:.0f}s]")
        for nm in ("imb_60", "forced_share_60", "backstop_share_1440", "adl_share_1440", "open_close_ratio_360", "volume_ratio_60", "wallets_per_musd_60", "twap_share_60", "slope_cum_imb_30",
                   "mins_since_forced_any", "mins_since_forced_spike", "accel_share"):
            v = Xa[:, G5.NAMES_LEG.index(nm)].astype(float)
            f = np.isfinite(v)
            print(f"  a_{nm:<24} NaN {100 * (~f).mean():6.2f}%  median {np.median(v[f]) if f.any() else np.nan:+.4g}  p5 {np.percentile(v[f], 5) if f.any() else np.nan:+.4g}  p95 {np.percentile(v[f], 95) if f.any() else np.nan:+.4g}")
        for nm in G5.PRICE_NAMES:
            v = ps[u][nm].astype(float)
            f = np.isfinite(v)
            print(f"  {nm:<24} NaN {100 * (~f).mean():6.2f}%  median {np.median(v[f]) if f.any() else np.nan:+.4g}  p5 {np.percentile(v[f], 5) if f.any() else np.nan:+.4g}  p95 {np.percentile(v[f], 95) if f.any() else np.nan:+.4g}")


if __name__ == "__main__":
    main()
