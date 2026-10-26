"""HL-MASTER1 integrity tests for G8 (order book at t0).

    python -u research/dataset/master_tests_g8.py > research/dataset/logs/master_tests_g8.log

  1. INVARIANTS: crossed rows are NaN in every quantity; snapshot_age_s in (0, 60]; depth non-decreasing across bands (d10 <= d25 <= d50); book_reach >= 0; imbalance in [-1, 1]; trunc flags in {0, 1};
     d_X = a_X - b_X exactly; pair rows with the same coin on both legs do not exist.
  2. INDEPENDENT recomputation (3,000 events, rel_* on 300): the row labelled o - 1 read straight from the raw daily l2 parquets; the 336 earlier cutoff rows read the same way; the median in plain numpy.
  3. POISON: for 12 coins and 3 cutoffs each (36 trials), every row labelled at or after the cutoff's t0 (cutoff j' > j) is overwritten with random values; all features at cutoffs <= j are identical.
  4. AS-OF: a row labelled o (first snapshot at or after t0) overwritten changes nothing at cutoff j; the row labelled o - 1 overwritten changes the value; a missing o - 1 row gives NaN (nothing carried).
"""
import os, sys, time, glob
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import master_g8 as G8
import master_g8_run as R8
import master_g5_run as R5
import flowfeat as ff

rng = np.random.default_rng(20261025)
_cache = {}


def raw_row(coin, m):
    """The raw l2 row (coin, epoch minute m) from the daily parquet of m's UTC day, or None."""
    day = pd.Timestamp(m * 60, unit="s").strftime("%Y%m%d")
    if day not in _cache:
        if len(_cache) > 6:
            _cache.clear()
        p = os.path.join(R8.L2DIR, f"{day}_l2.parquet")
        _cache[day] = pd.read_parquet(p) if os.path.exists(p) else None
    D = _cache[day]
    if D is None:
        return None
    r = D[(D.coin == coin) & (D.minute == m)]
    return None if r.empty else r.iloc[0]


def ref_vec(coin, j):
    """BASE values of the cutoff-j row of a coin, straight from raw (NaN vector when missing)."""
    m = G8.EM0 + ff.CUT_PHASE + 30 * j - 1
    r = raw_row(coin, m)
    return np.full(len(G8.BASE), np.nan) if r is None else r[G8.BASE].to_numpy(float)


def test_invariants(G):
    for u, df in G.items():
        for lg in (("a", "b") if u == "pair" else ("a",)):
            cr = df[f"{lg}_crossed"] == 1
            for c in G8.NAMES:
                if c in ("crossed",) or not c[0:3] in ("mid", "spr", "bid", "ask", "imb", "sli", "boo") and not c.startswith(("rel", "chg")):
                    continue
                assert df.loc[cr, f"{lg}_{c}"].isna().all(), (u, lg, c, "crossed row has a value")
            age = df[f"{lg}_snapshot_age_s"].dropna()
            assert ((age > 0) & (age <= 60)).all(), (u, lg, float(age.min()), float(age.max()))
            for s in ("bid", "ask"):
                x10, x25, x50 = (df[f"{lg}_{s}_d{b}"] for b in (10, 25, 50))
                ok = x10.notna() & x25.notna() & x50.notna()
                assert ((x10[ok] <= x25[ok] + 1e-3) & (x25[ok] <= x50[ok] + 1e-3)).all(), (u, lg, s, "depth not monotone in the band")
                assert (df[f"{lg}_book_reach_{s}_bp"].dropna() >= 0).all()
                for b in (10, 25, 50):
                    assert set(df[f"{lg}_trunc_{s}_{b}"].dropna().unique()) <= {0.0, 1.0}
            for b in (10, 25, 50):
                x = df[f"{lg}_imb_{b}"].dropna()
                assert ((x >= -1 - 1e-6) & (x <= 1 + 1e-6)).all()
        if u == "pair":
            for nm in G8.NAMES:
                if nm in G8.NO_DIFF:
                    continue
                a, b, d = df[f"a_{nm}"].to_numpy(np.float64), df[f"b_{nm}"].to_numpy(np.float64), df[f"d_{nm}"].to_numpy(np.float64)
                ok = np.isfinite(a) & np.isfinite(b)
                assert np.allclose(d[ok], (np.float32(a[ok]) - np.float32(b[ok])), rtol=1e-5, atol=1e-5, equal_nan=True), (nm, "d != a - b")
                assert np.isnan(d[~ok]).all()
    print("[G8 INVARIANTS] PASS (crossed rows NaN, age in (0, 60], depth monotone in band, reach >= 0, imb in [-1, 1], trunc in {0,1}, d = a - b)")


def test_indep(G, ev, n, n_rel):
    t0 = time.time()
    bad, ncmp = [], 0
    for u in ("pair", "coin"):
        E, o = ev[u]
        j_all = ((o - ff.CUT_PHASE) // 30).astype(int)
        pick = rng.choice(len(E), n // 2, replace=False)
        for r in pick:
            for lg in (("a", "b") if u == "pair" else ("a",)):
                coin = (E.ticker_a if lg == "a" else E.ticker_b).iloc[r]
                j = int(j_all[r])
                v = ref_vec(coin, j)
                got = G[u].iloc[r]
                for c in G8.BASE:
                    if c == "snap_off_s":
                        exp, g = 60.0 - v[G8.BIX[c]], got[f"{lg}_snapshot_age_s"]
                    else:
                        exp, g = v[G8.BIX[c]], got[f"{lg}_{c}"]
                    ncmp += 1
                    if np.isnan(exp) != np.isnan(g) or (not np.isnan(exp) and abs(exp - g) > 1e-4 * abs(exp) + 1e-3):
                        bad.append((u, lg, r, c, exp, g))
                for tag, k in (("chg1h", 2), ("chg6h", 12)):
                    vk = ref_vec(coin, j - k)
                    for c in G8.CHG:
                        exp = v[G8.BIX[c]] - vk[G8.BIX[c]]
                        g = got[f"{lg}_{tag}_{c}"]
                        ncmp += 1
                        if np.isnan(exp) != np.isnan(g) or (not np.isnan(exp) and abs(exp - g) > 1e-4 * abs(exp) + 1e-3):
                            bad.append((u, lg, r, f"{tag}_{c}", exp, g))
    # relative depth on a few events: the 336 previous cutoff rows
    E, o = ev["coin"]
    j_all = ((o - ff.CUT_PHASE) // 30).astype(int)
    for r in rng.choice(len(E), n_rel, replace=False):
        coin, j = E.ticker_a.iloc[r], int(j_all[r])
        if j < 400:
            continue
        prev = np.array([ref_vec(coin, jj) for jj in range(j - 336, j)])
        for c in G8.REL:
            x = prev[:, G8.BIX[c]]
            fin = np.isfinite(x)
            med = np.median(x[fin]) if fin.sum() >= 144 else np.nan
            cur = ref_vec(coin, j)[G8.BIX[c]]
            exp = cur / med if np.isfinite(med) and med > 0 and np.isfinite(cur) else np.nan
            g = G["coin"].iloc[r][f"a_rel_{c}"]
            ncmp += 1
            if np.isnan(exp) != np.isnan(g) or (not np.isnan(exp) and abs(exp - g) > 1e-3 * abs(exp) + 1e-4):
                bad.append(("coin", "a", r, f"rel_{c}", exp, g))
    print(f"[G8 INDEP] {ncmp:,} comparisons ({n} events, rel_* on {n_rel}); mismatches {len(bad)} [{time.time() - t0:.0f}s]")
    for b in bad[:15]:
        print("  MISMATCH", b)
    assert not bad
    print("[G8 INDEP] PASS")


def poison_raw(R, j, rg):
    """Overwrite EVERY minute row (not only cutoff rows) of the raw coin table whose exchange time is at or after t0_j. t0_j = minute EM0 + o_j; a row labelled m has exchange time >= m * 60 s."""
    t0m = G8.EM0 + ff.CUT_PHASE + 30 * j
    R2 = R.copy()
    late = R2["minute"].to_numpy() >= t0m
    for c in G8.BASE:
        R2.loc[late, c] = rg.uniform(1, 1e6, int(late.sum())).astype(np.float32)
    return R2


N_POISON_COINS, N_POISON_CUTS = 12, 3             # the size the accepted run used: 36 (coin, cutoff) trials (user 2026-10-26 accepted it in place of the 1,000-event rerun)


def test_poison_asof(coins):
    """Raw-level poison on 12 coins x 3 cutoffs (36 trials), plus the broken variant (gather at t0 instead of t0 - 1), which must be CAUGHT."""
    files = sorted(glob.glob(os.path.join(R8.L2DIR, "*_l2.parquet")))
    pick = list(rng.choice(coins, N_POISON_COINS, replace=False))
    raw = {c: [] for c in pick}
    for f in files:
        D = pd.read_parquet(f)
        for c in pick:
            raw[c].append(D[D.coin == c])
    raw = {c: pd.concat(v, ignore_index=True) for c, v in raw.items()}
    bad_ok, caught, trials, nodel = 0, 0, 0, 0
    misses = []
    for c in pick:
        R = raw[c]
        for j in rng.integers(400, ff.NJ - 5, N_POISON_CUTS):
            trials += 1
            for lag, is_rule in ((1, True), (0, False)):
                T = G8.dense_table([G8.cutoff_rows(R, lag)], c)
                F = G8.feature_matrix(T)
                T2 = G8.dense_table([G8.cutoff_rows(poison_raw(R, j, rng), lag)], c)
                F2 = G8.feature_matrix(T2)
                same = np.array_equal(F[:j + 1], F2[:j + 1], equal_nan=True)
                if is_rule and not same:
                    bad_ok += 1
                if not is_rule and not same:
                    caught += 1
                if not is_rule and same:                                 # a miss of the broken variant: say why
                    t0m = G8.EM0 + ff.CUT_PHASE + 30 * int(j)
                    has_t0 = bool((R["minute"].to_numpy() == t0m).any())
                    has_t1 = bool((R["minute"].to_numpy() == t0m - 1).any())
                    misses.append((c, int(j), has_t0, has_t1))
            # deleted o-1 row -> NaN, nothing carried
            T = G8.dense_table([G8.cutoff_rows(R)], c)
            if np.isfinite(T[j, G8.BIX["spread_bp"]]):
                T3 = T.copy()
                T3[j] = np.nan
                F3 = G8.feature_matrix(T3)
                nodel += int(not np.isnan(F3[j, G8.NAMES.index("spread_bp")]))
    print(f"[G8 POISON] {trials} (coin, cutoff) trials, every minute row with exchange time >= t0 overwritten in the RAW table: features at or before the cutoff changed in {bad_ok} cases for the rule (must be 0)")
    print(f"[G8 POISON] broken variant (row labelled t0 read instead of t0 - 1): the same poison changed the features in {caught} of {trials} trials (must be > 0: the test can see the bug)")
    for c, j, h0, h1 in misses:
        print(f"[G8 POISON] broken-variant miss: coin {c}, cutoff {j}: the raw table has a row labelled t0: {h0}; a row labelled t0 - 1: {h1}" + ("  -> the t0 row does not exist, so reading it gives NaN with or without the poison" if not h0 else "  -> NOT explained by a missing t0 row: a finding"))
    print(f"[G8 AS-OF] deleted t0 - 1 row: value carried from an older minute in {nodel} cases (must be 0)")
    assert bad_ok == 0 and caught > 0 and nodel == 0
    print("[G8 POISON/AS-OF] PASS")


def main():
    t0 = time.time()
    ev = R5.event_tables()
    G = {u: pd.read_parquet(os.path.join(R5.WORK, u, "g8.parquet")) for u in ("pair", "coin")}
    if "--poison-only" in sys.argv:
        coins = np.array(sorted(set(ev["pair"][0].ticker_a) | set(ev["coin"][0].ticker_a)))
        test_poison_asof(coins)
        print(f"[TESTS G8 poison-only] PASS [{time.time() - t0:.0f}s]")
        return
    test_invariants(G)
    test_indep(G, ev, 3000, 300)
    coins = np.array(sorted(set(ev["pair"][0].ticker_a) | set(ev["coin"][0].ticker_a)))
    test_poison_asof(coins)
    print(f"[TESTS G8] ALL PASS [{time.time() - t0:.0f}s]")


if __name__ == "__main__":
    main()
