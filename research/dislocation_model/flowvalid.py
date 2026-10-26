"""HL-FLOW1 Part 2 validator: recompute the features for 500 random rows, independently.

For each sampled row the features are recomputed from the per-minute flow and 1-minute
bar files with direct slicing and summation (no cumulative sums, no rolling objects),
on arrays TRUNCATED AT THE ROW'S CUTOFF C = entry_time + 30 min: every array is cut to
the minutes before C before any feature is read, so a read at or after C would raise.
Each value is compared with the stored flowfeat.npz (float32 storage: rtol 1e-4,
atol 1e-5); NaN patterns must match exactly. Any mismatch aborts.
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd

import paths
import flowfeat as ff
from adapters.hyperliquid_futures import HL_FUTURES_DIR

SEED = 20261015
NROWS = 500


def leg_features(a, o, s, W):
    """Leg quantities from the arrays `a` (each already truncated to minutes < C = o)."""
    out = {q: np.nan for q in ff.LEG_Q}
    if o - W < 0:
        return out, np.nan, np.nan
    seg = lambda k: a[k][o - W:o]
    assert len(seg("taker_buy_usd")) == W and len(a["taker_buy_usd"]) == o
    if np.isnan(seg("taker_buy_usd")).any():
        return out, np.nan, np.nan
    buy, sell = seg("taker_buy_usd").sum(), seg("taker_sell_usd").sum()
    tn = buy + sell
    if not tn > 0:
        return out, tn, np.nan
    pick = lambda kp, kn: (seg(kp) if s > 0 else seg(kn)).sum()
    out["forced_share"] = pick("liq_forced_short_usd", "liq_forced_long_usd") / tn
    out["backstop_share"] = seg("backstop_liq_usd").sum() / tn
    out["adl_share"] = seg("adl_usd").sum() / tn
    op, cp = pick("open_buy_usd", "open_sell_usd") / tn, pick("close_buy_usd", "close_sell_usd") / tn
    out["open_push"], out["close_push"] = op, cp
    out["open_close_ratio"] = op / (op + cp) if (op + cp) > 0 else np.nan
    tnm = seg("taker_buy_usd") + seg("taker_sell_usd")
    out["top3"] = np.where(tnm > 0, np.nan_to_num(seg("top3_taker_share")) * tnm, 0.0).sum() / tn
    wallets = seg("n_taker_wallets").sum()
    out["wallets_per_musd"] = wallets / (tn / 1e6)
    tw = seg("twap_taker_usd")
    out["twap_share"] = np.nan if np.isnan(tw).any() else tw.sum() / tn
    return out, tn, (buy - sell) / tn


def wallets_norm(a, o, W):
    """Median of the wallets-per-$M quantity at the 336 cutoffs ending at or before the window start."""
    vals = []
    for k in range(ff.TRAIL):
        ce = o - W - 30 * k
        if ce - W < 0:
            continue
        sl = slice(ce - W, ce)
        b = a["taker_buy_usd"][:o][sl]
        if len(b) != W or np.isnan(b).any():
            continue
        tn = b.sum() + a["taker_sell_usd"][:o][sl].sum()
        if tn > 0:
            vals.append(a["n_taker_wallets"][:o][sl].sum() / (tn / 1e6))
    return np.median(vals) if len(vals) >= ff.MINVALID else np.nan


def run():
    t0 = time.time()
    meta = pd.read_parquet(paths.META)
    Z = np.load(ff.OUT, allow_pickle=False)
    X, names = Z["X"], [str(x) for x in Z["names"]]
    n = len(meta)
    rng = np.random.default_rng(SEED)
    rows = np.sort(rng.choice(n, NROWS, replace=False))
    d = np.sign(meta.z_at_entry.to_numpy(float)); d[d == 0] = 1.0
    beta = meta.beta.to_numpy(float)
    C = pd.to_datetime(meta.entry_time) + pd.Timedelta(minutes=30)
    o_all = ff.minute_index(C)
    holes = pd.read_parquet(ff.HOLES)["minute"]
    hix = ff.minute_index(holes.dt.tz_localize(None))
    hole = np.zeros(ff.N, bool); hole[hix[(hix >= 0) & (hix < ff.N)]] = True
    allcoins = sorted(f[:-8] for f in os.listdir(ff.FLOW_DIR) if f.endswith(".parquet"))
    legcoins = set(meta.ticker_a.iloc[rows]) | set(meta.ticker_b.iloc[rows])
    flow, lc = {}, {}
    mkt = np.zeros(ff.N)
    for c in allcoins:
        fl = pd.read_parquet(os.path.join(ff.FLOW_DIR, f"{c}.parquet"), columns=["date"] + ff.CORE)
        cols = {k: ff.dense(fl, k) for k in ff.CORE}
        mkt += np.nan_to_num(cols["liq_forced_long_usd"]) + np.nan_to_num(cols["liq_forced_short_usd"])
        if c in legcoins:
            flow[c] = cols
        b1 = pd.read_feather(HL_FUTURES_DIR / f"{c}-1m.feather", columns=["date", "close"])
        a = np.full(ff.N, np.nan)
        ix = ff.minute_index(b1["date"].dt.tz_localize(None)); ok = (ix >= 0) & (ix < ff.N)
        a[ix[ok]] = np.log(b1["close"].to_numpy(float)[ok])
        lc[c] = a
    mkt[hole] = np.nan
    print(f"[VALID] loaded {len(allcoins)} coins' 1m closes and {len(flow)} leg coins' flow  [{time.time() - t0:.0f}s]", flush=True)
    ix_ = {nm: j for j, nm in enumerate(names)}
    bad, maxerr, ncmp = [], 0.0, 0
    for r in rows:
        o = int(o_all[r]); dr, br = d[r], beta[r]
        ta, tb = meta.ticker_a.iloc[r], meta.ticker_b.iloc[r]
        sA, sB = dr, -dr * np.sign(br)
        trunc = lambda c: {k: v[:o] for k, v in flow[c].items()}      # NOTHING at or after C survives
        fa, fb = trunc(ta), trunc(tb)
        la, lb = lc[ta][:o], lc[tb][:o]
        cA = dr * (la[o - 1] - la[o - 61]); cB = -dr * br * (lb[o - 1] - lb[o - 61])
        if np.isfinite(cA) and np.isfinite(cB):
            pa, pb = max(cA, 0.0), max(cB, 0.0)
            wA = pa / (pa + pb) if (pa + pb) > 0 else 0.5
        else:
            wA = np.nan
        wB = 1 - wA
        exp = {}
        for W in ff.WINDOWS:
            ra, _, _ = leg_features(fa, o, sA, W); rb, _, _ = leg_features(fb, o, sB, W)
            na, nb_ = wallets_norm(fa, o, W), wallets_norm(fb, o, W)
            ra["wallets_per_musd"] = ra["wallets_per_musd"] / na if na > 0 else np.nan
            rb["wallets_per_musd"] = rb["wallets_per_musd"] / nb_ if nb_ > 0 else np.nan
            for g, qs in ff.GROUPS.items():
                for q in qs:
                    xa, xb = ra[q], rb[q]
                    bad_ = (not np.isfinite(wA)) or (wA > 0 and not np.isfinite(xa)) or (wB > 0 and not np.isfinite(xb))
                    exp[f"{g.lower().replace('-', '_')}_{q}_{W}"] = np.nan if bad_ else (wA * xa if wA > 0 else 0.0) + (wB * xb if wB > 0 else 0.0)
            # market block
            exp[f"market_btc_ret_{W}"] = dr * (lc["BTC"][:o][o - 1] - lc["BTC"][:o][o - 1 - W])
            exp[f"market_eth_ret_{W}"] = dr * (lc["ETH"][:o][o - 1] - lc["ETH"][:o][o - 1 - W])
            M = mkt[:o]
            tot = M[o - W:o]
            cur = np.nan if np.isnan(tot).any() else tot.sum()
            vals = []
            for k in range(ff.TRAIL):
                ce = o - W - 30 * k
                if ce - W < 0:
                    continue
                t_ = M[ce - W:ce]
                if len(t_) == W and not np.isnan(t_).any():
                    vals.append(t_.sum())
            med = np.median(vals) if len(vals) >= ff.MINVALID else np.nan
            exp[f"market_liq_usd_{W}"] = cur / med if (med > 0 and np.isfinite(cur)) else np.nan
        M = mkt[:o]
        if o - 28 * 1440 >= 0:
            m7, m28 = M[o - 7 * 1440:o], M[o - 28 * 1440:o]
            s7, v7, s28, v28 = np.nansum(m7), (~np.isnan(m7)).sum(), np.nansum(m28), (~np.isnan(m28)).sum()
            exp["market_liq_7d_ratio"] = (s7 / v7) / (s28 / v28) if s28 > 0 else np.nan
        else:
            exp["market_liq_7d_ratio"] = np.nan
        # breadth: every coin, past-only std of 60-minute returns at the half-hour cutoffs
        ex = nv = 0
        for c, a in lc.items():
            a = a[:o]
            cuts = o - 60 - 30 * np.arange(ff.TRAIL)                   # cutoffs ending at or before C - 60
            cuts = cuts[cuts - 61 >= 0]
            rr = a[cuts - 1] - a[cuts - 61]
            rr = rr[np.isfinite(rr)]
            now = a[o - 1] - a[o - 61]
            if len(rr) >= ff.MINVALID and np.isfinite(now):
                nv += 1
                ex += abs(now) > 2 * rr.std(ddof=1)
        exp["market_breadth_60"] = ex / nv if nv else np.nan

        def r30(c):
            a = lc[c][:o]
            cuts = o - 30 * np.arange(ff.TRAIL)
            cuts = cuts[cuts - 31 >= 0]
            return a[cuts - 1] - a[cuts - 31], len(cuts)
        bt, _ = r30("BTC")
        cc = []
        for c in (ta, tb):
            x, _ = r30(c)
            m = np.isfinite(x) & np.isfinite(bt[:len(x)])
            cc.append(np.corrcoef(x[m], bt[:len(x)][m])[0, 1] if m.sum() >= ff.MINVALID else np.nan)
        exp["market_btc_corr_7d"] = (cc[0] + cc[1]) / 2
        # compare
        for nm, v in exp.items():
            got = float(X[r, ix_[nm]])
            ncmp += 1
            if np.isnan(v) != np.isnan(got):
                bad.append((int(r), nm, v, got)); continue
            if np.isnan(v):
                continue
            err = abs(v - got)
            maxerr = max(maxerr, err)
            if err > 1e-5 + 1e-4 * abs(v):
                bad.append((int(r), nm, v, got))
    print(f"[VALID] {NROWS} rows x {len(exp)} features = {ncmp:,} comparisons; mismatches {len(bad)}; "
          f"max abs diff {maxerr:.2e}  [{time.time() - t0:.0f}s]")
    print("[VALID] every array was truncated at the row's cutoff C before any read (no minute >= C available)")
    for b_ in bad[:20]:
        print("  MISMATCH", b_)
    if bad:
        raise SystemExit("[VALID] FAILED")
    print("[VALID] PASS")
