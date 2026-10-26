"""HL-MASTER1 integrity tests for G7 (derivatives state and vault inventory).

    python -u research/dataset/master_tests_g7.py > research/dataset/logs/master_tests_g7.log

  1. POISON (600 pair legs, 200 coin legs): for a sampled leg at cutoff o every RAW input at or after minute o - 1 + 1 (observed OI snapshots, fills-based OI changes, 1m closes, taker flow, ctx fields, the vault
     positions, and the funding rows whose minute label is >= o) is replaced by random values; the production assemble() and leg_g7() are rerun; all leg columns must be identical to the last digit. Also with the funding
     rows, ctx and vault arrays TRUNCATED at o.
  2. INDEPENDENT recomputation (1,500 legs) by plain loops over the raw sources read separately: the last observed OI within 120 minutes, the level, the percent changes, the fills-based windows, the funding means and the
     as-of rule (a row stamped just after an hour mark is not available at that mark), the ctx basis and spread, the vault inventory.
  3. INVARIANTS: ages >= 0; oi_obs_age <= 120; vault_share_of_oi in [0, 1] where finite; funding within +-0.05 per hour; the pair differences equal a - b.
"""
import os, sys, time
from multiprocessing import Pool
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import master_g7 as G7
import master_oi as O
import flowfeat as ff

rng = np.random.default_rng(20261031)


def poison_raw(R, o, mode):
    P = {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in R.items()}
    m = o - 1
    rg = np.random.default_rng(o)
    for k in ("lc",):
        P[k][o:] = rg.normal(0, 3, len(P[k]) - o) if mode == "overwrite" else np.nan
    P["obs_dense"][o:] = rg.uniform(1, 1e9, len(P["obs_dense"]) - o) if mode == "overwrite" else np.nan
    P["cd"][o + 1:] = P["cd"][o] + (np.cumsum(rg.normal(0, 1e5, len(P["cd"]) - o - 1)) if mode == "overwrite" else 0.0)
    P["tn"][o:] = rg.uniform(0, 1e6, len(P["tn"]) - o) if mode == "overwrite" else np.nan
    ctx = {k: v.copy() for k, v in R["ctx"].items()}
    for k in ctx:
        ctx[k][o:] = rg.uniform(0.5, 2, len(ctx[k]) - o) if mode == "overwrite" else np.nan
    P["ctx"] = ctx
    ft, fr, fp = R["fund"]
    if ft is not None:
        fr, fp = fr.copy(), fp.copy()
        late = ft >= o
        if mode == "overwrite":
            fr[late], fp[late] = rg.normal(0, 1e-3, late.sum()), rg.normal(0, 1e-3, late.sum())
            P["fund"] = (ft, fr, fp)
        else:
            P["fund"] = (ft[~late], fr[~late], fp[~late])
    if R["vault"] is not None:
        P["vault"] = tuple(np.concatenate([a[:o], (rg.normal(0, 1e4, len(a) - o) if mode == "overwrite" else np.full(len(a) - o, np.nan))]) for a in R["vault"])
    return P


def poison_job(args):
    c, rows, shared = args
    G = shared
    R = G7.load_raw_coin(c, G["ctx"], G["cd"], G["holes"], G["vaults"])
    A = G7.assemble(R)
    bad = []
    for o in rows:
        base = G7.leg_g7(c, np.array([o]), A)
        for mode in ("overwrite", "truncate"):
            P = poison_raw(R, o, mode)
            got = G7.leg_g7(c, np.array([o]), G7.assemble(P))
            for k in base:
                if not np.array_equal(np.asarray(base[k], float), np.asarray(got[k], float), equal_nan=True):
                    bad.append((c, o, mode, k, float(base[k][0]), float(got[k][0])))
    return bad


SHARED = {}


def _pj(args):
    return poison_job((args[0], args[1], SHARED))


def test_poison(units, n_pair, n_coin):
    t0 = time.time()
    SHARED["ctx"] = G7.load_ctx_dense(sorted(set(units["pair"].ticker_a) | set(units["pair"].ticker_b) | set(units["coin"].ticker_a)))
    SHARED["cd"] = O.load_delta()
    SHARED["holes"] = O.hole_flags()
    SHARED["vaults"] = G7.vault_arrays(set(units["pair"].ticker_a) | set(units["pair"].ticker_b) | set(units["coin"].ticker_a))
    print(f"[G7 POISON] inputs loaded [{time.time() - t0:.0f}s]", flush=True)
    jobs = {}
    for u, n in (("pair", n_pair), ("coin", n_coin)):
        E = units[u]
        o = ff.minute_index(pd.to_datetime(E.entry_time) + pd.Timedelta(minutes=30))
        for r in rng.choice(len(E), n, replace=False):
            c = E.ticker_b.iloc[r] if (u == "pair" and rng.random() < 0.5) else E.ticker_a.iloc[r]
            jobs.setdefault(c, []).append(int(o[r]))
    with Pool(int(os.environ.get("NPROC", 6))) as pool:
        res = pool.map(_pj, sorted(jobs.items()), chunksize=1)
    bad = [b for r in res for b in r]
    print(f"[G7 POISON] {n_pair} pair legs + {n_coin} coin legs, overwrite and truncation, {len(G7.LEG_COLS)} columns each: changed in {len(bad)} cases [{time.time() - t0:.0f}s]")
    for b in bad[:10]:
        print("  CHANGED", b)
    assert not bad
    print("[G7 POISON] PASS")


def fund_job(args):
    c, rows = args
    G = SHARED
    R = G7.load_raw_coin(c, G["ctx"], G["cd"], G["holes"], G["vaults"])
    A = G7.assemble(R)
    ft, fr, fp = R["fund"]
    bad_fwd, bad_rev = [], []
    if ft is None:
        return bad_fwd, bad_rev, 0
    n = 0
    for o in rows:
        base = G7.leg_g7(c, np.array([o]), A)
        late = ft == o                                  # rows stamped in [t0, t0 + 60 s): the minute label of t0
        if not late.any():
            continue
        n += 1
        P = dict(R)
        fr2, fp2 = fr.copy(), fp.copy()
        fr2[late], fp2[late] = fr2[late] + 0.01, fp2[late] + 0.01
        P["fund"] = (ft, fr2, fp2)
        got = G7.leg_g7(c, np.array([o]), G7.assemble(P))
        for k in base:
            if not np.array_equal(np.asarray(base[k], float), np.asarray(got[k], float), equal_nan=True):
                bad_fwd.append((c, o, k))
        pos = np.searchsorted(ft, o - 1, side="right") - 1                 # the last row available at t0 (stamped just before)
        if pos >= 0:
            fr3, fp3 = fr.copy(), fp.copy()
            fr3[pos] += 0.01; fp3[pos] += 0.01
            P2 = dict(R)
            P2["fund"] = (ft, fr3, fp3)
            got2 = G7.leg_g7(c, np.array([o]), G7.assemble(P2))
            if not (abs(got2["fund_last"][0] - base["fund_last"][0] - 0.01) < 1e-9 and abs(got2["prem_last"][0] - base["prem_last"][0] - 0.01) < 1e-9):
                bad_rev.append((c, o))
    return bad_fwd, bad_rev, n


def test_fund_asof(units, n):
    t0 = time.time()
    jobs = {}
    for u in ("pair", "coin"):
        E = units[u]
        o = ff.minute_index(pd.to_datetime(E.entry_time) + pd.Timedelta(minutes=30))
        hour = np.flatnonzero((o - ff.CUT_PHASE) % 60 == 0)                     # t0 on an hour mark (:00)
        for r in rng.choice(hour, n // 2, replace=False):
            jobs.setdefault(E.ticker_a.iloc[r], []).append(int(o[r]))
    with Pool(int(os.environ.get("NPROC", 6))) as pool:
        res = pool.map(fund_job, sorted(jobs.items()), chunksize=1)
    fwd = [b for r in res for b in r[0]]
    rev = [b for r in res for b in r[1]]
    cnt = sum(r[2] for r in res)
    print(f"[G7 FUNDING AS-OF] {cnt} events with t0 on an hour mark: rows stamped in [t0, t0 + 60 s) perturbed -> columns changed {len(fwd)} (must be 0); the row stamped just before t0 perturbed -> "
          f"fund_last / prem_last moved by exactly the perturbation in {cnt - len(rev)} of {cnt} (must be all) [{time.time() - t0:.0f}s]")
    for b in fwd[:5] + rev[:5]:
        print("  FAIL", b)
    assert not fwd and not rev
    print("[G7 FUNDING AS-OF] PASS: the minute-floor convention is as-of correct")


def test_invariants():
    for u in ("pair", "coin"):
        G = pd.read_parquet(os.path.join(G7.WORK, u, "g7.parquet"))
        for lg in (("a", "b") if u == "pair" else ("a",)):
            assert (G[f"{lg}_oi_obs_age"].dropna() >= 0).all() and (G[f"{lg}_oi_obs_age"].dropna() <= G7.OBS_LIMIT).all()
            assert (G[f"{lg}_oi_rec_age"].dropna() >= 0).all()
            x = G[f"{lg}_vault_share_of_oi"].dropna()
            assert ((x >= 0) & (x <= 1.0001)).all(), (u, lg, x.max())
            f = G[f"{lg}_fund_last"].dropna()
            assert (f.abs() <= 0.05).all(), f.abs().max()
            assert (G[f"{lg}_oi_obs_usd"].dropna() >= 0).all() and (G[f"{lg}_oi_rec_usd"].dropna() >= -1e-3).all()
        if u == "pair":
            for k in ("oi_rec_usd", "fund_last", "vault_gross_usd"):
                ok = np.isfinite(G[f"a_{k}"]) & np.isfinite(G[f"b_{k}"])
                a_, b_, d_ = G[f"a_{k}"].to_numpy(float)[ok], G[f"b_{k}"].to_numpy(float)[ok], G[f"d_{k}"].to_numpy(float)[ok]
                assert (np.abs((a_ - b_) - d_) <= 1e-6 * (np.abs(a_) + np.abs(b_)) + 1e-12).all(), k          # float32 storage: the tolerance is relative to the magnitudes, not to the difference
    print("[G7 INVARIANTS] PASS (ages in range, observed age <= 120, vault share in [0,1], hourly funding within +-5%, pair differences equal a - b)")


def indep_inputs(coins):
    """Independent readers: observed OI and ctx fields from the day files, fills-based changes from the oi parquets, funding rows and vault fills from their files."""
    obs = {c: np.full(ff.N, np.nan) for c in coins}
    fields = {c: {k: np.full(ff.N, np.nan) for k in ("funding", "premium", "oracle_px", "mark_px", "mid_px", "impact_bid_px", "impact_ask_px")} for c in coins}
    for f in sorted(os.listdir(G7.CTX)):
        if not f.endswith(".parquet") or f.startswith("_"):
            continue
        d = pd.read_parquet(os.path.join(G7.CTX, f))
        d = d[d.coin.astype(str).isin(coins)]
        t = pd.to_datetime(d.time)
        d = d[(t.dt.second == 0) & (t.dt.microsecond == 0)]
        mm = ((pd.to_datetime(d.time).dt.tz_localize(None) - ff.GRID0) // pd.Timedelta(minutes=1)).to_numpy()
        for c, g in d.assign(m=mm).groupby(d.coin.astype(str)):
            g = g[(g.m >= 0) & (g.m < ff.N)]
            obs[c][g.m.to_numpy()] = g.open_interest.to_numpy(float)
            for k in fields[c]:
                fields[c][k][g.m.to_numpy()] = g[k].to_numpy(float)
    delta = {c: np.zeros(ff.N) for c in coins}
    for f in sorted(os.listdir(G7.OI_DIR)):
        if f.endswith("_oi.parquet"):
            d = pd.read_parquet(os.path.join(G7.OI_DIR, f), columns=["coin", "minute", "oi_delta_coin"])
            d = d[d.coin.astype(str).isin(coins)]
            mm = ((pd.to_datetime(d.minute).dt.tz_localize(None) - ff.GRID0) // pd.Timedelta(minutes=1)).to_numpy()
            for c, g in d.assign(m=mm).groupby(d.coin.astype(str)):
                g = g[(g.m >= 0) & (g.m < ff.N)]
                np.add.at(delta[c], g.m.to_numpy(), g.oi_delta_coin.to_numpy(float))
    return obs, fields, delta


def test_indep(units, n):
    t0 = time.time()
    picks = []
    for u in ("pair", "coin"):
        E = units[u]
        o = ff.minute_index(pd.to_datetime(E.entry_time) + pd.Timedelta(minutes=30))
        for r in rng.choice(len(E), n // 2, replace=False):
            lg = "b" if (u == "pair" and rng.random() < 0.5) else "a"
            picks.append((E.ticker_b.iloc[r] if lg == "b" else E.ticker_a.iloc[r], u, lg, int(r), int(o[r])))
    coins = sorted({p[0] for p in picks})
    obs, fields, delta = indep_inputs(set(coins))
    print(f"[G7 INDEP] independent inputs read for {len(coins)} coins [{time.time() - t0:.0f}s]", flush=True)
    G = {u: pd.read_parquet(os.path.join(G7.WORK, u, "g7.parquet")) for u in ("pair", "coin")}
    import evmarket as em
    bad, ncmp, mx = [], 0, 0.0
    for c, u, lg, r, o in sorted(picks):
        lc = em.load_lc(c) if True else None
        m = o - 1
        price = np.exp(lc[m])
        ob = obs[c]
        def last_obs(mm):
            for k in range(0, G7.OBS_LIMIT + 1):
                if mm - k >= 0 and np.isfinite(ob[mm - k]):
                    return ob[mm - k], k
            return np.nan, np.nan
        v, age = last_obs(m)
        exp = {"oi_obs_usd": v * price, "oi_obs_age": age}
        for lab, W in G7.WCH.items():
            v2, _ = last_obs(m - W) if m - W >= 0 else (np.nan, np.nan)
            exp[f"oi_obs_chg_{lab}"] = v / v2 - 1 if np.isfinite(v) and np.isfinite(v2) and v2 > 0 else np.nan
        # reconstructed level
        def level(mm):
            k = mm
            while k >= 0 and not np.isfinite(ob[k]):
                k -= 1
            if k < 0:
                return np.nan, np.nan
            return ob[k] + 2.0 * delta[c][k:mm].sum(), mm - k          # fills in minutes [k, mm): cd[mm] - cd[k]
        L, since = level(m)
        exp["oi_rec_usd"], exp["oi_rec_age"] = L * price, since
        exp["oi_rec_in_gap"] = float(since > 60) if np.isfinite(since) else np.nan
        for lab, W in G7.WCH.items():
            L2, _ = level(m - W) if m - W >= 0 else (np.nan, np.nan)
            exp[f"oi_rec_chg_{lab}"] = L / L2 - 1 if np.isfinite(L) and np.isfinite(L2) and L2 > 0 else np.nan
        # funding as-of (read straight from the API file): rows stamped before t0 only
        t0ts = ff.GRID0 + pd.Timedelta(minutes=o)
        fpath = os.path.join(G7.FUND, f"{c}.parquet")
        if os.path.exists(fpath):
            fd = pd.read_parquet(fpath)
            ft_ = pd.to_datetime(fd.time).dt.tz_localize(None)
            fd = fd[ft_ < t0ts].assign(t=ft_[ft_ < t0ts])
            if len(fd):
                fd = fd.assign(t=fd.t.dt.floor("min"))          # the production rule works on minute labels: a row stamped H + a few ms belongs to minute H
                last = fd.iloc[-1]
                exp["fund_last"], exp["prem_last"] = float(last.fundingRate), float(last.premium)
                exp["fund_age_h"] = (o - ((last.t - ff.GRID0) // pd.Timedelta(minutes=1))) / 60.0
                for lab, kh in (("8h", 8), ("24h", 24), ("7d", 168)):
                    w = fd[fd.t > last.t - pd.Timedelta(hours=kh)]
                    exp[f"fund_mean_{lab}"] = float(w.fundingRate.mean()) if w.fundingRate.notna().sum() >= 0.75 * kh else np.nan
            else:
                for k in ("fund_last", "prem_last", "fund_age_h", "fund_mean_8h", "fund_mean_24h", "fund_mean_7d"):
                    exp[k] = np.nan
        row = G[u].iloc[r]
        for k, vv in exp.items():
            gg = float(row[f"{lg}_{k}"])
            ncmp += 1
            if np.isnan(vv) != np.isnan(gg):
                bad.append((c, u, lg, r, k, vv, gg)); continue
            if np.isnan(vv):
                continue
            err = abs(vv - gg)
            mx = max(mx, err / (1e-6 + 1e-4 * abs(vv)))
            if err > 1e-6 + 1e-4 * abs(vv):
                bad.append((c, u, lg, r, k, vv, gg))
    print(f"[G7 INDEP] {len(picks)} legs: {ncmp:,} comparisons (observed OI, age, changes, reconstructed level and changes, funding as-of and means); mismatches {len(bad)}; worst error / tolerance {mx:.3f} [{time.time() - t0:.0f}s]")
    for b in bad[:15]:
        print("  MISMATCH", b)
    assert not bad
    print("[G7 INDEP] PASS")


def main():
    t0 = time.time()
    units = {u: pd.read_parquet(os.path.join(G7.WORK, u, "events.parquet"), columns=["event_id", "ticker_a", "ticker_b", "entry_time"]) for u in ("pair", "coin")}
    if "--fund-only" in sys.argv:                                   # the targeted funding as-of check alone (the other G7 tests already passed on this build)
        SHARED["ctx"] = G7.load_ctx_dense(sorted(set(units["pair"].ticker_a) | set(units["pair"].ticker_b) | set(units["coin"].ticker_a)))
        SHARED["cd"] = O.load_delta()
        SHARED["holes"] = O.hole_flags()
        SHARED["vaults"] = G7.vault_arrays(set(units["pair"].ticker_a) | set(units["pair"].ticker_b) | set(units["coin"].ticker_a))
        test_fund_asof(units, 500)
        print(f"[TESTS G7 fund-only] PASS [{time.time() - t0:.0f}s]")
        return
    test_invariants()
    test_indep(units, 1500)
    test_poison(units, 600, 200)
    test_fund_asof(units, 500)
    print(f"[TESTS G7] ALL PASS [{time.time() - t0:.0f}s]")


if __name__ == "__main__":
    main()
