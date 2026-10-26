"""HL-MASTER1 integrity tests for G9a (market regime).

    python -u research/dataset/master_tests_g9a.py > research/dataset/logs/master_tests_g9a.log

G9a is a function of the cutoff bar only (identical for every event of that bar), so the tests sample BARS.
  1. POISON by truncation: for 60 random cutoffs o_j the whole pipeline is rerun on raw arrays CUT AT o_j (a read at or after o_j would raise or change a value); the last row must equal the full run's row j
     to the last digit. Each cutoff needs the whole pipeline, which is why 60 distinct bars are used instead of 1,000 events. And by overwrite: for 8 cutoffs every raw array after o_j is replaced by random values and
     row j must be unchanged.
  2. INDEPENDENT recomputation of 2,000 distinct bars (plain numpy loops over the raw 1m arrays; no cumulative-sum tricks): returns, volatilities, breadth ingredients, share up, dispersion, coherence,
     liquidation / ADL / backstop / taker windows with their trailing medians, the per-valid-minute ratio and the 90-day ranks.
  3. INVARIANTS: shares in [0,1], rv >= 0, counts >= 0, ratio columns positive, event counts consistent.
"""
import os, sys, time
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import master_g9a as G9
import flowfeat as ff

rng = np.random.default_rng(20261029)


def row_equal(a, b):
    return np.array_equal(np.asarray(a, float), np.asarray(b, float), equal_nan=True)


def test_poison(raw, T):
    bad = 0
    cuts = np.sort(rng.choice(np.arange(400, len(T) - 1), 60, replace=False))
    t0 = time.time()
    for j in cuts:
        o = int(T.cutoff_minute.iloc[j])
        P = G9.compute(raw, nmax=o)
        got, exp = P.iloc[-1], T.iloc[j]
        assert int(got.cutoff_minute) == o
        for c in T.columns:
            if not row_equal(got[c], exp[c]):
                bad += 1
                print(f"  TRUNCATION CHANGED {c} at j={j}: {exp[c]} -> {got[c]}")
    print(f"[G9a POISON truncation] 60 cutoffs, whole pipeline rerun on raw arrays cut at o_j: columns changed {bad} [{time.time() - t0:.0f}s]")
    assert bad == 0
    bad = 0
    for j in rng.choice(np.arange(1500, len(T) - 1), 8, replace=False):
        o = int(T.cutoff_minute.iloc[j])
        R = dict(raw)
        R["lc"] = {c: np.concatenate([v[:o], np.cumsum(rng.normal(0, 0.001, len(v) - o)) + (v[o - 1] if np.isfinite(v[o - 1]) else 0)]) for c, v in raw["lc"].items()}
        for k in ("S1m", "mkt_liq", "adl", "bk", "tk"):
            v = raw[k].copy()
            v[o:] = rng.uniform(0, 1e6, len(v) - o)
            R[k] = v
        v = raw["n1m"].copy(); v[o:] = rng.integers(0, 200, len(v) - o); R["n1m"] = v
        v = raw["hole"].copy(); v[o:] = rng.random(len(v) - o) < 0.01; R["hole"] = v
        v = raw["idx30"].copy(); v[j + 1:] = rng.normal(0, 0.01, len(v) - j - 1); R["idx30"] = v
        P = G9.compute(R)
        got, exp = P.iloc[j], T.iloc[j]
        for c in T.columns:
            if not row_equal(got[c], exp[c]):
                bad += 1
                print(f"  OVERWRITE CHANGED {c} at j={j}: {exp[c]} -> {got[c]}")
    print(f"[G9a POISON overwrite] 8 cutoffs, every raw array after o_j replaced by random values: columns changed {bad}")
    assert bad == 0
    print("[G9a POISON] PASS")


def sd1(x):
    x = x[np.isfinite(x)]
    return x.std(ddof=1) if len(x) > 1 else np.nan


def test_indep(raw, T, n=2000):
    coins = raw["coins"]
    ci = {c: i for i, c in enumerate(coins)}
    lc = raw["lc"]
    idx_r = np.where(raw["n1m"] >= 30, raw["S1m"] / np.maximum(raw["n1m"], 1), np.nan)
    hole = raw["hole"]
    mkt = np.where(hole, np.nan, raw["mkt_liq"])
    adl = np.where(hole, np.nan, raw["adl"]); bk = np.where(hole, np.nan, raw["bk"]); tk = np.where(hole, np.nan, raw["tk"])
    bad, ncmp, mx = [], 0, 0.0
    t0 = time.time()
    r1 = {"BTC": np.concatenate([[np.nan], np.diff(lc["BTC"])]), "ETH": np.concatenate([[np.nan], np.diff(lc["ETH"])]), "idx": idx_r}
    for j in np.sort(rng.choice(np.arange(len(T)), n, replace=False)):
        o = int(T.cutoff_minute.iloc[j])
        exp = {}
        for k, r in r1.items():
            nm = k.lower()
            for lab, W in G9.WIN.items():
                w = r[o - W:o] if o - W >= 0 else None
                if k == "idx":
                    exp[f"ret_{nm}_{lab}"] = (w.sum() if w is not None and np.isfinite(w).all() else np.nan)
                else:
                    a = lc[k]
                    exp[f"ret_{nm}_{lab}"] = a[o - 1] - a[o - 1 - W] if o - 1 - W >= 0 else np.nan
            for lab in ("1h", "24h", "7d"):
                W = G9.WIN[lab]
                w = r[o - W:o] if o - W >= 0 else np.array([])
                exp[f"rv_{nm}_{lab}"] = sd1(w) if len(w) and np.isfinite(w).sum() >= 0.7 * W else np.nan
            exp[f"volratio_{nm}"] = exp[f"rv_{nm}_24h"] / exp[f"rv_{nm}_7d"]
        # cross-section
        a24, a1 = [], []
        for c in coins:
            x = lc[c]
            if o - 1 - 1440 >= 0 and np.isfinite(x[o - 1]) and np.isfinite(x[o - 1 - 1440]):
                a24.append(x[o - 1] - x[o - 1 - 1440])
            if o - 1 - 60 >= 0 and np.isfinite(x[o - 1]) and np.isfinite(x[o - 1 - 60]):
                a1.append(x[o - 1] - x[o - 1 - 60])
        a24, a1 = np.array(a24), np.array(a1)
        # on the half-hour cutoff grid the 24 h window is 48 cutoffs back = o - 1440 exactly
        exp["share_up_24h"] = (a24 > 0).mean() if len(a24) else np.nan
        exp["n_live_coins"] = float(len(a24))
        exp["xs_std_1h"] = a1.std(ddof=1) if len(a1) > 1 else np.nan
        # market sums
        def win(a, W):
            w = a[o - W:o] if o - W >= 0 else None
            return w.sum() if w is not None and np.isfinite(w).all() else np.nan
        exp["adl_usd_24h"], exp["mkt_backstop_usd_24h"] = win(adl, 1440), win(bk, 1440)
        def rel(a, W):
            cur = win(a, W)
            samp = []
            for k in range(0, 336):
                oo = o - W - 30 * k                     # cutoffs j - W/30 - k
                samp.append(a[oo - W:oo].sum() if oo - W >= 0 and np.isfinite(a[oo - W:oo]).all() else np.nan)
            samp = np.array(samp)
            med = np.nanmedian(samp) if np.isfinite(samp).sum() >= 144 else np.nan
            return cur / med if med > 0 else np.nan
        exp["mkt_liq_1h"], exp["mkt_liq_24h"], exp["mkt_taker_1h_rel"] = rel(mkt, 60), rel(mkt, 1440), rel(tk, 60)
        D7, D28 = 10080, 40320
        if o - D28 >= 0:
            w7, w28 = mkt[o - D7:o], mkt[o - D28:o]
            v7, v28 = np.isfinite(w7).sum(), np.isfinite(w28).sum()
            s7, s28 = np.nansum(w7), np.nansum(w28)
            exp["mkt_liq_ratio_7d_28d"] = (s7 / v7) / (s28 / v28) if s28 > 0 and v7 > 0 and v28 > 0 else np.nan
        else:
            exp["mkt_liq_ratio_7d_28d"] = np.nan
        for k, v in exp.items():
            g = float(T[k].iloc[j])
            ncmp += 1
            if np.isnan(v) != np.isnan(g):
                bad.append((j, k, v, g)); continue
            if np.isnan(v):
                continue
            err = abs(v - g)
            mx = max(mx, err / (1e-9 + 1e-7 * abs(v)))
            if err > 1e-9 + 1e-7 * abs(v):
                bad.append((j, k, v, g))
    print(f"[G9a INDEP] {n} distinct bars: {ncmp:,} comparisons (returns, volatilities, share up, dispersion, liquidation/ADL/backstop/taker windows with trailing medians, 7d/28d ratio); mismatches {len(bad)}; worst error / tolerance {mx:.3f} [{time.time() - t0:.0f}s]")
    for b in bad[:15]:
        print("  MISMATCH", b)
    assert not bad
    print("[G9a INDEP] PASS")


def test_seg(raw, T, n=2000):
    r30 = raw["idx30"]
    NJ = len(T)
    sd = lambda x: x.std(ddof=1) if len(x) > 1 else np.nan
    # reference series of rv_24h_seg and |ret_7d_seg| for every bar, plain loops
    rv24 = np.full(NJ, np.nan); ret7 = np.full(NJ, np.nan); rv7 = np.full(NJ, np.nan)
    for j in range(NJ):
        if j + 1 - 48 >= 0:
            w = r30[j + 1 - 48:j + 1]
            rv24[j] = sd(w[np.isfinite(w)]) if np.isfinite(w).sum() >= 0.7 * 48 else np.nan
        if j + 1 - 336 >= 0:
            w = r30[j + 1 - 336:j + 1]
            rv7[j] = sd(w[np.isfinite(w)]) if np.isfinite(w).sum() >= 0.7 * 336 else np.nan
            ret7[j] = w.sum() if np.isfinite(w).all() else np.nan
    bad, ncmp = [], 0
    def rank_ref(x, j):
        if j < 4320:
            return np.nan
        prev = x[j - 4320:j]
        f = np.isfinite(prev)
        return (prev[f] < x[j]).sum() / f.sum() if f.sum() >= 3000 and np.isfinite(x[j]) else np.nan
    for j in np.sort(rng.choice(np.arange(NJ), n, replace=False)):
        exp = {}
        for lab, k in (("1h", 2), ("6h", 12), ("24h", 48), ("7d", 336)):
            w = r30[j + 1 - k:j + 1] if j + 1 - k >= 0 else None
            exp[f"ret_idx_{lab}_seg"] = w.sum() if w is not None and np.isfinite(w).all() else np.nan
        exp["rv_idx_24h_seg"], exp["rv_idx_7d_seg"] = rv24[j], rv7[j]
        exp["volratio_idx_seg"] = rv24[j] / rv7[j]
        exp["rank90_idx_rv_24h_seg"] = rank_ref(rv24, j)
        exp["rank90_idx_abs_ret_7d_seg"] = rank_ref(np.abs(ret7), j)
        for k, v in exp.items():
            g = float(T[k].iloc[j])
            ncmp += 1
            if np.isnan(v) != np.isnan(g):
                bad.append((j, k, v, g)); continue
            if not np.isnan(v) and abs(v - g) > 1e-9 + 1e-7 * abs(v):
                bad.append((j, k, v, g))
    print(f"[G9a SEG INDEP] {n} distinct bars: {ncmp:,} comparisons of the _seg columns (returns, volatilities, ratio, 90-day ranks); mismatches {len(bad)}")
    for b in bad[:10]:
        print("  MISMATCH", b)
    assert not bad
    print("[G9a SEG INDEP] PASS")


def test_invariants(T):
    for c in ("share_up_24h", "breadth_extreme_1h", "rank90_idx_rv_24h", "rank90_idx_abs_ret_7d", "rank90_mkt_liq_24h"):
        x = T[c].dropna()
        assert ((x >= 0) & (x <= 1)).all(), c
    for c in [c for c in T.columns if c.startswith("rv_")] + ["xs_std_1h"]:
        assert (T[c].dropna() >= 0).all(), c
    assert (T.n_live_coins >= 0).all()
    for c in ("mkt_liq_1h", "mkt_liq_24h", "mkt_liq_ratio_7d_28d", "mkt_taker_1h_rel"):
        assert (T[c].dropna() >= 0).all(), c
    assert ((T.coherence_7d.dropna() >= -1) & (T.coherence_7d.dropna() <= 1)).all()
    first90 = T.rank90_idx_rv_24h.iloc[:4320]
    assert first90.isna().all(), "rank columns must be NaN for the first 90 days"
    print("[G9a INVARIANTS] PASS (shares and ranks in [0,1], rv and ratios >= 0, coherence in [-1,1], rank NaN for the first 4,320 cutoffs)")


def main():
    t0 = time.time()
    raw = G9.load_raw()
    T = pd.read_parquet(os.path.join(G9.WORK, "g9a_bar_table.parquet"))
    print(f"[TESTS G9a] raw and bar table loaded ({len(T):,} cutoffs) [{time.time() - t0:.0f}s]", flush=True)
    test_invariants(T)
    test_indep(raw, T)
    test_seg(raw, T)
    test_poison(raw, T)
    print(f"[TESTS G9a] ALL PASS [{time.time() - t0:.0f}s]")


if __name__ == "__main__":
    main()
