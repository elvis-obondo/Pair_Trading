"""HL-MASTER1 G9a: market regime at t0 that needs neither open interest nor funding. One row per 30-minute cutoff bar, then joined to the events of both units.

    python -u research/dataset/master_g9a.py > research/dataset/logs/master_g9a.log

Cutoff j: o_j = flowfeat.CUT_PHASE + 30 j is the minute index of t0 = T + 30 min; every window is [o - W, o) (minutes labelled <= T + 29), so the price at t0 is the 1m close labelled T + 29 = lc[o - 1].
Benchmarks: BTC, ETH (1m log closes) and the equal-weight index of ALL live coins (ev_market.npz: S1m / n1m, n1m >= 30 coins; the index return at minute k = S1m[k] / n1m[k]).
COLUMNS (identical for every event of a bar):
  ret_{btc,eth,idx}_{1h,6h,24h,7d}     log return over 60 / 360 / 1,440 / 10,080 minutes (BTC, ETH: close at o-1 minus close at o-1-W; index: sum of 1m index returns over [o-W, o)); NaN if any end/minute missing
  rv_{btc,eth,idx}_{1h,24h,7d}         sd (ddof 1) of 1-minute log returns over the window, NaN minutes excluded, NaN if fewer than 70% usable
  volratio_{btc,eth,idx}               rv_24h / rv_7d
  breadth_extreme_1h                   flowfeat's market_breadth_60: share of live coins with |60-minute return| > 2 x the sd of the coin's own 60-minute returns at the half-hour cutoffs over the
                                       trailing 7 days (336 cutoffs, >= 144 samples, shifted by the 2 cutoffs of the window); recomputed here from the coins' cutoff closes
  share_up_24h, xs_std_1h, n_live_coins   over live coins (finite close now and 24 h / 1 h ago): share with a positive 24 h return; cross-sectional sd of 1-hour returns; count of live coins
  coherence_7d                         mean over coins of the trailing 336-cutoff correlation (>= 144 valid) of the coin's 30m returns with the index's 30m returns
  mkt_liq_1h, mkt_liq_24h              market-wide forced long + short USD over 60 / 1,440 minutes / the median of the same window at cutoffs over the trailing 7 days (build 4's trailing_median; NaN if < 144 valid)
  mkt_liq_ratio_7d_28d                 build 3's market_liq_7d_ratio: mean per VALID minute over [o-7d, o) / mean per valid minute over [o-28d, o) (hole minutes do not depress a window)
  adl_usd_24h, mkt_backstop_usd_24h    market-wide ADL USD (adl_usd) and backstop-absorbed USD (backstop_liq_usd - adl_usd, per coin-minute) over 1,440 minutes (NaN if the window has a hole minute)
  mkt_taker_1h_rel                     market-wide taker notional over 60 minutes / its trailing 7-day median
  SEGMENT-WISE VARIANT (suffix _seg; planner 2026-10-25; default for models later; the strict columns are kept): ret_idx_{1h,6h,24h,7d}_seg = the sum of the equal-weight index's 30-minute returns (all live coins, >= 30 per bar) over the
  last 2 / 12 / 48 / 336 half-hour bars (NaN only if one of them is missing); rv_idx_{24h,7d}_seg = sd (ddof 1) of the 30-minute returns over 48 / 336 bars (>= 70% usable); volratio_idx_seg; rank90_idx_rv_24h_seg, rank90_idx_abs_ret_7d_seg.
  rank90_idx_rv_24h, rank90_idx_abs_ret_7d, rank90_mkt_liq_24h   share of the previous 4,320 half-hour samples (90 days) strictly below the current value (the raw 24 h liquidation USD for the last);
                                       NaN with fewer than 3,000 usable samples (so for the first 90 days)
EVENT-LEVEL (unit-specific counts, not market quantities): n_other_triggers_same_bar = events of the same unit on the same 30m bar excluding itself; n_triggers_prev_24h = events of the unit with T' in [T-24h, T).
compute(raw, nmax) is a pure function of the raw arrays; with nmax set, arrays are cut to length nmax and only cutoffs with o <= nmax are produced (the poison test).
OUTPUT: research/datasets/master/work/g9a_bar_table.parquet and {pair,coin}/g9a.parquet
"""
import os, sys, time
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "research"))
sys.path.insert(0, os.path.join(ROOT, "research", "dislocation_model"))
import paths
import flowfeat as ff
import evmarket as em

WORK = os.path.join(paths.DATASETS, "master", "work")
WIN = {"1h": 60, "6h": 360, "24h": 1440, "7d": 10080}


def load_raw():
    coins = sorted(f[:-8] for f in os.listdir(ff.FLOW_DIR) if f.endswith(".parquet"))
    mk = np.load(em.OUT)
    lc = {c: em.load_lc(c) for c in coins}
    adl = np.zeros(ff.N); bk = np.zeros(ff.N); tk = np.zeros(ff.N)
    for c in coins:
        fl = pd.read_parquet(os.path.join(ff.FLOW_DIR, f"{c}.parquet"), columns=["date", "backstop_liq_usd", "adl_usd", "taker_buy_usd", "taker_sell_usd"])
        a, b = np.nan_to_num(ff.dense(fl, "adl_usd")), np.nan_to_num(ff.dense(fl, "backstop_liq_usd"))
        adl += a; bk += b - a
        tk += np.nan_to_num(ff.dense(fl, "taker_buy_usd")) + np.nan_to_num(ff.dense(fl, "taker_sell_usd"))
    holes = pd.read_parquet(ff.HOLES)["minute"]
    hix = ff.minute_index(holes.dt.tz_localize(None))
    hole = np.zeros(ff.N, bool)
    hole[hix[(hix >= 0) & (hix < ff.N)]] = True
    # the segment-wise 30m index (planner 2026-10-25, the _seg columns): equal-weight mean 30m return of ALL live coins at the panel bars (>= 30 coins), placed on the cutoff grid
    import coinevents as ce
    panel, pidx, V, cols = ce.load_panel()
    Sx, nx, _ = ce.index_returns(V)
    r30 = np.where(nx >= 30, Sx / np.maximum(nx, 1), np.nan)
    o_bar = ff.minute_index(pd.DatetimeIndex(pidx) + pd.Timedelta(minutes=30))
    j_bar = (o_bar - ff.CUT_PHASE) // 30
    assert ((o_bar - ff.CUT_PHASE) % 30 == 0).all()
    idx30 = np.full(ff.NJ, np.nan)
    ok = (j_bar >= 0) & (j_bar < ff.NJ)
    idx30[j_bar[ok]] = r30[ok]
    return dict(coins=coins, lc=lc, S1m=mk["S1m"], n1m=mk["n1m"].astype(np.int64), mkt_liq=mk["mkt_liq"], adl=adl, bk=bk, tk=tk, hole=hole, idx30=idx30)


def cutoff(cs, nc, W, o):
    """Window total over [o - W, o) at the cutoffs o (cum_nan arrays), NaN where the window is incomplete (flowfeat.cutoff_series on an explicit cutoff list, so truncated arrays work)."""
    ok = o - W >= 0
    oo = np.where(ok, o, W)
    good = ok & ((nc[oo] - nc[oo - W]) == 0)
    return np.where(good, cs[oo] - cs[oo - W], np.nan)


def sd_cutoff(r, o, W, frac=0.7):
    """sd (ddof 1) of the finite values of r over [o - W, o) at every cutoff o; NaN if fewer than frac x W usable."""
    f = np.isfinite(r)
    z = np.where(f, r, 0.0)
    cs, cs2, cn = (np.concatenate([[0.0], np.cumsum(x)]) for x in (z, z * z, f.astype(float)))
    ok = o - W >= 0
    oo = np.where(ok, o, W)
    n = cn[oo] - cn[oo - W]
    s1, s2 = cs[oo] - cs[oo - W], cs2[oo] - cs2[oo - W]
    with np.errstate(invalid="ignore", divide="ignore"):
        v = (s2 - s1 * s1 / n) / (n - 1)
    return np.where(ok & (n >= frac * W), np.sqrt(np.maximum(v, 0)), np.nan)


def rank90(x, n=4320, need=3000):
    """Share of the previous n samples strictly below x[j] (NaN unless >= need finite)."""
    out = np.full(len(x), np.nan)
    if len(x) <= n:
        return out
    w = np.lib.stride_tricks.sliding_window_view(x, n)[:-1]                       # w[i] = x[i : i + n], the previous n for j = i + n
    cur = x[n:]
    fin = np.isfinite(w)
    cnt = fin.sum(1)
    below = (np.where(fin, w, np.inf) < cur[:, None]).sum(1)
    out[n:] = np.where((cnt >= need) & np.isfinite(cur), below / np.maximum(cnt, 1), np.nan)
    return out


def compute(raw, nmax=None):
    N = ff.N if nmax is None else nmax
    cut = lambda a: a[:N] if a.ndim == 1 else a[:, :N]
    NJ = (N - ff.CUT_PHASE) // 30 + 1
    o = ff.CUT_PHASE + 30 * np.arange(NJ)
    o = o[o <= N]
    NJ = len(o)
    out = {}
    coins = raw["coins"]
    lc = {c: cut(raw["lc"][c]) for c in coins}
    hole = cut(raw["hole"])
    # ---- 1-minute returns
    r1 = {c: np.concatenate([[np.nan], np.diff(lc[c])]) for c in ("BTC", "ETH")}
    n1m = cut(raw["n1m"])
    idx_r = np.where(n1m >= 30, cut(raw["S1m"]) / np.maximum(n1m, 1), np.nan)
    r1["idx"] = idx_r
    cs_r = {}
    for k, r in r1.items():
        cs_r[k] = ff.cum_nan(r)
    for k in ("btc", "eth", "idx"):
        key = k.upper() if k != "idx" else "idx"
        r = r1[key]
        cs, nc = cs_r[key]
        for lab, W in WIN.items():
            tot = cutoff(cs, nc, W, o)
            if k == "idx":
                out[f"ret_{k}_{lab}"] = tot
            else:
                a = lc[key.upper()]
                ok = o - 1 - W >= 0
                out[f"ret_{k}_{lab}"] = np.where(ok, a[np.clip(o - 1, 0, None)] - a[np.clip(o - 1 - W, 0, None)], np.nan)
        for lab in ("1h", "24h", "7d"):
            out[f"rv_{k}_{lab}"] = sd_cutoff(r, o, WIN[lab])
        out[f"volratio_{k}"] = out[f"rv_{k}_24h"] / out[f"rv_{k}_7d"]
    # ---- the cutoff-grid close matrix: breadth, share up, dispersion, coherence
    lcj = np.column_stack([lc[c][o - 1] for c in coins])                         # (NJ, coins)
    exceed = np.zeros(NJ); nvalid = np.zeros(NJ)
    idx30 = cutoff(*cs_r["idx"], 30, o)
    coh_sum = np.zeros(NJ); coh_n = np.zeros(NJ)
    pidx = pd.Series(idx30)
    for ci, c in enumerate(coins):
        x = lcj[:, ci]
        r60 = np.full(NJ, np.nan); r60[2:] = x[2:] - x[:-2]
        sd = pd.Series(r60).rolling(ff.TRAIL, min_periods=ff.MINVALID).std().to_numpy()
        sdp = np.full(NJ, np.nan); sdp[2:] = sd[:-2]
        v = np.isfinite(r60) & np.isfinite(sdp)
        exceed += np.where(v, np.abs(r60) > 2 * sdp, False); nvalid += v
        r30 = np.full(NJ, np.nan); r30[1:] = x[1:] - x[:-1]
        cr = pd.Series(r30).rolling(ff.TRAIL, min_periods=ff.MINVALID).corr(pidx).to_numpy()
        f = np.isfinite(cr)
        coh_sum += np.where(f, cr, 0.0); coh_n += f
    out["breadth_extreme_1h"] = np.where(nvalid > 0, exceed / np.maximum(nvalid, 1), np.nan)
    r1h = np.full(lcj.shape, np.nan); r1h[2:] = lcj[2:] - lcj[:-2]
    r24 = np.full(lcj.shape, np.nan); r24[48:] = lcj[48:] - lcj[:-48]
    live = np.isfinite(r24)
    with np.errstate(invalid="ignore", divide="ignore"):
        out["share_up_24h"] = np.where(live.sum(1) > 0, (np.where(live, r24, 0) > 0).sum(1) / np.maximum(live.sum(1), 1), np.nan)
        out["xs_std_1h"] = np.nanstd(r1h, axis=1, ddof=1)
    out["n_live_coins"] = live.sum(1).astype(float)
    out["coherence_7d"] = np.where(coh_n > 0, coh_sum / np.maximum(coh_n, 1), np.nan)
    # ---- forced liquidations, ADL, backstop, taker
    mkt = np.where(hole, np.nan, cut(raw["mkt_liq"]))
    mcs, mnc = ff.cum_nan(mkt)
    for lab, W in (("1h", 60), ("24h", 1440)):
        ser = cutoff(mcs, mnc, W, o)
        med = ff.trailing_median(ser, W)[:NJ]
        out[f"mkt_liq_{lab}"] = np.where(med > 0, ser / med, np.nan)
        if lab == "24h":
            ser24 = ser
    D7, D28 = 7 * 1440, 28 * 1440
    ok28 = o - D28 >= 0
    s7 = np.where(o - D7 >= 0, mcs[o] - mcs[np.maximum(o - D7, 0)], np.nan)
    s28 = np.where(ok28, mcs[o] - mcs[np.maximum(o - D28, 0)], np.nan)
    v7 = D7 - (mnc[o] - mnc[np.maximum(o - D7, 0)]); v28 = D28 - (mnc[o] - mnc[np.maximum(o - D28, 0)])
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = (s7 / v7) / (s28 / v28)
    out["mkt_liq_ratio_7d_28d"] = np.where(ok28 & (s28 > 0) & np.isfinite(ratio), ratio, np.nan)
    for nm, key in (("adl_usd_24h", "adl"), ("mkt_backstop_usd_24h", "bk")):
        a = np.where(hole, np.nan, cut(raw[key]))
        cs, nc = ff.cum_nan(a)
        out[nm] = cutoff(cs, nc, 1440, o)
    tk = np.where(hole, np.nan, cut(raw["tk"]))
    cs, nc = ff.cum_nan(tk)
    ser = cutoff(cs, nc, 60, o)
    med = ff.trailing_median(ser, 60)[:NJ]
    out["mkt_taker_1h_rel"] = np.where(med > 0, ser / med, np.nan)
    # ---- the segment-wise variant (_seg): returns and volatility from the 30-minute index series (NaN only where a 30m return in the window is missing), same rank rule
    r30 = raw["idx30"][:NJ]
    cs30, nc30 = ff.cum_nan(r30)
    jj = np.arange(NJ)
    for lab, k in (("1h", 2), ("6h", 12), ("24h", 48), ("7d", 336)):
        ok = jj + 1 - k >= 0
        a = np.clip(jj + 1 - k, 0, None)
        out[f"ret_idx_{lab}_seg"] = np.where(ok & ((nc30[jj + 1] - nc30[a]) == 0), cs30[jj + 1] - cs30[a], np.nan)
    for lab, k in (("24h", 48), ("7d", 336)):
        f = np.isfinite(r30)
        z = np.where(f, r30, 0.0)
        c1, c2, cn = (np.concatenate([[0.0], np.cumsum(x)]) for x in (z, z * z, f.astype(float)))
        ok = jj + 1 - k >= 0
        a = np.clip(jj + 1 - k, 0, None)
        n_ = cn[jj + 1] - cn[a]
        with np.errstate(invalid="ignore", divide="ignore"):
            v = ((c2[jj + 1] - c2[a]) - (c1[jj + 1] - c1[a]) ** 2 / n_) / (n_ - 1)
        out[f"rv_idx_{lab}_seg"] = np.where(ok & (n_ >= 0.7 * k), np.sqrt(np.maximum(v, 0)), np.nan)
    out["volratio_idx_seg"] = out["rv_idx_24h_seg"] / out["rv_idx_7d_seg"]
    out["rank90_idx_rv_24h_seg"] = rank90(out["rv_idx_24h_seg"])
    out["rank90_idx_abs_ret_7d_seg"] = rank90(np.abs(out["ret_idx_7d_seg"]))
    out["rank90_idx_rv_24h"] = rank90(out["rv_idx_24h"])
    out["rank90_idx_abs_ret_7d"] = rank90(np.abs(out["ret_idx_7d"]))
    out["rank90_mkt_liq_24h"] = rank90(ser24)
    T = pd.DataFrame(out)
    T.insert(0, "cutoff_minute", o)
    return T


def main():
    t0 = time.time()
    raw = load_raw()
    print(f"[G9a] raw loaded: {len(raw['coins'])} coins  [{time.time() - t0:.0f}s]", flush=True)
    T = compute(raw)
    mk = np.load(em.OUT)
    jgrid = ff.CUT_PHASE + 30 * np.arange(ff.NJ)
    d = np.nanmax(np.abs(T.breadth_extreme_1h.to_numpy() - mk["breadth_j"][:len(T)]))
    print(f"[G9a] bar table {len(T):,} cutoffs x {len(T.columns) - 1} columns  [{time.time() - t0:.0f}s]; breadth recomputed vs ev_market.npz breadth_j: max |diff| {d:.2e}")
    assert d < 1e-12, "breadth_extreme_1h differs from the build 3/4 market breadth"
    T.to_parquet(os.path.join(WORK, "g9a_bar_table.parquet"), index=False)
    for c in T.columns[1:]:
        v = T[c].to_numpy(float)
        f = np.isfinite(v)
        print(f"  {c:<26} NaN {100 * (~f).mean():6.2f}%  median {np.median(v[f]) if f.any() else np.nan:+.4g}  p5 {np.percentile(v[f], 5) if f.any() else np.nan:+.4g}  p95 {np.percentile(v[f], 95) if f.any() else np.nan:+.4g}")
    for u in ("pair", "coin"):
        E = pd.read_parquet(os.path.join(WORK, u, "events.parquet"), columns=["event_id", "entry_time"])
        t = pd.to_datetime(E.entry_time)
        o = ff.minute_index(t + pd.Timedelta(minutes=30))
        assert ((o - ff.CUT_PHASE) % 30 == 0).all()
        j = (o - ff.CUT_PHASE) // 30
        G = T.iloc[j].drop(columns=["cutoff_minute"]).reset_index(drop=True)
        G.insert(0, "event_id", E.event_id.to_numpy())
        Ts = np.sort(t.to_numpy())
        cnt_bar = t.groupby(t).transform("size").to_numpy()
        G["n_other_triggers_same_bar"] = (cnt_bar - 1).astype(np.float32)
        G["n_triggers_prev_24h"] = (np.searchsorted(Ts, t.to_numpy(), side="left") - np.searchsorted(Ts, (t - pd.Timedelta(hours=24)).to_numpy(), side="left")).astype(np.float32)
        for c in G.columns[1:]:
            G[c] = G[c].astype(np.float32)
        G.to_parquet(os.path.join(WORK, u, "g9a.parquet"), index=False)
        print(f"[G9a {u}] {len(G):,} rows x {len(G.columns) - 1} columns; NaN share by month of rank90_idx_rv_24h / coherence_7d / mkt_liq_24h:")
        m = t.dt.to_period("M")
        print(G.assign(m=m.values).groupby("m")[["rank90_idx_rv_24h", "coherence_7d", "mkt_liq_24h", "ret_idx_7d"]].agg(lambda s: s.isna().mean()).round(4).to_string())
    print(f"  [{time.time() - t0:.0f}s]")


if __name__ == "__main__":
    main()
