"""HL-EVENT1 pass 1: the market-wide minute arrays every coin-level event needs.

    python -u research/dislocation_model/evmarket.py

One pass over all 206 coins' 1-minute closes and flow files. Output datasets/ev_market.npz:
  S1m, n1m    per minute: the sum and the count of finite 1-minute log returns across ALL
              coins (a return is finite only if both the minute's close and the previous
              minute's close are finite). A coin's equal-weight index excludes itself:
              idx_c(m) = (S1m[m] - r_c(m)) / (n1m[m] - 1), valid when r_c(m) is finite and
              n1m[m] - 1 >= 30 (the build 4 benchmark rule).
  mkt_liq     per minute: forced-liquidation notional (long + short) summed over all coins;
              NaN on archive-hole minutes (a coin outside its life contributes 0).
  breadth_j   per half-hour cutoff j (cutoff offset 28 + 30 j minutes from the window start):
              the share of live coins whose 60-minute |log return| exceeds twice the std of
              that coin's 60-minute returns at the cutoffs ending at or before C - 60 over
              7 days (flowfeat.py's definition; coins with < 144 valid samples excluded).
Everything is indexed by minute offset from flowfeat.GRID0 (2025-05-25 14:32 UTC).
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd

import paths
import flowfeat as ff
from adapters.hyperliquid_futures import HL_FUTURES_DIR

OUT = os.path.join(paths.DATASETS, "ev_market.npz")


def load_lc(coin):
    """Dense 1-minute log close on the window grid (NaN outside the life and in hole minutes)."""
    b1 = pd.read_feather(HL_FUTURES_DIR / f"{coin}-1m.feather", columns=["date", "close"])
    lc = np.full(ff.N, np.nan)
    ix = ff.minute_index(b1["date"].dt.tz_localize(None))
    ok = (ix >= 0) & (ix < ff.N)
    lc[ix[ok]] = np.log(b1["close"].to_numpy(float)[ok])
    return lc


def ret1m(lc):
    r = np.full(ff.N, np.nan)
    r[1:] = lc[1:] - lc[:-1]
    return r


def main():
    t0 = time.time()
    coins = sorted(f[:-8] for f in os.listdir(ff.FLOW_DIR) if f.endswith(".parquet"))
    S = np.zeros(ff.N); n = np.zeros(ff.N, np.int32)
    mkt = np.zeros(ff.N)
    jgrid = ff.CUT_PHASE + 30 * np.arange(ff.NJ)
    exceed = np.zeros(ff.NJ); nvalid = np.zeros(ff.NJ)
    for ci, c in enumerate(coins):
        lc = load_lc(c)
        r = ret1m(lc)
        fin = np.isfinite(r)
        S += np.where(fin, r, 0.0); n += fin
        fl = pd.read_parquet(os.path.join(ff.FLOW_DIR, f"{c}.parquet"), columns=["date", "liq_forced_long_usd", "liq_forced_short_usd"])
        mkt += np.nan_to_num(ff.dense(fl, "liq_forced_long_usd")) + np.nan_to_num(ff.dense(fl, "liq_forced_short_usd"))
        lcj = lc[jgrid - 1]
        r60 = np.full(ff.NJ, np.nan); r60[2:] = lcj[2:] - lcj[:-2]
        sd = pd.Series(r60).rolling(ff.TRAIL, min_periods=ff.MINVALID).std().to_numpy()
        sdp = np.full(ff.NJ, np.nan); sdp[2:] = sd[:-2]
        v = np.isfinite(r60) & np.isfinite(sdp)
        exceed += np.where(v, np.abs(r60) > 2 * sdp, False); nvalid += v
        if (ci + 1) % 40 == 0:
            print(f"  coin {ci + 1}/{len(coins)}  [{time.time() - t0:.0f}s]", flush=True)
    holes = pd.read_parquet(ff.HOLES)["minute"]
    hix = ff.minute_index(holes.dt.tz_localize(None))
    hole = np.zeros(ff.N, bool); hole[hix[(hix >= 0) & (hix < ff.N)]] = True
    mkt = np.where(hole, np.nan, mkt)
    breadth = np.where(nvalid > 0, exceed / np.maximum(nvalid, 1), np.nan)
    np.savez_compressed(OUT, S1m=S, n1m=n, mkt_liq=mkt, breadth_j=breadth, hole=hole)
    print(f"[EVMARKET] {len(coins)} coins; 1-minute returns finite on {int((n >= 31).sum()):,} of {ff.N:,} minutes with >= 31 coins; "
          f"min n {int(n.min())}, median {int(np.median(n))}, max {int(n.max())}; hole minutes {int(hole.sum())}; "
          f"breadth finite at {int(np.isfinite(breadth).sum()):,} of {ff.NJ:,} cutoffs  [{time.time() - t0:.0f}s]")


if __name__ == "__main__":
    main()
