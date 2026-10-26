"""HL-MASTER1 G8 event stage: order-book state at t0 per leg, from build8_l2.py's per coin-minute tables.

    python -u research/dataset/master_g8.py   (library; master_g8_run.py runs it)

AS-OF RULE (checker 2026-10-25). t0 = T + 30 min, o = flowfeat.minute_index(t0), the minute label of the row used is o - 1 (epoch minute m0 = EM0 + o - 1): the snapshot with the minimum exchange time
in [t0 - 60 s, t0), taken at the start of that minute. Never the row labelled t0 (its first snapshot is observed at or after t0). A missing row gives NaN, nothing is carried from an older minute.
snapshot_age_s = t0 - exchange time of the snapshot used = 60 - snap_off_s.
Only half-hour cutoff rows are needed: the table keeps, per coin, the rows labelled o_j - 1 for every cutoff j (o_j = CUT_PHASE + 30 j), as a dense (NJ, ncols) array (NaN = no row / empty side).

COLUMNS per leg (prefix a_ / b_; the coin unit has leg a only), all read at the row m0 of the leg's coin:
  mid, spread_bp, snapshot_age_s, crossed, bid_d{10,25,50}, ask_d{10,25,50} (USD within the band), trunc_{bid,ask}_{10,25,50} (1 = the 20th level is inside the band: depth is a lower bound),
  imb_{10,25,50}, slip_{buy,sell}_1k (bp vs mid; NaN beyond the 20 levels), book_reach_{bid,ask}_bp (bp from mid to the 20th stored level)
  rel_{bid,ask}_d{10,25,50}   the depth divided by its median over the previous 336 half-hour cutoff rows (j-336 .. j-1; needs >= 144 finite; NaN if the median is 0)
  chg1h_X, chg6h_X            X at j minus X at j-2 / j-12 (NaN if either is missing) for X in spread_bp, bid_d10, ask_d10, imb_10, slip_buy_1k, slip_sell_1k
PAIR: a_*, b_* and d_X = a_X - b_X for the numeric columns (not mid, crossed, trunc_*, snapshot_age_s).
"""
import os, sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "research", "dislocation_model"))
import flowfeat as ff

EM0 = int(ff.GRID0.value // 10**9 // 60)               # epoch minute of grid minute 0
BASE = (["mid", "spread_bp", "snap_off_s", "crossed"] + [f"{s}_d{b}" for s in ("bid", "ask") for b in (10, 25, 50)] + [f"trunc_{s}_{b}" for s in ("bid", "ask") for b in (10, 25, 50)]
        + [f"imb_{b}" for b in (10, 25, 50)] + ["slip_buy_1k", "slip_sell_1k", "book_reach_bid_bp", "book_reach_ask_bp"])
BIX = {c: i for i, c in enumerate(BASE)}
REL = [f"{s}_d{b}" for s in ("bid", "ask") for b in (10, 25, 50)]
CHG = ["spread_bp", "bid_d10", "ask_d10", "imb_10", "slip_buy_1k", "slip_sell_1k"]
NAMES = ([c for c in BASE if c != "snap_off_s"] + ["snapshot_age_s"] + [f"rel_{c}" for c in REL] + [f"chg1h_{c}" for c in CHG] + [f"chg6h_{c}" for c in CHG])
NO_DIFF = {"mid", "crossed", "snapshot_age_s"} | {c for c in BASE if c.startswith("trunc_")}
TRAIL, MIN_TRAIL = 336, 144


def cutoff_rows(D, lag=1):
    """Rows of one coin-minute table (columns coin, minute, BASE...) that sit at a cutoff row label (minute m = EM0 + o_j - 1): returns (coin, j, values).
    lag = 1 is the rule; lag = 0 is the deliberately broken variant (the row labelled t0) that the poison test must catch."""
    o = D["minute"].to_numpy(np.int64) + lag - EM0
    ok = (o >= ff.CUT_PHASE) & ((o - ff.CUT_PHASE) % 30 == 0) & (o <= ff.N)
    D = D[ok]
    j = (o[ok] - ff.CUT_PHASE) // 30
    return D["coin"].to_numpy(), j.astype(np.int64), D[BASE].to_numpy(np.float32)


def dense_table(parts, coin):
    """(NJ, len(BASE)) float32 for one coin from the list of (coin, j, values) parts."""
    T = np.full((ff.NJ, len(BASE)), np.nan, np.float32)
    for c, j, v in parts:
        m = c == coin
        if m.any():
            T[j[m]] = v[m]
    return T


def feature_matrix(T):
    """(NJ, len(NAMES)) event-independent features of one coin at every cutoff j (a pure function of rows <= j)."""
    nj = T.shape[0]
    out = np.full((nj, len(NAMES)), np.nan, np.float32)
    ni = {n: i for i, n in enumerate(NAMES)}
    for c in BASE:
        if c != "snap_off_s":
            out[:, ni[c]] = T[:, BIX[c]]
    out[:, ni["snapshot_age_s"]] = 60.0 - T[:, BIX["snap_off_s"]]
    for c in REL:
        x = pd.Series(T[:, BIX[c]].astype(np.float64))
        med = x.shift(1).rolling(TRAIL, min_periods=MIN_TRAIL).median().to_numpy()
        with np.errstate(divide="ignore", invalid="ignore"):
            out[:, ni[f"rel_{c}"]] = np.where(med > 0, x.to_numpy() / med, np.nan)
    for c in CHG:
        x = T[:, BIX[c]].astype(np.float64)
        for tag, k in (("chg1h", 2), ("chg6h", 12)):
            y = np.full(nj, np.nan)
            y[k:] = x[k:] - x[:-k]
            out[:, ni[f"{tag}_{c}"]] = y
    return out


def gather(F, j):
    """Rows of the feature matrix at cutoff indices j."""
    return F[j]
