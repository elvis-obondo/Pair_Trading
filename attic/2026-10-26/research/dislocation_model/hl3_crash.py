"""HL-FLOW1 Part 4: the 10 October 2025 cascade as its own event (descriptive, no model).

Window A: dislocations whose trigger time (the cutoff C = entry_time + 30 min) falls in
2025-10-10 20:00 - 2025-10-11 02:00 UTC. Window B: the 3 hours before it (17:00 - 20:00).
For each: n, reach rate against the mean chance probability, and the split by terciles
of the H1 forced-share feature (h1_forced_share_60; terciles taken inside the window set,
rows with a NaN excluded and counted). Descriptive only.

PRE-REGISTERED ROW, on ALL dislocations: a BTC shock is a minute t where BTC's 30-minute
return ending at t (1-minute closes) is below -5%. An episode is in the cascade regime
when its trigger time C lies in (t, t + 3 h] of some shock minute. Compared with the
rest: n, reach rate, mean chance, and the gap (reach - chance), with the difference of
gaps and a day-clustered 95% interval over all episodes.

SEAM / HOLE CHECK for the crash window: archive hole minutes in 2025-10-10 17:00 -
2025-10-11 03:00 (from missing_minutes.parquet), and the 5 mid-2025 seams' distance.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd

import flowfeat as ff
from adapters.hyperliquid_futures import HL_FUTURES_DIR
from hl3_common import Pop


def describe(lbl, m, P, fs=None):
    n = int(m.sum())
    if n == 0:
        print(f"  {lbl}: n 0")
        return
    y, c = P.y[m], P.chance[m]
    print(f"  {lbl}: n {n:,}, reach rate {y.mean():.4f}, mean chance {c.mean():.4f}, gap {y.mean() - c.mean():+.4f}")
    if fs is not None:
        v = fs[m]
        ok = np.isfinite(v)
        print(f"      forced-share terciles (h1_forced_share_60): rows with a value {int(ok.sum()):,}, NaN {int((~ok).sum()):,}")
        if ok.sum() >= 3:
            q = np.quantile(v[ok], [1 / 3, 2 / 3])
            for lbl2, mm in (("low ", ok & (v <= q[0])), ("mid ", ok & (v > q[0]) & (v <= q[1])), ("high", ok & (v > q[1]))):
                yy, cc = y[mm], c[mm]
                print(f"        tercile {lbl2}: n {int(mm.sum()):>4}, reach {yy.mean():.4f}, chance {cc.mean():.4f}, gap {yy.mean() - cc.mean():+.4f}"
                      f"   (forced share {v[mm].min():.4f} .. {v[mm].max():.4f})")


def main():
    P = Pop()
    Z = np.load(ff.OUT, allow_pickle=False)
    names = [str(x) for x in Z["names"]]
    fs = Z["X"][P.rows][:, names.index("h1_forced_share_60")].astype(float)
    C = pd.to_datetime(P.meta.entry_time) + pd.Timedelta(minutes=30)
    print("=" * 110)
    print("HL-FLOW1 PART 4 -- the 10 October 2025 cascade")
    print("=" * 110)
    print(f"  matched population {P.n:,}; trigger time = entry_time + 30 min (the cutoff)")
    a0, a1 = pd.Timestamp("2025-10-10 20:00"), pd.Timestamp("2025-10-11 02:00")
    b0 = a0 - pd.Timedelta(hours=3)
    wa = ((C > a0) & (C <= a1)).to_numpy()
    wb = ((C > b0) & (C <= a0)).to_numpy()
    print(f"  rows are from {'fit' if (P.sp.fit[wa]).all() else 'mixed'} days (the crash is before CUT 2026-05-25; the last fit day is {pd.Timestamp(P.sp.fit_days.max()).date()}); descriptive only")
    describe("WINDOW A  2025-10-10 20:00 - 2025-10-11 02:00", wa, P, fs)
    describe("WINDOW B  the 3 hours before (17:00 - 20:00)", wb, P, fs)
    describe("everything else", ~(wa | wb), P)
    # ---- the pre-registered BTC row
    b1 = pd.read_feather(HL_FUTURES_DIR / "BTC-1m.feather", columns=["date", "close"])
    ix = ff.minute_index(b1["date"].dt.tz_localize(None))
    px = np.full(ff.N, np.nan); ok = (ix >= 0) & (ix < ff.N); px[ix[ok]] = b1["close"].to_numpy(float)[ok]
    ret30 = np.full(ff.N, np.nan); ret30[30:] = px[30:] / px[:-30] - 1.0
    shock = np.flatnonzero(ret30 < -0.05)
    print()
    print(f"  BTC shocks (30-minute return < -5%, 1-minute closes): {len(shock):,} minutes; first {ff.GRID0 + pd.Timedelta(minutes=int(shock[0])) if len(shock) else None}")
    if len(shock):
        grp = np.split(shock, np.flatnonzero(np.diff(shock) > 180) + 1)
        for g in grp:
            lo, hi = ff.GRID0 + pd.Timedelta(minutes=int(g[0])), ff.GRID0 + pd.Timedelta(minutes=int(g[-1]))
            print(f"    shock cluster {lo} .. {hi}  ({len(g)} minutes), BTC min 30m return {ret30[g].min():+.4f}")
    o = ff.minute_index(C)
    inreg = np.zeros(P.n, bool)
    sh = np.zeros(ff.N + 1, np.int64)
    sh[shock + 1] += 1
    cs = np.cumsum(sh)                         # cs[k] = shocks at minutes < k
    inreg = (cs[o] - cs[np.maximum(o - 180, 0)]) > 0     # a shock minute t with C - 180 <= t < C
    print()
    for lbl, m in (("IN the cascade regime (C within 3h after a BTC shock)", inreg), ("the rest", ~inreg)):
        describe(lbl, m, P)
    y, c, day = P.y, P.chance, P.day
    gap = lambda m: y[m].mean() - c[m].mean()
    pt = gap(inreg) - gap(~inreg) if inreg.any() else np.nan
    days = np.unique(day)
    pos = {d: np.flatnonzero(day == d) for d in days}
    rb = np.random.default_rng(20261015)
    dr = []
    for _ in range(300):
        ix_ = np.concatenate([pos[d] for d in rb.choice(days, len(days), replace=True)])
        mi = inreg[ix_]
        if mi.sum() > 0 and (~mi).sum() > 0:
            dr.append((y[ix_][mi].mean() - c[ix_][mi].mean()) - (y[ix_][~mi].mean() - c[ix_][~mi].mean()))
    lo, hi = np.percentile(dr, [2.5, 97.5]) if dr else (np.nan, np.nan)
    rd = pd.to_datetime(C[inreg]).dt.floor("D").unique()
    print(f"  regime episodes fall on {len(rd)} calendar day(s): {', '.join(str(x.date()) for x in rd)}"
          f"  -> a day-clustered interval over this few clusters is NOT meaningful; descriptive, fit period")
    print(f"  difference of gaps (regime minus rest): {pt:+.4f}  day-clustered 95% [{lo:+.4f}, {hi:+.4f}]  "
          f"(n regime {int(inreg.sum()):,}, rest {int((~inreg).sum()):,}; {len(dr)} valid resamples)")
    # ---- hole / seam check
    holes = pd.read_parquet(ff.HOLES)["minute"].dt.tz_localize(None)
    h_in = holes[(holes >= pd.Timestamp("2025-10-10 17:00")) & (holes < pd.Timestamp("2025-10-11 03:00"))]
    print()
    print(f"  HOLE CHECK: archive hole minutes in 2025-10-10 17:00 - 2025-10-11 03:00: {len(h_in)}")
    seams = [pd.Timestamp(s) for s in ("2025-06-08 09:30", "2025-06-08 10:00", "2025-07-19 09:30", "2025-07-27 11:30", "2025-09-27 09:00")]
    print("  nearest seam to the crash window: " + str(min(abs(a0 - s) for s in seams)) + " away")


if __name__ == "__main__":
    main()
