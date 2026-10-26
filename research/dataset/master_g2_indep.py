"""HL-MASTER1 G2 independent recomputation: 2,000 random events, a second implementation written WITHOUT reading master_g2.kernel.

    python -u research/dataset/master_g2_indep.py > research/dataset/logs/master_g2_indep.log

Plain numpy per event and per bar (explicit loops, direct slices of the GLOBAL panel; no segment arrays, no rolling objects, no sliding windows), from the raw
sources: the 30m log-close panel, the 30m high/low feathers and the 1-minute feathers read separately by timestamp. Compares all 24 columns of g2.parquet
(float32 storage: rtol 1e-4, atol 1e-6); NaN patterns must match exactly. Any mismatch aborts.
"""
import os, sys, time
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "research"))
sys.path.insert(0, os.path.join(ROOT, "research", "dislocation_model"))
import paths
import universe_panel
from adapters.hyperliquid_futures import bar_file
from envfeat import iid_vratio_norm

WORK = os.path.join(paths.DATASETS, "master", "work", "pair")
N = 2000
SEED = 20261025
VDIV = iid_vratio_norm(96)
panel = universe_panel.drop_forming_bars(universe_panel.load_panel())
idx = pd.to_datetime(panel.index)
V = panel.to_numpy(float)
ix = {c: j for j, c in enumerate(panel.columns)}
_hl, _m1 = {}, {}


def hilo(c):
    if c not in _hl:
        d = pd.read_feather(bar_file(c, "30m"), columns=["date", "high", "low"])
        t = pd.to_datetime(d.date, utc=True).dt.tz_localize(None)
        _hl[c] = (pd.Series(np.log(d.high.to_numpy(float)), index=t).reindex(idx).to_numpy(), pd.Series(np.log(d.low.to_numpy(float)), index=t).reindex(idx).to_numpy())
    return _hl[c]


def m1(c):
    if c not in _m1:
        d = pd.read_feather(bar_file(c, "1m"), columns=["date", "close", "mins_since_trade"])
        t = pd.to_datetime(d.date, utc=True).dt.tz_localize(None)
        t = pd.DatetimeIndex(t)
        keep = ~t.duplicated(keep="last")
        _m1[c] = (pd.Series(np.log(d.close.to_numpy(float)), index=t)[keep], pd.Series(d.mins_since_trade.to_numpy(float), index=t)[keep])
    return _m1[c]


def beta_at(a, b, k):
    """Vol-matched beta of the 96 bars ending at k: sd(a)/sd(b), signed by the covariance."""
    xa, xb = a[k - 95:k + 1], b[k - 95:k + 1]
    cov = np.mean((xa - xa.mean()) * (xb - xb.mean()))
    return np.sign(cov) * xa.std() / xb.std()


def expected(row):
    c_a, c_b = row.ticker_a, row.ticker_b
    a, b = V[:, ix[c_a]], V[:, ix[c_b]]
    gi, g0 = int(row.bar_index), int(row.seg_start_bar)
    be, al, mu, sg, z = row.beta, row.alpha, row.mu, row.sigma, row.z
    s = 1.0 if z >= 0 else -1.0
    o = {}
    xa, xb = a[gi - 95:gi + 1], b[gi - 95:gi + 1]
    o["r2_2d"] = np.corrcoef(xa, xb)[0, 1] ** 2
    xa7, xb7 = a[gi - 335:gi + 1], b[gi - 335:gi + 1]
    o["r2_7d"] = np.corrcoef(xa7, xb7)[0, 1] ** 2
    ra2, rb2 = np.diff(a[gi - 96:gi + 1]), np.diff(b[gi - 96:gi + 1])
    ra7, rb7 = np.diff(a[gi - 336:gi + 1]), np.diff(b[gi - 336:gi + 1])
    o["corr_30m_2d"] = np.corrcoef(ra2, rb2)[0, 1]
    o["corr_30m_7d"] = np.corrcoef(ra7, rb7)[0, 1]
    o["vol_ratio_2d"] = ra2.std(ddof=1) / rb2.std(ddof=1)
    o["vol_ratio_7d"] = ra7.std(ddof=1) / rb7.std(ddof=1)
    o["beta"], o["abs_beta"], o["sign_beta"] = be, abs(be), float(np.sign(be))
    o["neutrality"] = abs(1 - abs(be)) / (1 + abs(be))
    bs = np.array([beta_at(a, b, k) for k in range(gi - 335, gi + 1)])
    o["beta_stab"] = bs.std() / abs(bs.mean())
    first_beta = g0 + 95
    o["beta_chg_24h"] = be - beta_at(a, b, gi - 48) if gi - 48 >= first_beta else np.nan
    o["beta_chg_7d"] = be - beta_at(a, b, gi - 336) if gi - 336 >= first_beta else np.nan
    w = np.array([(a[k] - be * b[k] - al - mu) / sg for k in range(gi - 335, gi + 1)])
    o["crossings_7d"] = float(sum(1 for k in range(1, len(w)) if w[k] * w[k - 1] < 0))
    phi = np.polyfit(w[:-1], w[1:], 1)[0]
    o["phi_7d"] = phi
    o["halflife_h"] = -np.log(2) / np.log(phi) * 0.5 if 0 < phi < 1 else np.nan
    wf = w * s
    lvl = wf[-96:]
    o["vratio"] = np.diff(lvl).std() / max(lvl.std(), 1e-12) * VDIV
    dW = np.diff(wf)
    o["vol_slope"] = dW[-16:].std() / max(dW[-48:-16].std(), 1e-12)
    ha, la = hilo(c_a)
    hb, lb = hilo(c_b)
    gaps = []
    for k in range(gi - 95, gi + 1):
        if s > 0:
            top = ha[k] - be * (lb[k] if be > 0 else hb[k])
            g = top - (a[k] - be * b[k])
        else:
            bot = la[k] - be * (hb[k] if be > 0 else lb[k])
            g = -bot + (a[k] - be * b[k])
        if np.isfinite(g):
            gaps.append(g)
    o["sandwich"] = np.mean(gaps) / sg if gaps else np.nan
    # 1-minute
    T = pd.Timestamp(row.entry_time) + pd.Timedelta(minutes=29)
    mins = pd.date_range(T - pd.Timedelta(minutes=1440), T, freq="min")
    ca, ta_ = m1(c_a)
    cb, tb_ = m1(c_b)
    xa1, xb1 = ca.reindex(mins).to_numpy(), cb.reindex(mins).to_numpy()
    da, db = np.diff(xa1), np.diff(xb1)
    ok = np.isfinite(da) & np.isfinite(db)
    o["n_1m_24h"] = float(ok.sum())
    o["corr_1m_24h"] = np.corrcoef(da[ok], db[ok])[0, 1] if ok.sum() >= 1000 else np.nan
    o["g2_nan_1m"] = float(np.isnan(o["corr_1m_24h"]))
    tra = (ta_.reindex(mins[1:]).to_numpy() == 0)
    trb = (tb_.reindex(mins[1:]).to_numpy() == 0)
    o["both_traded_share_24h"] = float((tra & trb).sum()) / 1440.0
    o["seg_bars"] = float(row.bars_into_segment)
    return o


def main():
    t0 = time.time()
    E = pd.read_parquet(os.path.join(WORK, "events.parquet"))
    G = pd.read_parquet(os.path.join(WORK, "g2.parquet")).set_index("event_id")
    rng = np.random.default_rng(SEED)
    rows = np.sort(rng.choice(len(E), N, replace=False))
    bad, ncmp, mx = [], 0, 0.0
    for q, r in enumerate(rows):
        row = E.iloc[r]
        exp = expected(row)
        got = G.loc[int(row.event_id)]
        for nm, v in exp.items():
            g = float(got[nm])
            ncmp += 1
            if np.isnan(v) != np.isnan(g):
                bad.append((int(row.event_id), nm, v, g)); continue
            if np.isnan(v):
                continue
            err = abs(v - g); mx = max(mx, err / (1e-6 + 1e-4 * abs(v)))
            if err > 1e-6 + 1e-4 * abs(v):
                bad.append((int(row.event_id), nm, v, g))
        if (q + 1) % 500 == 0:
            print(f"  {q + 1} events  [{time.time() - t0:.0f}s]", flush=True)
    miss = [c for c in G.columns if c not in expected(E.iloc[rows[0]])]
    print(f"[G2 INDEP] {N} events x {len(exp)} columns = {ncmp:,} comparisons; mismatches {len(bad)}; worst error / tolerance {mx:.3f}; columns not recomputed: {miss}  [{time.time() - t0:.0f}s]")
    for b in bad[:20]:
        print("  MISMATCH", b)
    if bad:
        raise SystemExit("[G2 INDEP] FAILED")
    print("[G2 INDEP] PASS")


if __name__ == "__main__":
    main()
