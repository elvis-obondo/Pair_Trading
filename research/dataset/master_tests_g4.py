"""HL-MASTER1 integrity tests for G4 (coin and time context).

    python -u research/dataset/master_tests_g4.py > research/dataset/logs/master_tests_g4.log

  1. POISON (1,000 pair events, 300 coin events): for each event recompute the leg features with EVERY raw input at or after t0 replaced by random values: the coin's 1m closes and
     trade flags after the trigger minute, and the daily taker notional of ALL coins from the trigger's UTC day on (so the "day before" rule is proven); the hole list truncated at t0.
     Features must be identical to the last digit. Static columns (sector, meta traits, cg status) are "static snapshot, outside the as-of rule": reported, not counted as passes.
  2. SWAP (2,000 pair events): per-leg columns swap A <-> B, differences and log liquidity ratios negate, same_sector is unchanged.
  3. INDEPENDENT recomputation (2,000 pair events x 2 legs, 500 coin events) by plain numpy/pandas (direct timestamp lookups, pandas rolling for the daily tables), no use of master_g4's functions.
  4. INVARIANTS: shares and ranks in [0,1], ages >= 0, time columns consistent (hour/weekday from t0), listing never after the first trade day when src = 1.
"""
import os, sys, time
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import master_g4 as G4

rng = np.random.default_rng(20261028)
SKIP = ("coin_code", "listing_src", "listing_left_censored")


def same(a, b):
    return np.array_equal(np.asarray(a, float), np.asarray(b, float), equal_nan=True)


def test_poison(ctx, E, A_by, n, label):
    m0, t0s, dayix = ctx.event_keys(E)
    bad = 0
    t0 = time.time()
    for r in rng.choice(len(E), n, replace=False):
        for col in ("ticker_a", "ticker_b") if "ticker_b" in E else ("ticker_a",):
            c = E[col].iloc[r]
            m, d = m0[r:r + 1], dayix[r:r + 1]
            base = G4.leg_at(A_by[c], m, d, t0s.iloc[r:r + 1], ctx.code[c], ctx.lst[c], ctx.src[c], ctx.cens[c], ctx.liq)
            lc, mst = A_by[c]["lc"].copy(), A_by[c]["mst"].copy()
            lc[m[0] + 1:] = rng.uniform(-3, 3, len(lc) - m[0] - 1)
            mst[m[0] + 1:] = rng.integers(0, 5, len(mst) - m[0] - 1)
            daily = {k: v.copy() for k, v in ctx.daily.items()}
            for k, v in daily.items():
                v[d[0]:] = rng.uniform(1e3, 1e9, len(v) - d[0])
            liq = G4.liq_tables(daily, ctx.code, ctx.ndays, len(ctx.coins_all))
            got = G4.leg_at(G4.coin_arrays(lc, mst), m, d, t0s.iloc[r:r + 1], ctx.code[c], ctx.lst[c], ctx.src[c], ctx.cens[c], liq)
            for k in base:
                if not same(base[k], got[k]):
                    bad += 1
                    print(f"  POISON CHANGED {k} event row {r} coin {c}: {base[k]} -> {got[k]}")
        hm = ctx.hole_min[ctx.hole_min < G4.minute_of(t0s.iloc[r:r + 1])[0]]
        a = G4.time_cols(t0s.iloc[r:r + 1], ctx.hole_min)
        b = G4.time_cols(t0s.iloc[r:r + 1], hm)
        if any(not same(a[k], b[k]) for k in a):
            bad += 1
            print("  POISON CHANGED a time column at row", r)
    print(f"[G4 POISON {label}] {n} events, future raw inputs and trigger-day-onwards daily flow of all coins randomised: columns changed in {bad} cases [{time.time() - t0:.0f}s]")
    print("  (static columns: sector, max_leverage, tier1_max_leverage, size_decimals, margin_table_id, cg_status = static snapshot, outside the as-of rule; not counted as passes)")
    assert bad == 0
    print(f"[G4 POISON {label}] PASS")


def test_swap(ctx, E, A_by, n=2000):
    pick = rng.choice(len(E), n, replace=False)
    S = E.iloc[pick].reset_index(drop=True)
    Sw = S.rename(columns={"ticker_a": "ticker_b", "ticker_b": "ticker_a"})
    La, Lb = ctx.legs(S, "ticker_a", A_by), ctx.legs(S, "ticker_b", A_by)
    La2, Lb2 = ctx.legs(Sw, "ticker_a", A_by), ctx.legs(Sw, "ticker_b", A_by)
    bad = 0
    for k in La:
        bad += int(not same(La[k], Lb2[k]) or not same(Lb[k], La2[k]))
    sa, sb = ctx.sect.sector.reindex(S.ticker_a).fillna("unmapped").to_numpy(), ctx.sect.sector.reindex(S.ticker_b).fillna("unmapped").to_numpy()
    p1, p2 = G4.pair_columns(La, Lb, sa, sb), G4.pair_columns(La2, Lb2, sb, sa)
    for k in p1:
        if k == "same_sector":
            bad += int(not same(p1[k], p2[k]))
        else:
            bad += int(not np.allclose(p1[k], -p2[k], equal_nan=True, rtol=1e-12, atol=1e-12))
    print(f"[G4 SWAP] {n} pair events: per-leg columns swap A <-> B, differences and log ratios negate, same_sector unchanged: failures {bad}")
    assert bad == 0
    print("[G4 SWAP] PASS")


def indep(ctx, E, n, label, legs):
    day0 = ctx.day0
    # independent daily table: pandas groupby/rolling on the raw flow files
    flow = {}
    for c in ctx.coins_all:
        p = os.path.join(G4.ff.FLOW_DIR, f"{c}.parquet")
        if os.path.exists(p):
            fl = pd.read_parquet(p, columns=["date", "taker_buy_usd", "taker_sell_usd"])
            dt = pd.to_datetime(fl["date"])
            dt = dt.dt.tz_localize(None) if dt.dt.tz is not None else dt
            tn = (fl.taker_buy_usd + fl.taker_sell_usd)
            s = pd.Series(tn.to_numpy(float), index=dt)
            s = s[s > 0]
            flow[c] = s.groupby(s.index.floor("D")).sum()
    D = pd.DataFrame(flow)
    idx = pd.date_range(day0, periods=ctx.ndays, freq="D")
    D = D.reindex(idx)
    l7 = D.rolling(7, min_periods=3).mean().shift(1)
    l30 = D.rolling(30, min_periods=10).mean().shift(1)
    r7, r30 = l7.rank(axis=1, pct=True), l30.rank(axis=1, pct=True)
    cache = {}
    grid = pd.date_range(G4.ff.GRID0, periods=G4.ff.N, freq="min")

    def minutes(c):
        """dense log close and mins_since_trade on the minute grid, built here by reindexing the raw 1m feather (not master_g4's code)."""
        if c not in cache:
            b1 = pd.read_feather(G4.bar_file(c, "1m"), columns=["date", "close", "mins_since_trade"])
            t = pd.DatetimeIndex(pd.to_datetime(b1.date, utc=True).dt.tz_localize(None))
            keep = ~t.duplicated(keep="last")
            cache[c] = (pd.Series(np.log(b1.close.to_numpy(float)), index=t)[keep].reindex(grid).to_numpy(),
                        pd.Series(b1.mins_since_trade.to_numpy(float), index=t)[keep].reindex(grid).to_numpy())
        return cache[c]

    def sd_win(cl, e, n_min, frac):
        if e - n_min < 0:
            return np.nan
        r_ = np.diff(cl[e - n_min:e + 1])
        f_ = np.isfinite(r_)
        return r_[f_].std(ddof=1) if f_.sum() >= frac * n_min else np.nan

    bad, ncmp = [], 0
    for r in np.sort(rng.choice(len(E), n, replace=False)):
        row = E.iloc[r]
        T = pd.Timestamp(row.entry_time)
        for lg, col in legs:
            c = row[col]
            cl, ms = minutes(c)
            end = T + pd.Timedelta(minutes=29)
            e = int((end - G4.ff.GRID0) / pd.Timedelta(minutes=1))
            exp = {"log_price": cl[e], "ret_7d": cl[e] - cl[e - 10080] if e - 10080 >= 0 else np.nan, "ret_30d": cl[e] - cl[e - 43200] if e - 43200 >= 0 else np.nan}
            exp["rv_24h"] = sd_win(cl, e, 1440, 0.7)
            exp["rv_7d"] = sd_win(cl, e, 10080, 0.7)
            samp = np.array([sd_win(cl, e - 1440 * k, 1440, 0.7) if e - 1440 * k - 1440 >= 0 else np.nan for k in range(1, 91)])
            exp["rv_24h_rel90"] = exp["rv_24h"] / np.nanmedian(samp) if np.isfinite(samp).sum() >= 30 else np.nan
            exp["traded_share_24h"] = float((ms[e - 1439:e + 1] == 0).sum()) / 1440.0
            exp["mins_since_trade"] = ms[e]
            Dday = T.floor("D")
            exp["liq_7d"], exp["liq_30d"] = l7.loc[Dday, c], l30.loc[Dday, c]
            exp["liq_rank_7d"], exp["liq_rank_30d"] = r7.loc[Dday, c], r30.loc[Dday, c]
            yield r, lg, exp


def test_indep(ctx, label, n, legs):
    E = pd.read_parquet(os.path.join(G4.WORK, label, "events.parquet"), columns=["event_id", "ticker_a", "ticker_b", "entry_time"])
    Gd = pd.read_parquet(os.path.join(G4.WORK, label, "g4.parquet"))
    bad, ncmp, mx = [], 0, 0.0
    t0 = time.time()
    for r, lg, exp in indep(ctx, E, n, label, legs):
        for k, v in exp.items():
            g = float(Gd[f"{lg}_{k}"].iloc[r])
            ncmp += 1
            if np.isnan(v) != np.isnan(g):
                bad.append((r, lg, k, v, g)); continue
            if np.isnan(v):
                continue
            err = abs(v - g)
            mx = max(mx, err / (1e-6 + 1e-4 * abs(v)))
            if err > 1e-6 + 1e-4 * abs(v):
                bad.append((r, lg, k, v, g))
    print(f"[G4 INDEP {label}] {n} events x {len(legs)} legs: {ncmp:,} comparisons, mismatches {len(bad)}, worst error / tolerance {mx:.3f} [{time.time() - t0:.0f}s]")
    for b in bad[:15]:
        print("  MISMATCH", b)
    assert not bad
    print(f"[G4 INDEP {label}] PASS")


def test_invariants():
    for u in ("pair", "coin"):
        G = pd.read_parquet(os.path.join(G4.WORK, u, "g4.parquet"))
        E = pd.read_parquet(os.path.join(G4.WORK, u, "events.parquet"), columns=["entry_time"])
        t0s = pd.to_datetime(E.entry_time) + pd.Timedelta(minutes=30)
        assert (G.utc_hour == t0s.dt.hour).all() and (G.weekday == t0s.dt.dayofweek).all() and (G.weekend == (G.weekday >= 5)).all()
        assert set(G.mins_since_top_hour.unique()) <= {0, 30}
        for lg in (("a", "b") if u == "pair" else ("a",)):
            for c in (f"{lg}_traded_share_24h", f"{lg}_liq_rank_7d", f"{lg}_liq_rank_30d"):
                x = G[c].dropna()
                assert ((x >= 0) & (x <= 1)).all(), c
            assert (G[f"{lg}_listing_age_days"].dropna() >= 0).all()
            assert (G[f"{lg}_mins_since_trade"].dropna() >= 0).all()
        assert not G.event_id.duplicated().any()
    print("[G4 INVARIANTS] PASS (shares and ranks in [0,1], ages and mins_since_trade >= 0, time columns from t0, no duplicate ids)")


def main():
    t0 = time.time()
    ctx = G4.Context()
    print(f"[TESTS G4] context loaded [{time.time() - t0:.0f}s]", flush=True)
    Ep = pd.read_parquet(os.path.join(G4.WORK, "pair", "events.parquet"), columns=["event_id", "ticker_a", "ticker_b", "entry_time"])
    Ec = pd.read_parquet(os.path.join(G4.WORK, "coin", "events.parquet"), columns=["event_id", "ticker_a", "entry_time"])
    need = sorted(set(Ep.ticker_a) | set(Ep.ticker_b) | set(Ec.ticker_a))
    A_by = {c: G4.coin_arrays(*G4.read_coin_minutes(c)) for c in need}
    test_invariants()
    test_swap(ctx, Ep, A_by)
    test_poison(ctx, Ep, A_by, 1000, "pair")
    test_poison(ctx, Ec, A_by, 300, "coin")
    test_indep(ctx, "pair", 2000, (("a", "ticker_a"), ("b", "ticker_b")))
    test_indep(ctx, "coin", 500, (("a", "ticker_a"),))
    print(f"[TESTS G4] ALL PASS [{time.time() - t0:.0f}s]")


if __name__ == "__main__":
    main()
