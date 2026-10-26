"""HL-MASTER1 integrity tests for G2b (symmetric z), both units' construction, on pair events.

    python -u research/dataset/master_tests_g2b.py > research/dataset/logs/master_tests_g2b.log

  1. SWAP (asserted, 1,000 real events): z_sym' = -sign(beta) z_sym, sigma_sym' = sigma_sym / |beta|, trig_sym' = trig_sym, |z_sym'| = |z_sym|, threshold_sym' = threshold_sym.
  2. GLOBAL SIGN FLIP (negated log prices): z_sym -> -z_sym, sigma_sym, threshold_sym and trig_sym unchanged.
  3. POISON / TRUNCATION: the five columns at bar i do not change when every bar after i is overwritten with random values or removed.
  4. INDEPENDENT recomputation (plain numpy loops, direct window moments, no rolling objects) of 1,000 events against g2b.parquet.
  5. Cross-check against the stored geometry: sigma_sym equals the std of the frozen-geometry spread window with beta_i, alpha_i (the closed form), on 1,000 events.
"""
import os, sys, time
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import master_g2b as B
import universe_panel

rng = np.random.default_rng(20261027)


def setup():
    E = pd.read_parquet(os.path.join(B.WORK, "pair", "events.parquet"))
    G = pd.read_parquet(os.path.join(B.WORK, "pair", "g2b.parquet"))
    panel = universe_panel.drop_forming_bars(universe_panel.load_panel())
    V = panel.to_numpy(float)
    ix = {c: j for j, c in enumerate(panel.columns)}
    return E, G, V, ix


def seg(row, V, ix):
    g0, g1 = int(row.seg_start_bar), int(row.seg_end_bar)
    return V[g0:g1, ix[row.ticker_a]].copy(), V[g0:g1, ix[row.ticker_b]].copy(), int(row.bars_into_segment)


def at(a, b, i):
    s, z, t, tr = B.sym_series(a, b)
    return np.array([s[i], z[i], t[i], tr[i]])


def same(x, y, tol=0.0):
    return np.array_equal(x, y, equal_nan=True) if tol == 0 else np.allclose(x, y, rtol=tol, atol=tol, equal_nan=True)


def test_swap(E, G, V, ix, n=1000):
    bad = 0
    for r in rng.choice(len(E), n, replace=False):
        row = E.iloc[r]
        a, b, i = seg(row, V, ix)
        be = row.beta
        o = at(a, b, i)
        o2 = at(b, a, i)
        if not (abs(o2[1] + np.sign(be) * o[1]) < 1e-9 * (1 + abs(o[1])) and abs(o2[0] - o[0] / abs(be)) < 1e-9 * (1 + o[0] / abs(be))
                and abs(abs(o2[1]) - abs(o[1])) < 1e-9 * (1 + abs(o[1])) and (abs(o2[2] - o[2]) < 1e-9 * (1 + o[2])) and (o2[3] == o[3] or (np.isnan(o2[3]) and np.isnan(o[3])))):
            bad += 1
            print("  SWAP FAIL", int(row.event_id), o, o2, be)
    print(f"[G2b SWAP] {n} real events: z_sym' = -sign(beta) z_sym, sigma_sym' = sigma_sym/|beta|, |z_sym'| = |z_sym|, threshold and trig unchanged: failures {bad}")
    assert bad == 0
    print("[G2b SWAP] PASS")


def test_flip(E, V, ix, n=500):
    bad = 0
    for r in rng.choice(len(E), n, replace=False):
        a, b, i = seg(E.iloc[r], V, ix)
        o, o2 = at(a, b, i), at(-a, -b, i)
        if not (abs(o2[1] + o[1]) < 1e-9 * (1 + abs(o[1])) and abs(o2[0] - o[0]) < 1e-9 * (1 + o[0]) and abs(o2[2] - o[2]) < 1e-9 * (1 + o[2])
                and (o2[3] == o[3] or (np.isnan(o2[3]) and np.isnan(o[3])))):
            bad += 1
            print("  FLIP FAIL", int(E.iloc[r].event_id), o, o2)
    print(f"[G2b FLIP] {n} real events with negated log prices: z_sym flips, the rest unchanged: failures {bad}")
    assert bad == 0
    print("[G2b FLIP] PASS")


def test_poison(E, V, ix, n=1000):
    bad = 0
    for r in rng.choice(len(E), n, replace=False):
        a, b, i = seg(E.iloc[r], V, ix)
        base = at(a, b, i)
        p_a, p_b = a.copy(), b.copy()
        p_a[i + 1:] = rng.uniform(a.min() - 1, a.max() + 1, len(a) - i - 1)
        p_b[i + 1:] = rng.uniform(b.min() - 1, b.max() + 1, len(b) - i - 1)
        if not (same(base, at(p_a, p_b, i)) and same(base, at(a[:i + 1], b[:i + 1], i))):
            bad += 1
    print(f"[G2b POISON] {n} events, future overwritten and truncated: columns changed in {bad} events")
    assert bad == 0
    print("[G2b POISON] PASS")


def beta_at(a, b, k):
    xa, xb = a[k - 95:k + 1], b[k - 95:k + 1]
    cov = np.mean((xa - xa.mean()) * (xb - xb.mean()))
    return np.sign(cov) * xa.std() / xb.std()


def zsym_direct(a, b, k):
    be = beta_at(a, b, k)
    win = a[k - 95:k + 1] - be * b[k - 95:k + 1]
    sig = win.std(ddof=1)
    return sig, (a[k] - be * b[k] - (a[k - 95:k + 1].mean() - be * b[k - 95:k + 1].mean())) / sig


def test_indep(E, G, V, ix, n=2000):
    Gi = G.set_index("event_id")
    bad, mx = [], 0.0
    for r in np.sort(rng.choice(len(E), n, replace=False)):
        row = E.iloc[r]
        a, b, i = seg(row, V, ix)
        sig_i, z_i = zsym_direct(a, b, i)
        zs = np.array([zsym_direct(a, b, k)[1] for k in range(i - 97, i + 1)])        # bars i-97 .. i
        absz = np.abs(zs)
        thr_i = np.percentile(absz[1:97], 99.0)                                       # bars i-96 .. i-1  -> zs[1..96]
        thr_p = np.percentile(absz[0:96], 99.0)                                       # bars i-97 .. i-2  (threshold of bar i-1)
        trig = float(absz[97] > thr_i and absz[96] <= thr_p)
        exp = dict(sigma_sym=sig_i, z_sym=z_i, threshold_sym=thr_i, trig_sym=trig, z_ratio=abs(z_i) / abs(row.z))
        got = Gi.loc[int(row.event_id)]
        for k, v in exp.items():
            g = float(got[k])
            err = abs(v - g)
            mx = max(mx, err / (1e-6 + 1e-4 * abs(v)))
            if err > 1e-6 + 1e-4 * abs(v):
                bad.append((int(row.event_id), k, v, g))
    print(f"[G2b INDEP] {n} events x 5 columns: mismatches {len(bad)}; worst error / tolerance {mx:.3f}")
    for b_ in bad[:10]:
        print("  MISMATCH", b_)
    assert not bad
    print("[G2b INDEP] PASS")
    # the closed form against the frozen-geometry window
    worst = 0.0
    for r in rng.choice(len(E), 1000, replace=False):
        row = E.iloc[r]
        a, b, i = seg(row, V, ix)
        win = a[i - 95:i + 1] - row.beta * b[i - 95:i + 1] - row.alpha
        worst = max(worst, abs(win.std(ddof=1) - float(Gi.loc[int(row.event_id)].sigma_sym)) / win.std(ddof=1))
        assert abs(win.mean()) < 1e-9 * (1 + abs(win).max()), "window mean of the frozen-geometry spread is not 0"
    print(f"[G2b CLOSED FORM] sigma_sym equals the std of the frozen-geometry window (beta_i, alpha_i) on 1,000 events: worst relative difference {worst:.2e}; window mean 0")
    assert worst < 1e-4


def main():
    t0 = time.time()
    E, G, V, ix = setup()
    print(f"[TESTS G2b] {len(E):,} events [{time.time() - t0:.0f}s]", flush=True)
    test_swap(E, G, V, ix)
    test_flip(E, V, ix)
    test_poison(E, V, ix)
    test_indep(E, G, V, ix)
    print(f"[TESTS G2b] ALL PASS [{time.time() - t0:.0f}s]")


if __name__ == "__main__":
    main()
