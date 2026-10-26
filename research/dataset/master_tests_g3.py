"""HL-MASTER1 integrity tests for G3 (history), both units.

    python -u research/dataset/master_tests_g3.py > research/dataset/logs/master_tests_g3.log

  1. POISON (look-ahead through labels). For random events i: overwrite reach_10h, minutes_to_mu and label_gap with random values for EVERY event j that is not resolved at
     t0_i (T_i - T_j < 600 minutes, which includes i itself and all later events), rebuild the history and require G3 for i unchanged to the last digit.
  2. KNOWN ANSWERS on a hand-made series, including the boundary T_i - T_j = 600 exactly (resolved) and 599 (not).
  3. INDEPENDENT recomputation of 2,000 pair-unit events and 2,000 coin-unit events with plain boolean masks over the raw arrays (no prefix sums, no searchsorted).
"""
import os, sys, time
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import master_g3 as G3

rng = np.random.default_rng(20261026)


def unit_arrays(unit):
    E, LB = G3.load(unit)
    G = pd.read_parquet(os.path.join(G3.WORK, unit, "g3.parquet"))
    return E, LB, G, G3.minutes(E.entry_time), E.pair_index.to_numpy()


def query_one(series, T, reach, mtm, gap, i):
    H = G3.Hist(series, T, reach, mtm, gap)
    return H.query(series[i:i + 1], T[i:i + 1], own=True)


def test_poison(unit, n):
    E, LB, G, T, series = unit_arrays(unit)
    reach, mtm, gap = LB.reach_10h.to_numpy(float), LB.minutes_to_mu.to_numpy(float), LB.label_gap.to_numpy()
    bad = 0
    t0 = time.time()
    for i in rng.choice(len(E), n, replace=False):
        unres = (T[i] - T) < 600                       # includes i and every later event
        r2, m2, g2 = reach.copy(), mtm.copy(), gap.copy()
        r2[unres] = rng.integers(0, 2, unres.sum()); m2[unres] = rng.uniform(1, 600, unres.sum()); g2[unres] = rng.integers(0, 2, unres.sum())
        q = query_one(series, T, r2, m2, g2, i)
        for c in G3.KEEP:
            a, b = float(np.float32(q[c][0])), float(G[c].iloc[i])
            if not (np.isnan(a) and np.isnan(b)) and a != b:
                bad += 1
                print(f"  POISON CHANGED {c} event {int(E.event_id.iloc[i])}: {b} -> {a}")
    print(f"[POISON {unit}] {n} events, all unresolved labels randomised: columns changed in {bad} cases [{time.time() - t0:.0f}s]")
    assert bad == 0
    print(f"[POISON {unit}] PASS")


def test_known():
    # one series, events at minutes 0, 600, 1199, 1200, 2400; reach 1, 0, 1, 1, 0; mu minutes 50, nan, 100, 200, nan; none gapped
    T = np.array([0, 600, 1199, 1200, 2400], dtype=np.int64)
    reach = np.array([1, 0, 1, 1, 0], float)
    mtm = np.array([50, np.nan, 100, 200, np.nan])
    H = G3.Hist(np.zeros(5, np.int64), T, reach, mtm, np.zeros(5, int))
    q = H.query(np.zeros(5, np.int64), T, own=True)
    # event at T=600: previous {0}, resolved at once because 600 - 0 = 600 (boundary)
    assert q["n_prev_triggers"][1] == 1 and q["n_prev_resolved"][1] == 1 and q["prev_reach_raw"][1] == 1.0 and q["last1_reach"][1] == 1.0
    # event at 1199: previous {0, 600}; 1199 - 600 = 599 -> only {0} resolved
    assert q["n_prev_triggers"][2] == 2 and q["n_prev_resolved"][2] == 1 and q["prev_reach_raw"][2] == 1.0
    # event at 1200: previous {0, 600, 1199}; 1200 - 600 = 600 -> {0, 600} resolved, reach mean 0.5, last1 = 0 (the 600 event), last2 = 1
    assert q["n_prev_resolved"][3] == 2 and q["prev_reach_raw"][3] == 0.5 and q["last1_reach"][3] == 0.0 and q["last2_reach"][3] == 1.0 and np.isnan(q["last3_reach"][3])
    assert q["days_since_last_trigger"][3] == (1200 - 1199) / 1440.0 and q["triggers_last_7d"][3] == 3
    # event at 2400: all of 0, 600, 1199, 1200 resolved (2400 - 1200 = 1200): reach 1,0,1,1 -> raw 0.75; last5: 1,1,0,1,nan; mean minutes to mu of reachers (50, 100, 200)
    assert q["n_prev_resolved"][4] == 4 and abs(q["prev_reach_raw"][4] - 0.75) < 1e-12
    assert [q[f"last{m}_reach"][4] for m in (1, 2, 3, 4)] == [1.0, 1.0, 0.0, 1.0] and np.isnan(q["last5_reach"][4])
    assert abs(q["prev_mean_minutes_to_mu"][4] - (50 + 100 + 200) / 3) < 1e-12
    # as-of global rate at 2400: events with T + 600 <= 2400 are T = 0, 600, 1199, 1200 -> 0.75; shrunk = (3 + 20 * 0.75) / (4 + 20)
    assert abs(q["global_reach_asof"][4] - 0.75) < 1e-12 and abs(q["prev_reach_shrunk"][4] - (3 + 15) / 24) < 1e-12
    # a gapped event is neither a reacher nor a resolved one
    H2 = G3.Hist(np.zeros(5, np.int64), T, reach, mtm, np.array([0, 0, 0, 1, 0]))
    q2 = H2.query(np.zeros(5, np.int64), T, own=True)
    assert q2["n_prev_resolved"][4] == 3 and q2["n_prev_triggers"][4] == 4
    print("[KNOWN] boundary (600 resolved, 599 not), recency order, shrinkage, as-of global rate, gap exclusion, mean minutes to mu: PASS")


def indep(unit, n):
    E, LB, G, T, series = unit_arrays(unit)
    reach, mtm, gap = LB.reach_10h.to_numpy(float), LB.minutes_to_mu.to_numpy(float), LB.label_gap.to_numpy()
    valid = (gap == 0) & np.isfinite(reach)
    bad, ncmp, t0 = [], 0, time.time()
    for i in np.sort(rng.choice(len(E), n, replace=False)):
        same = series == series[i]
        earlier = same & (T < T[i])
        res = earlier & ((T[i] - T) >= 600) & valid
        exp = {"n_prev_triggers": earlier.sum(), "n_prev_resolved": res.sum()}
        exp["prev_reach_raw"] = reach[res].mean() if res.any() else np.nan
        allres = valid & ((T[i] - T) >= 600)
        g = reach[allres].mean() if allres.any() else np.nan
        exp["global_reach_asof"] = g
        exp["prev_reach_shrunk"] = (reach[res].sum() + 20 * g) / (res.sum() + 20)
        rr = np.flatnonzero(res)
        rr = rr[np.argsort(T[rr])][::-1]
        for m in range(1, 6):
            exp[f"last{m}_reach"] = reach[rr[m - 1]] if len(rr) >= m else np.nan
        l5 = [reach[k] for k in rr[:5]]
        exp["last5_mean"] = np.mean(l5) if l5 else np.nan
        ee = np.flatnonzero(earlier)
        exp["days_since_last_trigger"] = (T[i] - T[ee].max()) / 1440.0 if len(ee) else np.nan
        exp["triggers_last_7d"] = (earlier & (T >= T[i] - 7 * 1440)).sum()
        rch = res & (reach > 0)
        exp["prev_mean_minutes_to_mu"] = mtm[rch].mean() if rch.any() else np.nan
        for c, v in exp.items():
            g_ = float(G[c].iloc[i])
            ncmp += 1
            if np.isnan(v) != np.isnan(g_):
                bad.append((int(E.event_id.iloc[i]), c, v, g_)); continue
            if not np.isnan(v) and abs(v - g_) > 1e-6 + 1e-4 * abs(v):
                bad.append((int(E.event_id.iloc[i]), c, v, g_))
    print(f"[G3 INDEP {unit}] {n} events x {len(exp)} columns = {ncmp:,} comparisons; mismatches {len(bad)} [{time.time() - t0:.0f}s]")
    for b in bad[:10]:
        print("  MISMATCH", b)
    assert not bad
    print(f"[G3 INDEP {unit}] PASS")


def main():
    test_known()
    test_poison("coin", 1000)
    test_poison("pair", 1000)
    indep("coin", 2000)
    indep("pair", 2000)
    print("[TESTS G3] ALL PASS")


if __name__ == "__main__":
    main()
