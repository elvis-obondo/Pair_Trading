"""HL-MASTER1 integrity tests for G6 (wallets), per leg and net.

    python -u research/dataset/master_tests_g6.py > research/dataset/logs/master_tests_g6.log

  1. POISON (1,000 legs, 3 per day at most): the production run_chunk is rerun for ONE leg with the wallet files monkey-patched: every T1 row whose bin is at or after the leg's t0 and every T2 row of the trigger's day
     and later is replaced by random values (and, in a second variant, removed). All 104 values of the leg must be identical to the last digit.
  2. INDEPENDENT recomputation (1,200 legs, grouped by day): plain pandas on the raw T1 / T2 files, written without master_g6's functions: the window slices, the population split, the skill table (explicit
     30-day groupby), deciles, the persistent sets, every feature of both populations and the two vault shares.
  3. INVARIANTS (on the output): shares in [0,1]; push_total_all >= push_total_human; nw_all >= nw_human; vault_push_share = 1 - push_total_human / push_total_all; hhi in [1/nw, 1]; net weights respected.
"""
import os, sys, time
from multiprocessing import Pool
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import master_g6 as G6
import master_g6_run as R6

rng = np.random.default_rng(20261101)


def one_leg(args):
    row, mode = args
    D = pd.Timestamp(row["day"])
    t0ms = int(row["t0_ms"])
    rg = np.random.default_rng(t0ms % (2 ** 32))
    orig1, orig2 = G6.load_t1, G6.load_t2

    def l1(wdir, day):
        x = orig1(wdir, day)
        if x is None:
            return None
        if mode == "base":
            return x
        b = G6.ms_of(x.bin)
        late = b >= t0ms
        if mode == "overwrite":
            x = x.copy()
            for c in ("taker_buy_usd", "taker_sell_usd", "twap_usd", "absorbed_buy_usd", "absorbed_sell_usd"):
                x.loc[late, c] = rg.uniform(0, 1e6, int(late.sum()))
            return x
        return x[~late]

    def l2(wdir, day):
        x = orig2(wdir, day)
        if x is None or day < D or mode == "base":
            return x
        if mode == "overwrite":
            x = x.copy()
            x["volume_usd"] = rg.uniform(1, 1e6, len(x)); x["closed_pnl_usd"] = rg.normal(0, 1e4, len(x))
            return x
        # "removed": the VALUES of every T2 day >= D are zeroed. The wallet column stays: run_chunk builds its wallet-id map from the T2 files of the chunk, and an id is an index, not information
        # (skill reads only days < D); deleting the rows would make the map miss wallets that T1 still holds and trip the build's own `wid >= 0` guard.
        return x.assign(volume_usd=0.0, closed_pnl_usd=0.0, n_forced_events=0.0, n_fills=0.0)
    G6.load_t1, G6.load_t2 = l1, l2
    try:
        mm = pd.read_parquet(R6.MISSING)
        holes = np.unique((G6.ms_of(mm["minute"] if "minute" in mm else mm.iloc[:, 0]) // G6.BIN_MS) * G6.BIN_MS)
        rows = pd.DataFrame([row]).reset_index(drop=True)
        return G6.run_chunk(rows, R6.WDIR, holes, D, D + pd.Timedelta(days=1))[0]
    finally:
        G6.load_t1, G6.load_t2 = orig1, orig2


def test_poison(rows, n):
    t0 = time.time()
    pick = rows.sample(n * 3, random_state=3).groupby("day").head(3).head(n)
    recs = [r for _, r in pick.iterrows()]
    with Pool(int(os.environ.get("NPROC", 7))) as pool:
        base = pool.map(one_leg, [(r, "base") for r in recs], chunksize=1)
        over = pool.map(one_leg, [(r, "overwrite") for r in recs], chunksize=1)
        trunc = pool.map(one_leg, [(r, "truncate") for r in recs], chunksize=1)
    bad = sum(int(not np.array_equal(b, o, equal_nan=True)) + int(not np.array_equal(b, t, equal_nan=True)) for b, o, t in zip(base, over, trunc))
    print(f"[G6 POISON] {len(recs)} legs, T1 rows at or after t0 and T2 days >= D overwritten / removed, {G6.NF * len(G6.WINS)} values each: legs changed {bad} (the T2 days >= D are zeroed, not deleted: skill reads days < D only, so passing also shows the zeroed days are never counted as active) [{time.time() - t0:.0f}s]")
    assert bad == 0
    print("[G6 POISON] PASS")


def ref_day(args):
    D, legs = args
    D = pd.Timestamp(D)
    ss = {}
    frames = []
    for k in range(1, 31):
        x = G6.load_t2(R6.WDIR, D - pd.Timedelta(days=k))
        if x is not None:
            frames.append(x.assign(d=k))
    A = pd.concat(frames)
    g = A.groupby("wallet")
    vol, pnl, nf, act = g.volume_usd.sum(), g.closed_pnl_usd.sum(), g.n_fills.sum(), g.size()
    forced = A.groupby("wallet").n_forced_events.sum()
    skill = (pnl / vol) * nf / (nf + G6.K_SHRINK)
    skill = skill[(act >= G6.MIN_ACTIVE) & (vol > 0)]
    prev = G6.load_t2(R6.WDIR, D - pd.Timedelta(days=1))
    sp = skill[skill.index.isin(prev.wallet)] if prev is not None else skill.iloc[:0]
    cuts = (np.percentile(sp, 10), np.percentile(sp, 90)) if len(sp) >= 100 else None
    T1 = pd.concat([x for x in (G6.load_t1(R6.WDIR, D - pd.Timedelta(days=1)), G6.load_t1(R6.WDIR, D)) if x is not None])
    T1 = T1.assign(ms=G6.ms_of(T1.bin), coin=T1.coin.astype(str))
    pf = []
    for k in range(1, 8):
        x = G6.load_t1(R6.WDIR, D - pd.Timedelta(days=k))
        if x is not None:
            pf.append(x.assign(n=x.taker_buy_usd + x.taker_sell_usd))
    mm = pd.read_parquet(R6.MISSING)
    holes = np.unique((G6.ms_of(mm["minute"] if "minute" in mm else mm.iloc[:, 0]) // G6.BIN_MS) * G6.BIN_MS)
    vaults = set(G6.VAULTS)
    out = []
    for idx, c, s, o_ms in legs:
        P7 = pd.concat(pf) if len(pf) >= G6.MIN_PERS_DAYS else None
        res = np.full((len(G6.WINS), G6.NF), np.nan)
        for wi, W in enumerate(G6.WINS):
            lo, hi = o_ms - W * 60_000, o_ms
            if lo < G6.DATA_START_MS or ((holes >= lo) & (holes < hi)).any():
                continue
            w = T1[(T1.coin == c) & (T1.ms >= lo) & (T1.ms < hi)]
            w = w.assign(push=w.taker_buy_usd if s > 0 else w.taker_sell_usd, both=w.taker_buy_usd + w.taker_sell_usd, opp=w.absorbed_sell_usd if s > 0 else w.absorbed_buy_usd)
            tot_all = w.push.sum()
            for pi, (pname, sub) in enumerate((("all", w), ("human", w[~w.wallet.isin(vaults)]))):
                base = pi * 11
                pt = sub.push.sum()
                res[wi, 22 + pi] = pt                      # push_total_all, push_total_human sit at 22, 23
                if pt <= 0:
                    res[wi, base + 3] = 0.0
                    continue
                sw = sub.groupby("wallet").push.sum()
                sw = sw[sw > 0]
                sh = (sw / pt).sort_values(ascending=False)
                res[wi, base], res[wi, base + 1], res[wi, base + 2], res[wi, base + 3] = sh.iloc[0], sh.iloc[:3].sum(), (sh ** 2).sum(), len(sh)
                if P7 is not None:
                    q = P7[P7.coin.astype(str) == c]
                    if pname == "human":
                        q = q[~q.wallet.isin(vaults)]
                    top = set(q.groupby("wallet").n.sum().sort_values(ascending=False, kind="stable").index[:10]) if len(q) else set()
                    res[wi, base + 4] = sw[sw.index.isin(top)].sum() / pt
                tw = sub.twap_usd
                if not tw.isna().any() and sub.both.sum() > 0:
                    res[wi, base + 5] = tw.sum() / sub.both.sum()
                sk = skill.reindex(sw.index)
                okk = sk.notna()
                if okk.any():
                    res[wi, base + 6] = (sk[okk] * sw[okk]).sum() / sw[okk].sum()
                res[wi, base + 7] = sw[okk].sum() / pt
                if cuts is not None:
                    res[wi, base + 8] = sw[okk & (sk <= cuts[0])].sum() / pt
                    res[wi, base + 9] = sw[okk & (sk >= cuts[1])].sum() / pt
                fz = forced.reindex(sw.index).fillna(0)
                res[wi, base + 10] = sw[fz > 0].sum() / pt
            if tot_all > 0:
                vm = w.wallet.isin(vaults)
                res[wi, 24] = w.push[vm].sum() / tot_all
                vab = w.opp[vm].sum()
                res[wi, 25] = vab / tot_all                # vault_absorb_ratio
                res[wi, 26] = vab / (vab + tot_all)        # vault_absorb_share
        out.append((idx, res))
    return out


def test_indep(rows, n):
    t0 = time.time()
    pick = rows.sample(n * 2, random_state=5).groupby("day").head(6).head(n)
    byday = {d: [(i, r.coin, float(r.s), int(r.t0_ms)) for i, r in g.iterrows()] for d, g in pick.groupby("day")}
    with Pool(int(os.environ.get("NPROC", 7))) as pool:
        res = pool.map(ref_day, list(byday.items()), chunksize=1)
    # production values for the same legs (from the written parquet files)
    a = {u: pd.read_parquet(os.path.join(R6.WORK, "pair" if u == 0 else "coin", "g6_a.parquet")) for u in (0, 1)}
    b = pd.read_parquet(os.path.join(R6.WORK, "pair", "g6_b.parquet"))
    bad, ncmp, mx = [], 0, 0.0
    for lst in res:
        for idx, ref in lst:
            r = rows.loc[idx]
            tbl = (a[int(r.unit)] if int(r.leg) == 0 else b)
            prefix = "a" if int(r.leg) == 0 else "b"
            row = tbl.iloc[int(r.ev)]
            for wi, W in enumerate(G6.WINS):
                for j, nm in enumerate(G6.NAMES):
                    v, g = ref[wi, j], float(row[f"{prefix}_{nm}_{W}"])
                    ncmp += 1
                    if np.isnan(v) != np.isnan(g):
                        bad.append((idx, W, nm, v, g)); continue
                    if np.isnan(v):
                        continue
                    err = abs(v - g)
                    mx = max(mx, err / (1e-6 + 1e-4 * abs(v)))
                    if err > 1e-6 + 1e-4 * abs(v):
                        bad.append((idx, W, nm, v, g))
    print(f"[G6 INDEP] {sum(len(l) for l in res)} legs: {ncmp:,} comparisons; mismatches {len(bad)}; worst error / tolerance {mx:.3f} [{time.time() - t0:.0f}s]")
    for x in bad[:15]:
        print("  MISMATCH", x)
    assert not bad
    print("[G6 INDEP] PASS")


def test_invariants():
    for u in ("pair", "coin"):
        for lg in (("a", "b", "net") if u == "pair" else ("a",)):
            G = pd.read_parquet(os.path.join(R6.WORK, u, f"g6_{lg}.parquet"))
            for W in G6.WINS:
                for f in ("top1", "top3", "hhi", "pers", "twap", "skill_cov", "bot", "topd", "prior_forced"):
                    for p in ("all", "human"):
                        x = G[f"{lg}_{f}_{p}_{W}"].dropna()
                        assert ((x >= -1e-5) & (x <= 1 + 1e-5)).all(), (u, lg, f, p, W, float(x.min()), float(x.max()))
                for f in ("vault_push_share", "vault_absorb_share"):
                    x = G[f"{lg}_{f}_{W}"].dropna()
                    assert ((x >= -1e-5) & (x <= 1 + 1e-5)).all(), (u, lg, f, W)
                x = G[f"{lg}_vault_absorb_ratio_{W}"].dropna()
                assert (x >= -1e-5).all(), (u, lg, "vault_absorb_ratio", W)
                if lg != "net":
                    ra, sa = G[f"{lg}_vault_absorb_ratio_{W}"], G[f"{lg}_vault_absorb_share_{W}"]
                    ok = ra.notna() & sa.notna()
                    assert (np.abs(sa[ok] - ra[ok] / (1 + ra[ok])) < 1e-4).all(), (u, lg, W, "vault_absorb_share != ratio / (1 + ratio)")
                    pa, ph = G[f"{lg}_push_total_all_{W}"], G[f"{lg}_push_total_human_{W}"]
                    ok = pa.notna() & ph.notna()
                    assert (pa[ok] + 1e-3 >= ph[ok]).all(), (u, lg, W, "push_total_all < push_total_human")
                    nwa, nwh = G[f"{lg}_nw_all_{W}"], G[f"{lg}_nw_human_{W}"]
                    ok = nwa.notna() & nwh.notna()
                    assert (nwa[ok] >= nwh[ok]).all(), (u, lg, W, "nw_all < nw_human")
                    vps = G[f"{lg}_vault_push_share_{W}"]
                    ok = pa.notna() & ph.notna() & vps.notna() & (pa > 0)
                    assert (np.abs(vps[ok] - (1 - ph[ok] / pa[ok])) < 1e-4).all(), (u, lg, W, "vault_push_share != 1 - human/all")
    print("[G6 INVARIANTS] PASS (shares in [0,1], push_total_all >= push_total_human, nw_all >= nw_human, vault_push_share = 1 - push_total_human / push_total_all)")


def main():
    t0 = time.time()
    rows = pd.read_parquet(R6.ROWS)
    if "--indep-only" in sys.argv:                 # integrity item 2: 2,000 legs (the first run used 1,200)
        test_indep(rows, 2000)
        print(f"[TESTS G6 indep-only] PASS [{time.time() - t0:.0f}s]")
        return
    if "--poison-only" in sys.argv:                # invariants and independent recomputation already passed on this build (master_tests_g6.log of chain 12)
        test_poison(rows, 400)
        print(f"[TESTS G6 poison-only] PASS [{time.time() - t0:.0f}s]")
        return
    test_invariants()
    test_indep(rows, 2000)
    test_poison(rows, 400)
    print(f"[TESTS G6] ALL PASS [{time.time() - t0:.0f}s]")


if __name__ == "__main__":
    main()
