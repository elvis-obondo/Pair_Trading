"""HL-MASTER1 G5: flow at t0, per leg, net-weighted, plus the minute-shape and the price-shape blocks. Features only.

    python -u research/dataset/master_g5.py > research/dataset/logs/master_g5.log

Cutoff o = the minute index of t0 = T + 30 min; windows [o - W, o) (minutes labelled <= T + 29). Leg x in {A, B}: push sign s_A = d, s_B = -d sign(beta); coin unit: the coin with s = d.
Any window with a missing minute (archive hole, or before the coin's first trade) is NaN; TN = taker buy + sell; ratios are NaN where TN = 0. Definitions as accepted by the reviewer (see docs/DATASET_DICTIONARY.md):
LEG, per W in {30, 60, 360, 1440}:  imb, forced_share, forced_net, backstop_ratio / adl_ratio (= (backstop_liq - adl) / TN and adl / TN: off-book over on-book, unbounded), backstop_share / adl_share (= off-book USD / (TN + off-book USD), in [0, 1]; default), open_push, close_push, open_close_ratio, top3 (proxy), wallets_raw,
  wallets_per_musd (normalised by the median of the same window quantity at the 336 half-hour cutoffs ending before the window; >= 144 valid), twap_share, volume_ratio (TN over its trailing median).
SHAPE: imb_5m_k, forced_5m_k (k = 0..11, the 12 five-minute bins of [o-60, o)); imb_30m_k, forced_30m_k (the 12 thirty-minute bins of [o-360, o), reading A) and imb_30m_pre_k, forced_30m_pre_k (the 12 bins of
  [o-420, o-60), reading B); max_abs_imb_5m, max_abs_imb_5m_bin; mins_since_forced_any (minutes since the last minute <= o-1 with push-side forced USD > 0, NaN if none in 24 h);
  mins_since_forced_spike (threshold 3 x the median of the POSITIVE push-side forced minute values over [o-7d, o), >= 20 positive minutes, within 24 h); slope_cum_imb_30/60 (OLS slope per minute of the cumulative
  s(buy - sell) / TN_W over the last 30 / 60 minutes); accel_share (push-side taker USD in the last 15 of the last 60 minutes / the 60-minute total).
NET: net(x) = wA x_A + wB x_B, cA = d dlog a, cB = -d beta dlog b over [o-60, o) (1m closes), wA = max(cA,0) / (max(cA,0) + max(cB,0)), 0.5 / 0.5 if both <= 0, NaN if a positively weighted leg is NaN;
  for the continuous columns only. PRICE SHAPE (pair level): see price_shape().
OUTPUT: research/datasets/master/work/{pair,coin}/g5_{a,b,net,shape}.parquet
"""
import os, sys, time
from multiprocessing import Pool
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
TMP = os.path.join(WORK, "g5_tmp")
WINS = (30, 60, 360, 1440)
COLS_FLOW = ["taker_buy_usd", "taker_sell_usd", "liq_forced_long_usd", "liq_forced_short_usd", "backstop_liq_usd", "adl_usd", "open_buy_usd", "open_sell_usd", "close_buy_usd",
             "close_sell_usd", "n_taker_wallets", "top3_taker_share", "twap_taker_usd"]
Q_WIN = ["imb", "forced_share", "forced_net", "backstop_ratio", "adl_ratio", "backstop_share", "adl_share", "open_push", "close_push", "open_close_ratio", "top3", "wallets_raw", "wallets_per_musd", "twap_share", "volume_ratio"]
NAMES_WIN = [f"{q}_{W}" for W in WINS for q in Q_WIN]
NAMES_SHAPE = ([f"imb_5m_{k}" for k in range(12)] + [f"forced_5m_{k}" for k in range(12)] + [f"imb_30m_{k}" for k in range(12)] + [f"forced_30m_{k}" for k in range(12)]
               + [f"imb_30m_pre_{k}" for k in range(12)] + [f"forced_30m_pre_{k}" for k in range(12)]
               + ["max_abs_imb_5m", "max_abs_imb_5m_bin", "mins_since_forced_any", "mins_since_forced_spike", "slope_cum_imb_30", "slope_cum_imb_60", "accel_share"])
NAMES_LEG = NAMES_WIN + NAMES_SHAPE
NO_NET = {"max_abs_imb_5m_bin", "mins_since_forced_any", "mins_since_forced_spike"}
PRICE_NAMES = ["ps_realized_var", "ps_efficiency", "ps_max_step", "ps_max_step_min", "ps_mins_since_big_step", "ps_drawdown", "w_a", "contrib_a", "contrib_b"]
CH = 20000


SCALE = 1e6                          # cumulative sums are kept as EXACT integers in micro-USD (a float64 cumulative sum of 1e12-1e13 loses ~1e-4 USD, which showed as shares of 1.000004 on tiny windows)


def ccum(a):
    """(exact integer cumulative sum in units of 1/SCALE with a leading 0, cumulative NaN count with a leading 0); NaN counts as 0 in the sum."""
    z = np.rint(np.nan_to_num(a, nan=0.0) * SCALE).astype(np.int64)
    cs = np.concatenate([[0], np.cumsum(z)])
    assert np.abs(cs).max() < 9e18, "cumulative sum overflows int64 at this scale"
    nc = np.concatenate([[0], np.cumsum(np.isnan(a))]).astype(np.int64)
    return cs, nc


def read_coin_raw(c):
    """Dense per-minute raw flow arrays of one coin (NaN where missing)."""
    fl = pd.read_parquet(os.path.join(ff.FLOW_DIR, f"{c}.parquet"), columns=["date"] + COLS_FLOW)
    return {k: ff.dense(fl, k) for k in COLS_FLOW}


def build_A(a):
    """Cumulative sums, shifted medians and spike thresholds from the raw arrays (pure: raw in, arrays out)."""
    A = {}
    for k in ("taker_buy_usd", "taker_sell_usd", "liq_forced_long_usd", "liq_forced_short_usd", "backstop_liq_usd", "adl_usd", "open_buy_usd", "open_sell_usd", "close_buy_usd", "close_sell_usd",
              "n_taker_wallets"):
        A[k], nc = ccum(a[k])
        if k == "taker_buy_usd":
            A["nc"] = nc
    TN = a["taker_buy_usd"] + a["taker_sell_usd"]
    top3n = np.where(TN > 0, np.nan_to_num(a["top3_taker_share"]) * TN, np.where(np.isnan(TN), np.nan, 0.0))
    A["top3n"], _ = ccum(top3n)
    A["tw"], A["ntw"] = ccum(a["twap_taker_usd"])
    A["tn_cs"], _ = ccum(TN)
    A["m_buy"], A["m_sell"], A["m_fl"], A["m_fs"] = a["taker_buy_usd"], a["taker_sell_usd"], a["liq_forced_long_usd"], a["liq_forced_short_usd"]
    norm = {}
    for W in WINS:
        wtot = cutoff(A["n_taker_wallets"], A["nc"], W)
        tntot = cutoff(A["tn_cs"], A["nc"], W)
        with np.errstate(divide="ignore", invalid="ignore"):
            q = np.where(tntot > 0, wtot / (tntot / 1e6), np.nan)
        norm[W] = (ff.trailing_median(q, W), ff.trailing_median(tntot, W))
    A["norm"] = norm
    thr = {}
    for nm, v in (("fs", a["liq_forced_short_usd"]), ("fl", a["liq_forced_long_usd"])):
        x = pd.Series(np.where(v > 0, v, np.nan))
        thr[nm] = x.rolling(10080, min_periods=20).median().to_numpy()
    A["thr"] = thr
    return A


def cutoff(cs, nc, W):
    """The W-window total ending at every half-hour cutoff that exists in the arrays (arrays may be truncated); NaN where incomplete."""
    N = len(cs) - 1
    o = ff.CUT_PHASE + 30 * np.arange((N - ff.CUT_PHASE) // 30 + 1)
    o = o[o <= N]
    out = np.full(len(o), np.nan)
    good = o - W >= 0
    oo = o[good]
    ok = (nc[oo] - nc[oo - W]) == 0
    v = (cs[oo] - cs[oo - W]) / SCALE
    out[np.flatnonzero(good)[ok]] = v[ok]
    return out


def load_coin(c):
    return build_A(read_coin_raw(c))


def wsum(cs, o, W):
    return (cs[o] - cs[o - W]) / SCALE


def leg_block(A, o, s):
    """All leg columns for cutoffs o (int array, n) and push signs s (+1 / -1, n). Returns {name: float32 array}."""
    n = len(o)
    out = {}
    j = (o - ff.CUT_PHASE) // 30
    nc = A["nc"]
    for W in WINS:
        ok = (o - W >= 0)
        oo = np.where(ok, o, W)
        okm = ok & ((nc[oo] - nc[oo - W]) == 0)
        B, S = wsum(A["taker_buy_usd"], oo, W), wsum(A["taker_sell_usd"], oo, W)
        TN = B + S
        fl, fs = wsum(A["liq_forced_long_usd"], oo, W), wsum(A["liq_forced_short_usd"], oo, W)
        bk, ad = wsum(A["backstop_liq_usd"], oo, W), wsum(A["adl_usd"], oo, W)
        ob, osl, cb, cs = (wsum(A[k], oo, W) for k in ("open_buy_usd", "open_sell_usd", "close_buy_usd", "close_sell_usd"))
        wal, t3 = wsum(A["n_taker_wallets"], oo, W), wsum(A["top3n"], oo, W)
        twok = ok & ((A["ntw"][oo] - A["ntw"][oo - W]) == 0)
        tw = wsum(A["tw"], oo, W)
        pos = s > 0
        with np.errstate(divide="ignore", invalid="ignore"):
            g = lambda x: np.where(okm & (TN > 0), x / TN, np.nan)
            op = np.where(pos, ob, osl); cl = np.where(pos, cb, cs)
            out[f"imb_{W}"] = g(s * (B - S))
            out[f"forced_share_{W}"] = g(np.where(pos, fs, fl))
            out[f"forced_net_{W}"] = g(s * (fs - fl))
            out[f"backstop_ratio_{W}"] = g(bk - ad)                      # off-book USD over on-book taker notional: >= 0, unbounded (build 3's definition)
            out[f"adl_ratio_{W}"] = g(ad)
            gsh = lambda x: np.where(okm & ((TN + x) > 0), x / (TN + x), np.nan)        # planner's default: off-book USD / (on-book taker notional + off-book USD), in [0, 1]
            out[f"backstop_share_{W}"] = gsh(bk - ad)
            out[f"adl_share_{W}"] = gsh(ad)
            out[f"open_push_{W}"] = g(op)
            out[f"close_push_{W}"] = g(cl)
            out[f"open_close_ratio_{W}"] = np.where(okm & (TN > 0) & ((op + cl) > 0), op / (op + cl), np.nan)
            out[f"top3_{W}"] = g(t3)
            wraw = np.where(okm & (TN > 0), wal / (TN / 1e6), np.nan)
            out[f"wallets_raw_{W}"] = wraw
            nm = A["norm"][W][0][j]
            out[f"wallets_per_musd_{W}"] = np.where(nm > 0, wraw / nm, np.nan)
            out[f"twap_share_{W}"] = np.where(twok & okm & (TN > 0), tw / TN, np.nan)
            nt = A["norm"][W][1][j]
            out[f"volume_ratio_{W}"] = np.where(okm & (nt > 0), TN / nt, np.nan)
    out.update(shape_block(A, o, s))
    return {k: v.astype(np.float32) for k, v in out.items()}


def bins(A, o, s, start, width, nb):
    """imb and push-side forced share for nb bins of `width` minutes starting at o - start (NaN if any minute of the whole span is missing)."""
    nc = A["nc"]
    ok = (o - start >= 0)
    oo = np.where(ok, o, start)
    span_ok = ok & ((nc[oo - start + width * nb] - nc[oo - start]) == 0)
    edges = (oo - start)[:, None] + width * np.arange(nb + 1)[None, :]
    def e(cs):
        return cs[edges]
    Bc, Sc, Fl, Fs = e(A["taker_buy_usd"]), e(A["taker_sell_usd"]), e(A["liq_forced_long_usd"]), e(A["liq_forced_short_usd"])
    B, S = np.diff(Bc, axis=1) / SCALE, np.diff(Sc, axis=1) / SCALE
    FL, FS = np.diff(Fl, axis=1) / SCALE, np.diff(Fs, axis=1) / SCALE
    TN = B + S
    ss = s[:, None]
    with np.errstate(divide="ignore", invalid="ignore"):
        imb = np.where(span_ok[:, None] & (TN > 0), ss * (B - S) / TN, np.nan)
        frc = np.where(span_ok[:, None] & (TN > 0), np.where(ss > 0, FS, FL) / TN, np.nan)
    return imb, frc, span_ok, B, S


def shape_block(A, o, s):
    n = len(o)
    out = {}
    imb5, frc5, ok5, B5, S5 = bins(A, o, s, 60, 5, 12)
    for k in range(12):
        out[f"imb_5m_{k}"], out[f"forced_5m_{k}"] = imb5[:, k], frc5[:, k]
    imb30, frc30, _, _, _ = bins(A, o, s, 360, 30, 12)
    for k in range(12):
        out[f"imb_30m_{k}"], out[f"forced_30m_{k}"] = imb30[:, k], frc30[:, k]
    imbp, frcp, _, _, _ = bins(A, o, s, 420, 30, 12)                       # reading B: the 12 bins of 30 min covering [o-420, o-60)
    for k in range(12):
        out[f"imb_30m_pre_{k}"], out[f"forced_30m_pre_{k}"] = imbp[:, k], frcp[:, k]
    allnan = ~np.isfinite(imb5).any(1)
    am = np.nanargmax(np.where(np.isfinite(imb5), np.abs(imb5), -1.0), axis=1)
    out["max_abs_imb_5m"] = np.where(allnan, np.nan, imb5[np.arange(n), am])
    out["max_abs_imb_5m_bin"] = np.where(allnan, np.nan, am.astype(float))
    # push-side forced minute series for the last 24 hours, spike searches
    ok = o - 1440 >= 0
    oo = np.where(ok, o, 1440)
    idx = oo[:, None] - 1440 + np.arange(1440)[None, :]
    pos = (s > 0)[:, None]
    fv = np.where(pos, A["m_fs"][idx], A["m_fl"][idx])                       # (n, 1440) minute values, last column = minute o - 1
    anyf = np.where(np.isfinite(fv), fv > 0, False)
    # minutes since the last forced minute: position from the end (0 = the minute labelled o - 1)
    rev = anyf[:, ::-1]
    has = rev.any(1)
    out["mins_since_forced_any"] = np.where(ok & has, np.argmax(rev, axis=1).astype(float), np.nan)
    th = 3.0 * np.where(s > 0, A["thr"]["fs"][oo - 1], A["thr"]["fl"][oo - 1])
    sp = np.where(np.isfinite(fv), fv > th[:, None], False) & np.isfinite(th)[:, None]
    rev = sp[:, ::-1]
    out["mins_since_forced_spike"] = np.where(ok & rev.any(1), np.argmax(rev, axis=1).astype(float), np.nan)
    # slope of the cumulative push-signed imbalance and the acceleration share
    for Wn in (30, 60):
        ix = oo[:, None] - Wn + np.arange(Wn)[None, :]
        d = s[:, None] * (A["m_buy"][ix] - A["m_sell"][ix])
        tn = np.nansum(A["m_buy"][ix] + A["m_sell"][ix], axis=1)
        full = np.isfinite(d).all(1) & ok
        c = np.cumsum(np.where(np.isfinite(d), d, 0.0), axis=1)
        x = np.arange(1, Wn + 1) - (Wn + 1) / 2.0
        with np.errstate(divide="ignore", invalid="ignore"):
            out[f"slope_cum_imb_{Wn}"] = np.where(full & (tn > 0), (c * x[None, :]).sum(1) / (x * x).sum() / tn, np.nan)
    ix = oo[:, None] - 60 + np.arange(60)[None, :]
    pushv = np.where(pos, A["m_buy"][ix], A["m_sell"][ix])
    full = np.isfinite(pushv).all(1) & ok
    tot = pushv.sum(1)
    with np.errstate(divide="ignore", invalid="ignore"):
        out["accel_share"] = np.where(full & (tot > 0), pushv[:, -15:].sum(1) / tot, np.nan)
    return out


def coin_job(args):
    c, rows = args                                       # rows: dict key -> (event index array, o array, s array)
    A = load_coin(c)
    res = {}
    for key, (ix, o, s) in rows.items():
        mats = np.empty((len(ix), len(NAMES_LEG)), np.float32)
        for a in range(0, len(ix), CH):
            blk = leg_block(A, o[a:a + CH], s[a:a + CH])
            for q, nm in enumerate(NAMES_LEG):
                mats[a:a + CH, q] = blk[nm]
        res[key] = (ix, mats)
    return c, res


def price_shape(la, lb, beta, alpha, mu, sg, s_z, o, d, benchmark=None):
    """Pair-level price shape of the folded 1-minute spread path over [o-61, o-1] (60 steps) and the weights. la, lb: (n, 1501) 1-minute log closes ending at minute o-1 (column 1500 = o-1)."""
    P = (la - beta[:, None] * lb - alpha[:, None] - mu[:, None]) / sg[:, None]
    P = P * s_z[:, None]                                                          # folded: the dislocation direction is positive
    steps = np.diff(P, axis=1)                                                    # (n, 1500); step j ends at minute o - 1500 + j
    last = steps[:, -60:]
    path = P[:, -61:]
    ok = np.isfinite(path).all(1)
    out = {}
    with np.errstate(invalid="ignore", divide="ignore"):
        out["ps_realized_var"] = np.where(ok, (last ** 2).sum(1), np.nan)
        out["ps_efficiency"] = np.where(ok & ((np.abs(last)).sum(1) > 0), np.abs(path[:, -1] - path[:, 0]) / np.abs(last).sum(1), np.nan)
        out["ps_max_step"] = np.where(ok, np.abs(last).max(1), np.nan)
        out["ps_max_step_min"] = np.where(ok, np.abs(last).argmax(1).astype(float), np.nan)
        hist = steps[:, :-60]                                                     # the 24 h of steps ENDING AT o - 60 (before the 60-minute window)
        sd = np.nanstd(hist[:, -1440:], axis=1, ddof=1)
        big = np.abs(last) >= 3 * sd[:, None]
        rev = big[:, ::-1]
        out["ps_mins_since_big_step"] = np.where(ok & np.isfinite(sd) & rev.any(1), np.argmax(rev, axis=1).astype(float), np.nan)
        out["ps_drawdown"] = np.where(ok, np.maximum.accumulate(path, axis=1).max(1) - path[:, -1], np.nan)
    return out


