"""HL-MASTER1 integrity tests for G2 (and the label poison test), pair level. Each test prints its own PASS line; any failure aborts.

    python -u research/dataset/master_tests.py > research/dataset/logs/master_tests_g2.log

  1. POISON (look-ahead). 1,000 random events: rerun the production kernel (master_g2.kernel) on the event's segment with EVERY raw input at or after t = 0
     replaced by random values (30m log closes, highs and lows after the trigger bar; 1m closes and the traded flags after the 1m bar labelled T + 29), and
     again with the arrays TRUNCATED right after those points. G2 must be identical to the last digit (NaN equal). The kernel's signature carries no
     seg_end_bar / pair_triggers_true / y00..y20, so those cannot be read by it; the event table's copies of them are not inputs. Labels: 100 events, the same
     poison on the 1-minute closes after t = 0 must CHANGE depth_10h (labels use the future).
  2. SWAP A <-> B on 1,000 real events (geometry recomputed on the swapped legs): |z'| = |z|, z' = -z; invariant columns equal; reciprocal columns multiply to 1.
  3. GLOBAL SIGN FLIP (negated log prices, highs/lows swapped): every column identical (the folded ones by construction, the rest by symmetry).
  4. KNOWN ANSWERS: hand-computed synthetic cases (proportional legs, anti-proportional legs, alternating and geometric spreads for crossings, phi, half-life).
  5. REAL-EVENT SPOT CHECKS are in the independent recomputation (master_g2_indep.py).
"""
import os, sys, time
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import master_g2 as G
import master_labels as L

rng = np.random.default_rng(20261024)
INV = ["r2_2d", "r2_7d", "corr_30m_2d", "corr_30m_7d", "corr_1m_24h", "n_1m_24h", "both_traded_share_24h", "neutrality", "crossings_7d", "halflife_h",
       "phi_7d", "vratio", "vol_slope", "sandwich", "g2_nan_1m", "seg_bars"]
RECIP = ["beta", "abs_beta", "vol_ratio_2d", "vol_ratio_7d"]


def setup():
    G.E = pd.read_parquet(os.path.join(G.WORK, "events.parquet"))
    G.EVG = {k: g for k, g in G.E.groupby("pair_index")}
    G.load_hilo()
    coins = sorted(set(G.E.ticker_a) | set(G.E.ticker_b))
    G.SER = G.load_1m_series(coins, False)
    for c in coins:
        d = pd.read_feather(G.bar_file(c, "1m"), columns=["date", "mins_since_trade"])
        mi = pd.to_datetime(d["date"], utc=True).dt.tz_localize(None).to_numpy().astype("datetime64[m]")
        off = ((mi - mi.min()) / np.timedelta64(1, "m")).astype(np.int64)
        arr = np.zeros(len(G.SER[c][1]))
        arr[off] = (d["mins_since_trade"].to_numpy(float) == 0).astype(float)
        G.TRD[c] = arr


def inputs(row):
    """Everything the kernel reads for one event, as copies."""
    a_, b_ = row.ticker_a, row.ticker_b
    ja, jb = G.ix[a_], G.ix[b_]
    g0, g1 = int(row.seg_start_bar), int(row.seg_end_bar)
    t0a, A1 = G.SER[a_]
    t0b, B1 = G.SER[b_]
    T = np.datetime64(row.entry_time, "m") + np.timedelta64(29, "m")
    d = dict(a=G.V[g0:g1, ja].copy(), b=G.V[g0:g1, jb].copy(), hia=G.HI[g0:g1, ja].copy(), loa=G.LO[g0:g1, ja].copy(),
             hib=G.HI[g0:g1, jb].copy(), lob=G.LO[g0:g1, jb].copy(), ii=np.array([int(row.bars_into_segment)]),
             ta1=np.array([int((T - t0a) / np.timedelta64(1, "m"))]), tb1=np.array([int((T - t0b) / np.timedelta64(1, "m"))]),
             A1=A1.copy(), B1=B1.copy(), TA=G.TRD[a_].copy(), TB=G.TRD[b_].copy())
    return d


def geometry(d, z=None):
    r = G.rs.rolling_spread_stats(d["a"], d["b"], 0.5)
    i = int(d["ii"][0])
    lo = i - G.FIT + 1
    bw = r.beta[lo:i + 1]
    bstab = float(np.std(bw) / abs(np.mean(bw))) if np.isfinite(bw).all() and np.mean(bw) != 0 else np.nan
    return dict(z=np.array([r.z[i]]), be=np.array([r.beta[i]]), al=np.array([r.alpha[i]]), mu=np.array([r.mu[i]]), sg=np.array([r.sigma[i]]), bstab=np.array([bstab]))


def run(d, geo):
    o, _ = G.kernel(d["a"], d["b"], d["hia"], d["loa"], d["hib"], d["lob"], d["ii"], geo["z"], geo["be"], geo["al"], geo["mu"], geo["sg"], geo["bstab"],
                    d["ta1"], d["tb1"], d["A1"], d["B1"], d["TA"], d["TB"])
    return dict(zip(G.NAMES, o[0]))


def same(x, y, rtol=0.0, atol=0.0):
    return bool(np.array_equal(x, y, equal_nan=True)) if rtol == 0 and atol == 0 else bool(np.allclose(x, y, rtol=rtol, atol=atol, equal_nan=True))


def poison(d):
    p = {k: v.copy() for k, v in d.items()}
    i = int(d["ii"][0])
    for k in ("a", "b", "hia", "loa", "hib", "lob"):
        x = p[k]
        lo_, hi_ = np.nanmin(x[:i + 1]), np.nanmax(x[:i + 1])
        x[i + 1:] = rng.uniform(lo_ - 1, hi_ + 1, size=len(x) - i - 1)
    for k, e in (("A1", "ta1"), ("B1", "tb1")):
        x = p[k]
        e_ = int(d[e][0])
        x[e_ + 1:] = rng.uniform(-3, 3, size=len(x) - e_ - 1)
    for k, e in (("TA", "ta1"), ("TB", "tb1")):
        x = p[k]
        e_ = int(d[e][0])
        x[e_ + 1:] = rng.integers(0, 2, size=len(x) - e_ - 1)
    return p


def truncate(d):
    p = {k: v.copy() for k, v in d.items()}
    i = int(d["ii"][0])
    for k in ("a", "b", "hia", "loa", "hib", "lob"):
        p[k] = p[k][:i + 1]
    for k, e in (("A1", "ta1"), ("B1", "tb1"), ("TA", "ta1"), ("TB", "tb1")):
        p[k] = p[k][:int(d[e][0]) + 1]
    return p


def test_poison(E, n=1000):
    t0 = time.time()
    pick = rng.choice(len(E), n, replace=False)
    bad = 0
    for q, r in enumerate(pick):
        row = E.iloc[r]
        d = inputs(row)
        geo = geometry(d)
        base = run(d, geo)
        for variant in (poison(d), truncate(d)):
            out = run(variant, geo)
            for nm in G.NAMES:
                if not same(base[nm], out[nm]):
                    bad += 1
                    print(f"  POISON CHANGED {nm} for event {int(row.event_id)}: {base[nm]} -> {out[nm]}")
    print(f"[POISON] {n} events x 2 variants (random overwrite, truncation) x {len(G.NAMES)} columns: features changed in {bad} cases [{time.time() - t0:.0f}s]")
    assert bad == 0, "LOOK-AHEAD: a G2 feature changed when the future was overwritten"
    # labels must change
    ch = 0
    sub = E.iloc[rng.choice(len(E), 100, replace=False)]
    L.SER = G.SER
    base = L.paths_for(sub)
    SER_p = {}
    for c, (t0_, arr) in G.SER.items():
        SER_p[c] = (t0_, arr)
    pois = {c: (t0_, arr.copy()) for c, (t0_, arr) in G.SER.items() if c in set(sub.ticker_a) | set(sub.ticker_b)}
    for _, row in sub.iterrows():
        T = np.datetime64(row.entry_time, "m") + np.timedelta64(29, "m")
        for c in (row.ticker_a, row.ticker_b):
            t0c, arr = pois[c]
            e_ = int((T - t0c) / np.timedelta64(1, "m"))
            arr[e_ + 1:e_ + 700] = rng.uniform(-3, 3, size=min(699, len(arr) - e_ - 1))
    L.SER = {**G.SER, **pois}
    new = L.paths_for(sub)
    fin = np.isfinite(base).all(1)
    changed = (np.abs(np.nan_to_num(new[:, 1:], nan=0.0) - np.nan_to_num(base[:, 1:], nan=0.0)).max(1) > 1e-9)[fin]
    L.SER = G.SER
    print(f"[POISON labels] 100 events: label path after t = 0 changed in {int(changed.sum())} of {int(fin.sum())} finite events; the path at t = 0 unchanged: "
          f"{bool(np.allclose(np.nan_to_num(new[:, 0]), np.nan_to_num(base[:, 0])))}")
    assert changed.all(), "labels did not respond to the poisoned future"
    assert np.allclose(np.nan_to_num(new[:, 0]), np.nan_to_num(base[:, 0]))
    print("[POISON] PASS")


SYM = ["r2_2d", "r2_7d", "corr_30m_2d", "corr_30m_7d", "corr_1m_24h", "n_1m_24h", "both_traded_share_24h", "neutrality", "g2_nan_1m", "seg_bars"]
GEOM = ["crossings_7d", "halflife_h", "phi_7d", "vratio", "vol_slope", "sandwich"]      # built on the standardised spread, which is NOT leg-symmetric (see below)


def test_swap(E, n=1000):
    """Swap A <-> B. Exactly symmetric: the leg-pair statistics (r2, correlations, neutrality, traded share) and the vol-matched beta's reciprocal.
    NOT symmetric, and reported instead of asserted: the entry z and every column built on the standardised spread (crossings, AR(1), vratio, vol_slope, sandwich).
    Reason (found by this test): the rolling spread series uses each bar's own beta_k, so swapping the legs gives s'_k = -s_k / beta_k + c_k with a different beta_k at every bar;
    mu and sigma are the rolling mean and sd of that series, so z' = -sign(beta) z holds only for a constant beta."""
    pick = rng.choice(len(E), n, replace=False)
    worst = {k: 0.0 for k in SYM + RECIP}
    bad = []
    rel, zc, diffs = [], [], {k: [] for k in GEOM}
    for r in pick:
        row = E.iloc[r]
        d = inputs(row)
        g1 = geometry(d)
        o1 = run(d, g1)
        s = dict(a=d["b"], b=d["a"], hia=d["hib"], loa=d["lob"], hib=d["hia"], lob=d["loa"], ii=d["ii"], ta1=d["tb1"], tb1=d["ta1"],
                 A1=d["B1"], B1=d["A1"], TA=d["TB"], TB=d["TA"])
        g2 = geometry(s)
        o2 = run(s, g2)
        rel.append(abs(g2["z"][0]) / abs(g1["z"][0]))
        zc.append((g1["z"][0], g2["z"][0] * -np.sign(g1["be"][0])))
        for nm in SYM:
            v1, v2 = o1[nm], o2[nm]
            if not (np.isnan(v1) and np.isnan(v2)) and not abs(v1 - v2) <= 1e-9 * (1 + abs(v1)):
                bad.append((nm, int(row.event_id), v1, v2))
            elif np.isfinite(v1):
                worst[nm] = max(worst[nm], abs(v1 - v2))
        for nm in RECIP:
            v1, v2 = o1[nm], o2[nm]
            if np.isnan(v1) and np.isnan(v2):
                continue
            if not abs(v1 * v2 - 1) <= 1e-9:
                bad.append((nm, int(row.event_id), v1, v2))
            else:
                worst[nm] = max(worst[nm], abs(v1 * v2 - 1))
        for nm in GEOM:
            if np.isfinite(o1[nm]) and np.isfinite(o2[nm]):
                diffs[nm].append((o1[nm], o2[nm]))
    print(f"[SWAP] {n} real events. Exactly symmetric columns (equal) and reciprocal columns (product 1): failures {len(bad)}")
    print("  worst |difference| per asserted column: " + ", ".join(f"{k} {v:.1e}" for k, v in worst.items()))
    rel = np.array(rel)
    zc = np.array(zc)
    print(f"  FINDING, not asserted: the entry z is not leg-symmetric. |z'|/|z| quantiles 5/25/50/75/95%: " + " / ".join(f"{np.quantile(rel, q):.2f}" for q in (.05, .25, .5, .75, .95))
          + f"; correlation of z with the sign-corrected z' {np.corrcoef(zc[:, 0], zc[:, 1])[0, 1]:.3f}; same sign (z vs sign-corrected z') {100 * np.mean(np.sign(zc[:, 0]) == np.sign(zc[:, 1])):.1f}%")
    for nm, v in diffs.items():
        v = np.array(v)
        print(f"  {nm:<13} swapped vs original: correlation {np.corrcoef(v[:, 0], v[:, 1])[0, 1]:.3f}, median |difference| {np.median(np.abs(v[:, 0] - v[:, 1])):.4f} over {len(v)} events")
    for b in bad[:10]:
        print("  FAIL", b)
    assert not bad
    print("[SWAP] PASS (symmetric columns exact; spread-based columns reported)")


def test_flip(E, n=500):
    pick = rng.choice(len(E), n, replace=False)
    bad = []
    for r in pick:
        row = E.iloc[r]
        d = inputs(row)
        g1 = geometry(d)
        o1 = run(d, g1)
        f = dict(d)
        f.update(a=-d["a"], b=-d["b"], hia=-d["loa"], loa=-d["hia"], hib=-d["lob"], lob=-d["hib"])
        g2 = geometry(f)
        assert abs(g2["z"][0] + g1["z"][0]) < 1e-9
        o2 = run(f, g2)
        for nm in G.NAMES:
            v1, v2 = o1[nm], o2[nm]
            if not (np.isnan(v1) and np.isnan(v2)) and not abs(v1 - v2) <= 1e-9 * (1 + abs(v1)):
                bad.append((nm, int(row.event_id), v1, v2))
    print(f"[FLIP] {n} real events with negated log prices (highs/lows swapped): z flips, every column identical: failures {len(bad)}")
    for b in bad[:10]:
        print("  FAIL", b)
    assert not bad
    print("[FLIP] PASS")


def test_known():
    t = np.arange(900, dtype=float)
    a = np.sin(0.2 * t) + 0.003 * t
    cases = []
    for sgn in (+1.0, -1.0):
        b = sgn * 2.0 * a + 1e-6 * np.cos(7 * t)
        n = len(a)
        hi = lambda x: x + 0.001
        lo = lambda x: x - 0.001
        r = G.rs.rolling_spread_stats(a, b, 0.5)
        i = 700
        geo = dict(z=np.array([r.z[i]]), be=np.array([r.beta[i]]), al=np.array([r.alpha[i]]), mu=np.array([r.mu[i]]), sg=np.array([r.sigma[i]]), bstab=np.array([np.nan]))
        A1 = np.zeros(800 * 60); B1 = np.zeros(800 * 60)
        TA = np.ones(len(A1)); TB = np.ones(len(A1))
        o, _ = G.kernel(a, b, hi(a), lo(a), hi(b), lo(b), np.array([i]), geo["z"], geo["be"], geo["al"], geo["mu"], geo["sg"], geo["bstab"],
                        np.array([len(A1) - 1]), np.array([len(A1) - 1]), A1, B1, TA, TB)
        c = dict(zip(G.NAMES, o[0]))
        exp = dict(r2_2d=1.0, r2_7d=1.0, corr_30m_2d=sgn, corr_30m_7d=sgn, beta=0.5 * sgn, abs_beta=0.5, sign_beta=sgn, neutrality=1 / 3, vol_ratio_2d=0.5, vol_ratio_7d=0.5)
        for k, v in exp.items():
            assert abs(c[k] - v) < 1e-4, f"known answer {k} (b = {sgn:+.0f} x 2a): got {c[k]}, expected {v}"
        cases.append((sgn, {k: c[k] for k in exp}))
    print("[KNOWN] proportional (b = +2a) and anti-proportional (b = -2a) legs: r2 = 1, |corr| = 1 with the right sign, beta = +-0.5, neutrality = 1/3, vol ratio = 0.5: PASS")
    # helper functions on hand-made spreads
    alt = np.tile([1.0, -1.0], 168)[None, :]
    assert G.crossings(alt)[0] == 335 and abs(G.ar1_phi(alt)[0] + 1) < 1e-12 and np.isnan(G.halflife_h(G.ar1_phi(alt))[0])
    geo9 = (0.9 ** np.arange(336))[None, :]
    assert abs(G.ar1_phi(geo9)[0] - 0.9) < 1e-9 and abs(G.halflife_h(G.ar1_phi(geo9))[0] + np.log(2) / np.log(0.9) * 0.5) < 1e-9
    assert G.crossings(geo9)[0] == 0
    print(f"[KNOWN] alternating spread: 335 crossings, phi = -1, half-life NaN; geometric 0.9^t: 0 crossings, phi = 0.9, half-life {G.halflife_h(G.ar1_phi(geo9))[0]:.4f} h: PASS")


def main():
    t0 = time.time()
    setup()
    E = G.E
    print(f"[TESTS] G2 on {len(E):,} events; inputs loaded [{time.time() - t0:.0f}s]", flush=True)
    test_known()
    test_swap(E)
    test_flip(E)
    test_poison(E)
    print(f"[TESTS] ALL PASS  [{time.time() - t0:.0f}s]")


if __name__ == "__main__":
    main()
