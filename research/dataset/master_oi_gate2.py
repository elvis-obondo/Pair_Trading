"""HL-MASTER1 G7: the OI gate re-run with the units DEFINITION applied (planner ruling 2026-10-25): asset_ctxs open_interest = sum of |positions| = 2 x one-sided OI, so oi_delta in asset_ctxs units is
sum(|p'| - |p|) over every fill (no half, no fitted constant) = 2 x build7_oi.py's oi_delta_coin.  Everything else is the UNCHANGED gate of master_oi.py (L = 0, complete coin-days, hourly-change
correlation >= 0.99 AND one-day drift < 0.5% of mean OI, >= 95% of coin-days).

    python -u research/dataset/master_oi_gate2.py > research/dataset/logs/master_oi_gate2.log

Reports: all coin-days; the first half (by date, the diagnostic half) and the second half (HELD OUT; its verdict governs if they differ); the failure breakdown (ADL days, liquidation-heavy days,
month, coin, turnover quintile) and the 2026-05 line (which coins and days carry the low slope). No fitting. One pass.
"""
import os, sys, time
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import master_oi as O
import flowfeat as ff
import paths

UNITS = 2.0                                           # asset_ctxs units: no half


def main():
    t0 = time.time()
    obs, cd, holes = O.load_obs(), O.load_delta(), O.hole_flags()
    print(f"[GATE2] loaded  [{time.time() - t0:.0f}s]", flush=True)
    d0 = pd.Timestamp("2025-05-25")
    base = ff.minute_index(pd.DatetimeIndex([d0]))[0]
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
            rd = UNITS * (cd[c][marks[1:]] - cd[c][marks[:-1]])
            m = np.mean(o[marks])
            if od.std() == 0 or rd.std() == 0:
                corr = 1.0 if (np.all(od == 0) and np.all(rd == 0)) else np.nan
            else:
                corr = np.corrcoef(od, rd)[0, 1]
            rows.append((c, ds, m, corr, abs(rd.sum() - od.sum()) / max(m, 1e-12), (rd.sum() - od.sum()) / max(m, 1e-12), np.abs(rd).sum() / max(m, 1e-12), (od * rd).sum(), (rd * rd).sum()))
    G = pd.DataFrame(rows, columns=["coin", "day_min", "oi", "corr", "drift", "sdrift", "turnover", "sxy", "sxx"])
    G["date"] = d0 + pd.to_timedelta(G.day_min - base, unit="m")
    G["month"] = G.date.dt.to_period("M")
    G["pass"] = (G["corr"] >= 0.99) & (G.drift < 0.005)
    G["pass_corr"], G["pass_drift"] = G["corr"] >= 0.99, G.drift < 0.005
    cut = G.date.sort_values().iloc[len(G) // 2]
    A, B = G[G.date < cut], G[G.date >= cut]
    print(f"[GATE2] {len(G):,} coin-days over {G.coin.nunique()} coins; first half {len(A):,} (to {cut.date()}), second half {len(B):,}")
    for lbl, S in (("ALL coin-days", G), ("first half (diagnostic)", A), ("SECOND HALF (held out; the verdict)", B)):
        print(f"  {lbl:<38} both {100 * S['pass'].mean():6.2f}%   corr>=0.99 {100 * S.pass_corr.mean():6.2f}%   drift<0.5% {100 * S.pass_drift.mean():6.2f}%   |drift| quantiles 50/90/95/99%: "
              + " / ".join(f"{S.drift.quantile(q):.5f}" for q in (.5, .9, .95, .99)))
    # flow ingredients for the breakdown
    adl, forced = {}, {}
    for c in G.coin.unique():
        p = os.path.join(ff.FLOW_DIR, f"{c}.parquet")
        if not os.path.exists(p):
            continue
        fl = pd.read_parquet(p, columns=["date", "adl_usd", "liq_forced_long_usd", "liq_forced_short_usd"])
        dt = pd.to_datetime(fl["date"])
        dt = dt.dt.tz_localize(None) if dt.dt.tz is not None else dt
        day = dt.dt.floor("D")
        adl[c] = fl.adl_usd.fillna(0).groupby(day).sum()
        forced[c] = (fl.liq_forced_long_usd.fillna(0) + fl.liq_forced_short_usd.fillna(0)).groupby(day).sum()
    G["adl"] = [adl.get(c, pd.Series(dtype=float)).get(d, 0.0) for c, d in zip(G.coin, G.date)]
    G["forced"] = [forced.get(c, pd.Series(dtype=float)).get(d, 0.0) for c, d in zip(G.coin, G.date)]
    q90 = G.groupby("coin").forced.transform(lambda s: s.quantile(0.9))
    G["kind"] = np.where(G.adl > 0, "ADL day", np.where((G.forced > q90) & (G.forced > 0), "liquidation-heavy", "neither"))
    print("\nFAILURE BREAKDOWN (units definition applied). Pass share (both conditions), median |drift|, coin-days -- all days | second half:")
    for k in ("ADL day", "liquidation-heavy", "neither"):
        S, SB = G[G.kind == k], B.assign(kind=G.loc[B.index, "kind"])
        SB = SB[SB.kind == k]
        print(f"   {k:<18} {100 * S['pass'].mean():6.2f}%  {S.drift.median():.5f}  {len(S):>7,}   |   {100 * SB['pass'].mean():6.2f}%  {SB.drift.median():.5f}  {len(SB):>7,}")
    neither = G[G.kind == "neither"]
    print(f"   gate WITHOUT ADL and liquidation-heavy days: all {100 * neither['pass'].mean():.2f}%, second half {100 * neither[neither.date >= cut]['pass'].mean():.2f}% (for the user to see whether those days alone account for the shortfall; the verdict is not changed by it)")
    print("   by month (pass share): " + ", ".join(f"{k} {100 * v:.1f}%" for k, v in G.groupby("month")["pass"].mean().items()))
    G["tq"] = pd.qcut(G.turnover, 5, labels=False, duplicates="drop")
    print("   by turnover quintile (low to high), pass share: " + ", ".join(f"{100 * v:.1f}%" for v in G.groupby("tq")["pass"].mean()) + "; median |drift|: " + ", ".join(f"{v:.5f}" for v in G.groupby("tq").drift.median()))
    pc = G.groupby("coin")["pass"].mean().sort_values()
    print(f"   coins with their own pass share < 95%: {int((pc < 0.95).sum())} of {len(pc)}; 10 lowest: " + ", ".join(f"{c} {100 * v:.0f}%" for c, v in pc.head(10).items()) + f"; median coin pass share {100 * pc.median():.1f}%")
    # 2026-05 line
    M5 = G[G.month == "2026-05"].copy()
    sl = M5.groupby("coin").apply(lambda g: g.sxy.sum() / g.sxx.sum()) / UNITS      # 1.0 = exact definition
    bad = sl[(sl - 1).abs() > 0.02]
    print(f"\n2026-05: pooled slope (units applied; 1.0 exact) {M5.sxy.sum() / M5.sxx.sum() / UNITS:.4f}; coins with |slope - 1| > 0.02 in that month: {len(bad)} of {len(sl)}: " + ", ".join(f"{c} {v:.3f}" for c, v in bad.sort_values().head(15).items()))
    pdays = M5.groupby(M5.date.dt.day).apply(lambda g: g.sxy.sum() / g.sxx.sum() / UNITS)
    print("   by day of May 2026 (slope): " + ", ".join(f"{k} {v:.3f}" for k, v in pdays.items() if abs(v - 1) > 0.01))
    ok = (B["pass"].mean() >= 0.95) and (G["pass"].mean() >= 0.95)
    print(f"\n[OI GATE2] second half {100 * B['pass'].mean():.2f}%, all days {100 * G['pass'].mean():.2f}% (needs >= 95% on the held-out half AND on all days): {'PASS' if ok else 'FAIL'}")
    G.drop(columns=["date"]).to_parquet(os.path.join(paths.DATASETS, "oi_gate2_coin_days.parquet"), index=False)
    print(f"  [{time.time() - t0:.0f}s]")
    if not ok:
        sys.exit(2)


if __name__ == "__main__":
    main()
