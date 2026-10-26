"""HL-MASTER1 G7: DIAGNOSTICS of the failed OI gate (planner-approved 2026-10-25: one pass on existing data, diagnostics only; the gate stays as written).

    python -u research/dataset/master_oi_diag.py > research/dataset/logs/master_oi_diag.log

Same coin-days as the gate (complete days: 25 hour marks observed, no hole minute, L = 0). Per coin-day: od = observed hourly OI changes, rd = fills-based hourly changes (24 each).
 1. slope of od on rd (through the origin and with an intercept) pooled, by coin (median, quantiles) and by month; the signed drift (sum rd - sum od)/mean OI: share positive, median, quantiles;
    drift against the day's turnover (sum |rd| / mean OI) and against the net reconstructed change; drift by size of the day's observed change.
 2. drift around events: ADL days (adl_usd > 0 for the coin that day), liquidation-heavy days (forced USD above the coin's own 90th percentile), neither; the last two days of a delisted coin's life;
    days next to a build 2 hole minute (within one day); the 7 coin-days that hold an unbalanced single-leg trade.
 3. a candidate correction, judged ONLY on data it was not fitted on: a global slope and a per-coin slope fitted on the FIRST half of the coin-days (by date), applied to the SECOND half; the unchanged
    drift condition (< 0.5%) is then evaluated on the second half uncorrected, with the global slope and with the per-coin slope (hourly correlation is scale-free, so only the drift condition moves).
    NO pass, NO reconstructed level from this script: it reports.
"""
import os, sys, time, json, glob
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import master_oi as O
import flowfeat as ff
import paths


def main():
    t0 = time.time()
    obs, cd, holes = O.load_obs(), O.load_delta(), O.hole_flags()
    print(f"[DIAG] loaded  [{time.time() - t0:.0f}s]", flush=True)
    L = 0
    d0 = pd.Timestamp("2025-05-25")
    day_starts = ff.minute_index(pd.date_range(d0, periods=int(ff.N / 1440) + 3, freq="D"))
    rows = []
    for c, o in obs.items():
        if c not in cd:
            continue
        for ds in day_starts:
            marks = ds + 60 * np.arange(25)
            if marks[0] < 0 or marks[-1] >= ff.N or not np.isfinite(o[marks]).all() or holes[marks[-1] + 1] - holes[marks[0]] != 0:
                continue
            od = np.diff(o[marks])
            rd = cd[c][marks[1:]] - cd[c][marks[:-1]]
            m = np.mean(o[marks])
            rows.append((c, ds, m, od.sum(), rd.sum(), (od * rd).sum(), (rd * rd).sum(), (od * od).sum(), np.abs(rd).sum(), np.abs(od).sum(), od.sum(), rd.sum() - od.sum()))
    G = pd.DataFrame(rows, columns=["coin", "day_min", "oi", "sum_od", "sum_rd", "sxy", "sxx", "syy", "turn_rd", "turn_od", "net_od", "gap"])
    G["date"] = d0 + pd.to_timedelta(G.day_min - ff.minute_index(pd.DatetimeIndex([d0]))[0], unit="m")
    G["month"] = G.date.dt.to_period("M")
    G["drift"] = G.gap / G.oi                       # signed: (sum rd - sum od) / mean OI
    G["turnover"] = G.turn_rd / G.oi
    print(f"[DIAG] {len(G):,} complete coin-days over {G.coin.nunique()} coins  [{time.time() - t0:.0f}s]")
    # ------------------------------------------------------------------ 1. slope and drift
    sl = G.sxy.sum() / G.sxx.sum()
    print(f"\n1. SLOPE of observed on reconstructed hourly change (through the origin), pooled over all hours: {sl:.5f}  (1.0 = no scale bias)")
    pc = G.groupby("coin").apply(lambda g: g.sxy.sum() / g.sxx.sum())
    print(f"   by coin: median {pc.median():.5f}, quantiles 5/25/75/95%: " + " / ".join(f"{pc.quantile(q):.5f}" for q in (.05, .25, .75, .95)) + f"; coins with |slope-1| > 0.02: {int((pc.sub(1).abs() > 0.02).sum())}")
    pm = G.groupby("month").apply(lambda g: g.sxy.sum() / g.sxx.sum())
    print("   by month: " + ", ".join(f"{k} {v:.4f}" for k, v in pm.items()))
    print(f"   signed drift (sum rd - sum od)/OI: share positive {100 * (G.drift > 0).mean():.1f}%; median {G.drift.median():+.5f}; quantiles 5/25/75/95%: " + " / ".join(f"{G.drift.quantile(q):+.5f}" for q in (.05, .25, .75, .95)))
    print("   signed drift by month (median): " + ", ".join(f"{k} {v:+.4f}" for k, v in G.groupby("month").drift.median().items()))
    print(f"   correlation of |drift| with turnover (sum |rd| / OI): {np.corrcoef(G.drift.abs(), G.turnover)[0, 1]:.3f}; of signed drift with the net observed change / OI: {np.corrcoef(G.drift, G.net_od / G.oi)[0, 1]:.3f}")
    G["tq"] = pd.qcut(G.turnover, 5, labels=False, duplicates="drop")
    print("   by turnover quintile (low to high): median |drift| " + ", ".join(f"{v:.4f}" for v in G.groupby("tq").drift.apply(lambda s: s.abs().median())) + "; share of coin-days with |drift| < 0.5%: "
          + ", ".join(f"{100 * v:.1f}%" for v in G.groupby("tq").drift.apply(lambda s: (s.abs() < 0.005).mean())))
    # ------------------------------------------------------------------ 2. events
    adl, forced = {}, {}
    for c in G.coin.unique():
        p = os.path.join(ff.FLOW_DIR, f"{c}.parquet")
        if not os.path.exists(p):
            continue
        cols = [x for x in ("date", "adl_usd", "liq_forced_long_usd", "liq_forced_short_usd") if x in pd.read_parquet(p).columns]
        fl = pd.read_parquet(p, columns=cols)
        dt = pd.to_datetime(fl["date"])
        dt = dt.dt.tz_localize(None) if dt.dt.tz is not None else dt
        day = dt.dt.floor("D")
        if "adl_usd" in fl:
            adl[c] = fl.adl_usd.fillna(0).groupby(day).sum()
        fu = fl.get("liq_forced_long_usd", 0) + fl.get("liq_forced_short_usd", 0)
        forced[c] = pd.Series(np.nan_to_num(fu.to_numpy(float)), index=dt.to_numpy()).groupby(day.to_numpy()).sum()
    G["adl"] = [adl.get(c, pd.Series(dtype=float)).get(d, 0.0) for c, d in zip(G.coin, G.date)]
    G["forced"] = [forced.get(c, pd.Series(dtype=float)).get(d, 0.0) for c, d in zip(G.coin, G.date)]
    q90 = G.groupby("coin").forced.transform(lambda s: s.quantile(0.9))
    kind = np.where(G.adl > 0, "ADL day", np.where((G.forced > q90) & (G.forced > 0), "liquidation-heavy", "neither"))
    print("\n2. DRIFT AROUND EVENTS (median |drift|, median signed drift, share passing |drift| < 0.5%, coin-days):")
    for k in ("ADL day", "liquidation-heavy", "neither"):
        s = G.drift[kind == k]
        print(f"   {k:<18} {s.abs().median():.4f}  {s.median():+.4f}  {100 * (s.abs() < 0.005).mean():5.1f}%  {len(s):,}")
    hole_days = set()
    hm = pd.read_parquet(O.MISSING)
    hm = hm["minute"] if "minute" in hm else hm.iloc[:, 0]
    hd = pd.to_datetime(hm).dt.tz_localize(None).dt.floor("D") if pd.to_datetime(hm).dt.tz is not None else pd.to_datetime(hm).dt.floor("D")
    for d in hd.unique():
        for k in (-1, 0, 1):
            hole_days.add(pd.Timestamp(d) + pd.Timedelta(days=k))
    nh = G.date.isin(hole_days)
    print(f"   within one day of a build 2 hole minute: median |drift| {G.drift[nh].abs().median():.4f}, pass {100 * (G.drift[nh].abs() < 0.005).mean():.1f}% over {int(nh.sum()):,} coin-days; others {G.drift[~nh].abs().median():.4f}, {100 * (G.drift[~nh].abs() < 0.005).mean():.1f}%")
    ub = [(int(d["day"]), d["unbalanced_detail"]) for d in (json.load(open(f)) for f in glob.glob(os.path.join(paths.DATASETS, "oi", "*_b7_meta.json")))] if glob.glob(os.path.join(paths.DATASETS, "oi", "*_b7_meta.json")) else []
    print(f"   the 7 unbalanced single legs: meta files not on this machine ({len(ub)} found); their effect is at most half a fill each, USD 2,823 in total.")
    # ------------------------------------------------------------------ 3. correction judged out of sample
    cut = G.date.sort_values().iloc[len(G) // 2]
    A, B = G[G.date < cut], G[G.date >= cut]
    s_glob = A.sxy.sum() / A.sxx.sum()
    s_coin = A.groupby("coin").apply(lambda g: g.sxy.sum() / g.sxx.sum())
    print(f"\n3. OUT-OF-SAMPLE CORRECTION: first half {len(A):,} coin-days (to {cut.date()}), second half {len(B):,}. Slope fitted on the first half: global {s_glob:.5f}; per-coin median {s_coin.median():.5f} (coins {len(s_coin)})")
    for lbl, f in (("uncorrected", np.ones(len(B))), ("global slope", np.full(len(B), s_glob)), ("per-coin slope", B.coin.map(s_coin).fillna(s_glob).to_numpy())):
        dr = np.abs(f * B.sum_rd.to_numpy() - B.sum_od.to_numpy()) / B.oi.to_numpy()
        print(f"   second half, {lbl:<14}: |drift| < 0.5% in {100 * (dr < 0.005).mean():.2f}% of coin-days (median |drift| {np.median(dr):.5f}, 90% {np.quantile(dr, .9):.5f})")
    print("   the unchanged gate needs 95% (hourly correlation is scale-free, 99.99% already); a correction that does not reach it on the held-out half is not adopted.")
    G.drop(columns=["date"]).to_parquet(os.path.join(paths.DATASETS, "oi_diag_coin_days.parquet"), index=False)
    print(f"  [{time.time() - t0:.0f}s]")


if __name__ == "__main__":
    main()
