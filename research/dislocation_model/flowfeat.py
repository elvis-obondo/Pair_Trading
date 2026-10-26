"""HL-FLOW1 Part 2: the flow-feature matrix. Matrix only: no target, no model.

    python -u research/dislocation_model/flowfeat.py --stage build
    python -u research/dislocation_model/flowfeat.py --stage validate

Output research/datasets/flowfeat.npz (X float32, names, groups) and
flowfeat_legs.npz (leg-level values, NOT model inputs), both joined to
disloc_meta.parquet BY ROW POSITION (60,004 rows). Never regenerates the dislocation set.

CUTOFF. The 30-minute bar labelled T closes at C = T + 30 min. A feature for that
dislocation reads only flow minutes with label < C. A window of W minutes is the
minutes [C - W, C). The builder reads per-minute flow files through cumulative sums
indexed by minute offset, and asserts that no window ends after C.

NOTATION. Leg A = ticker_a, leg B = ticker_b, d = sign(z_at_entry), beta = meta.beta.
The spread a - beta*b - alpha rises when A rises or when B moves by -sign(beta).
Push sign of a leg: sA = d, sB = -d*sign(beta). s > 0 means the leg's BUYING pushed the
spread the way it dislocated. Contribution of each leg to the spread's move over the
previous 60 minutes (1-minute closes, same cutoff): cA = d*dlog(a),
cB = -d*beta*dlog(b); wA = max(cA,0)/(max(cA,0)+max(cB,0)), wB = 1 - wA; both <= 0 ->
0.5 / 0.5. net(x) = wA*x_A + wB*x_B (a NaN leg value with weight > 0 makes the net NaN;
a leg with weight 0 does not).

LEG QUANTITIES, per window W in {30, 60}, from the coin's taker flow in [C - W, C):
  TN = taker_buy_usd + taker_sell_usd
  forced_share  = (liq_forced_short_usd if s > 0 else liq_forced_long_usd) / TN
  backstop_share = backstop_liq_usd / TN        adl_share = adl_usd / TN
  open_push = (open_buy_usd if s > 0 else open_sell_usd) / TN
  close_push = (close_buy_usd if s > 0 else close_sell_usd) / TN
  open_close_ratio = open_push / (open_push + close_push)   (NaN if both 0)
  top3 = sum(per-minute top3 notional) / TN   [PROXY: notional-weighted mean of the per-minute
        top-3 taker share, not a window-level concentration]
  wallets_per_musd = sum(per-minute n_taker_wallets) / (TN / 1e6), then divided by its
        trailing 7-day median [PROXY: per-minute distinct wallets summed over the window]
  twap_share = twap_taker_usd / TN   (NaN before 2025-07-27 08:00, never 0)
A window with ANY missing minute (archive hole, or before the coin's first trade) is
NaN. TN = 0 makes the ratios NaN. Nothing is zero-filled.

NORMALISATION (past only). The shares are ratios and already scale-free; dividing them
by a trailing median (often 0) is undefined, so they are NOT normalised. The
dollar-scaled quantities are: wallets_per_musd and the market liquidation total are each
divided by the median of the same W-window quantity at the 336 half-hour cutoffs ending
at or before the window start (cutoffs C - W - 30k, k = 0..335), NaN if fewer than 144
(3 days) are valid. [Gap filled: the brief's rule names "each coin's value"; the shares
are the ratios and are exempt.]

GROUPS (fixed before any model; expected direction = reaches mu more, + / less, -):
  H1  forced_share_W (+), backstop_share_W (+), adl_share_W (+)                    6
  H2  open_push_W (-), close_push_W (+), open_close_ratio_W (-)                    6
  H3  top3_W (+), wallets_per_musd_W (-: few wallets per $M = concentrated)        4
  H3-TWAP  twap_share_W (+), tested only on rows where it exists                   2
  MARKET (two-sided)  btc_ret_W, eth_ret_W (the return over [C-W, C) times d) x2 W 4;
        btc_corr_7d (mean of A's and B's trailing 7-day correlation of 30-minute returns
        with BTC) 1; liq_usd_W (market-wide forced liquidation notional, long + short,
        over all coins in the window / its past median) x2 W 2; liq_7d_ratio (mean per
        valid minute over [C-7d, C) / over [C-28d, C)) 1; breadth_60 (share of live coins
        whose 60-minute |log return| exceeds 2 x the std of that coin's 60-minute returns
        at the half-hour cutoffs ending at or before C - 60, over 7 days; coins with fewer
        than 144 valid samples excluded) 1                                           9
  27 model inputs. Context columns, stored but NOT model inputs: lone_mover (max(wA,wB) >=
  0.8), driver_is_A (wA > wB), flag_gap, hole60.
flag_gap = either leg stale (mins_since_trade >= 30 at the trigger bar) OR the row's span
touches one of the five seam bars (2025-06-08 09:30 and 10:00, 2025-07-19 09:30,
2025-07-27 11:30, 2025-09-27 09:00; the bars where >= half the live coins have a NaN
close). Gap filled: "touching" is not defined in the brief; the span used is the bar
labels [T - 335 bars, T + 20 bars], the dislocation's fit window and outcome. Kept,
never dropped. hole60 (a hole minute in [C - 60, C)) is a separate context column.

GAP-FILLS, stated: (1) market_liq_7d_ratio is the mean per VALID minute over [C-7d, C)
divided by the same over [C-28d, C), the hole-adjusted form of the brief's "7-day total /
28-day total" (identical when there are no hole minutes); (2) the normalisation reading
above, confirmed by the planner 2026-10-15: dollar-scaled quantities (wallets_per_musd,
the market liquidation total) are divided by their trailing 7-day median, ratios are not;
the un-normalised wallets_per_musd is stored too; (3) MEMORY RULE: the brief says to read
only the event windows (<= 60 min per event). The trailing 7-day normalisers and the
market-wide block need each coin's whole history, so the builder reads one coin at a time
(~80 MB of dense minute arrays) and never the whole flow table.
"""
import argparse, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd

import paths
from adapters.hyperliquid_futures import HL_FUTURES_DIR

FLOW_DIR = os.path.join(paths.RESEARCH, "hyperliquid", "flow")
HOLES = os.path.join(paths.RESEARCH, "hyperliquid", "missing_minutes.parquet")
OUT = os.path.join(paths.DATASETS, "flowfeat.npz")
OUT_LEGS = os.path.join(paths.DATASETS, "flowfeat_legs.npz")
GRID0 = pd.Timestamp("2025-05-25 14:32")          # tz-naive UTC, the first minute of the window
GRID1 = pd.Timestamp("2026-10-13 23:59")          # the last
N = int((GRID1 - GRID0) / pd.Timedelta(minutes=1)) + 1
WINDOWS = (30, 60)
TRAIL = 336                                       # 7 days of half-hour cutoffs
MINVALID = 144                                    # 3 days
CUT_PHASE = 28                                    # cutoff offsets are 28 + 30 j (GRID0 is at :32)
NJ = (N - CUT_PHASE) // 30 + 1
STALE_MIN = 30
SEAM_BARS = [pd.Timestamp(x) for x in ("2025-06-08 09:30", "2025-06-08 10:00", "2025-07-19 09:30",
                                       "2025-07-27 11:30", "2025-09-27 09:00")]
D3_META = os.path.join(paths.RESEARCH, "hyperliquid", "logs", "build2_assemble_meta_d3.json")
CORE = ["taker_buy_usd", "taker_sell_usd", "liq_forced_long_usd", "liq_forced_short_usd", "backstop_liq_usd",
        "adl_usd", "open_buy_usd", "open_sell_usd", "close_buy_usd", "close_sell_usd", "n_taker_wallets",
        "top3_taker_share", "twap_taker_usd"]

LEG_Q = ["forced_share", "backstop_share", "adl_share", "open_push", "close_push", "open_close_ratio",
         "top3", "wallets_per_musd", "twap_share"]
GROUPS = {
    "H1": ["forced_share", "backstop_share", "adl_share"],
    "H2": ["open_push", "close_push", "open_close_ratio"],
    "H3": ["top3", "wallets_per_musd"],
    "H3-TWAP": ["twap_share"],
}
EXPECT = {"forced_share": "+", "backstop_share": "+", "adl_share": "+", "open_push": "-", "close_push": "+",
          "open_close_ratio": "-", "top3": "+", "wallets_per_musd": "-", "twap_share": "+"}


def minute_index(ts):
    return ((pd.to_datetime(ts) - GRID0) / pd.Timedelta(minutes=1)).to_numpy().astype(np.int64)


def dense(df, col):
    """Per-minute array on the window grid; NaN outside the coin's life and in holes."""
    a = np.full(N, np.nan)
    ix = minute_index(df["date"].dt.tz_localize(None) if df["date"].dt.tz is not None else df["date"])
    ok = (ix >= 0) & (ix < N)
    a[ix[ok]] = df[col].to_numpy(float)[ok]
    return a


def wsum(cs, o, W):
    """Sum of the minutes [o - W, o) from a cumulative-sum array (cs[k] = sum of minutes < k)."""
    return cs[o] - cs[o - W]


def cutoff_series(cs, nanc, W):
    """The W-window total ending at every half-hour cutoff, NaN where the window is incomplete."""
    o = CUT_PHASE + 30 * np.arange(NJ)
    good = (o - W >= 0) & (o <= N)
    out = np.full(NJ, np.nan)
    oo = o[good]
    ok = (nanc[oo] - nanc[oo - W]) == 0
    v = cs[oo] - cs[oo - W]
    out[np.flatnonzero(good)[ok]] = v[ok]
    return out


def trailing_median(series, W):
    """Median of series at cutoffs j - W/30 - k, k = 0..335; NaN if < 144 valid."""
    r = pd.Series(series).rolling(TRAIL, min_periods=MINVALID).median().to_numpy()
    sh = W // 30
    out = np.full(len(r), np.nan)
    out[sh:] = r[:-sh] if sh else r
    return out


def cum_nan(a):
    """(cumulative sum with NaN as 0, cumulative NaN count), both with a leading 0."""
    z = np.nan_to_num(a, nan=0.0)
    cs = np.concatenate([[0.0], np.cumsum(z)])
    nc = np.concatenate([[0], np.cumsum(np.isnan(a))]).astype(np.int64)
    return cs, nc


def build():
    t0 = time.time()
    meta = pd.read_parquet(paths.META)
    n = len(meta)
    d = np.sign(meta.z_at_entry.to_numpy(float)); d[d == 0] = 1.0
    beta = meta.beta.to_numpy(float)
    C = pd.to_datetime(meta.entry_time) + pd.Timedelta(minutes=30)
    o = minute_index(C)                                        # cutoff minute offset
    assert ((o - CUT_PHASE) % 30 == 0).all(), "a cutoff is not on the half-hour grid"
    jj = (o - CUT_PHASE) // 30
    assert (o <= N).all() and (o - 60 >= 0).all()
    ta, tb = meta.ticker_a.to_numpy(str), meta.ticker_b.to_numpy(str)
    sA, sB = d, -d * np.sign(beta)
    coins = sorted(set(ta) | set(tb))
    holes = pd.read_parquet(HOLES)["minute"]
    hole = np.zeros(N, bool)
    hix = minute_index(holes.dt.tz_localize(None) if holes.dt.tz is not None else holes)
    hole[hix[(hix >= 0) & (hix < N)]] = True
    import json
    nmiss = json.load(open(D3_META))["missing_minutes"]
    assert int(hole.sum()) == nmiss, f"missing_minutes.parquet has {int(hole.sum())} minutes, the d3 assemble meta says {nmiss}"
    print(f"[INFO] {n:,} rows, {len(coins)} leg coins; window minutes {N:,}; cutoffs {NJ:,}; hole minutes {int(hole.sum())}", flush=True)

    # per-leg result arrays
    L = {(leg, q, W): np.full(n, np.nan) for leg in "AB" for q in LEG_Q for W in WINDOWS}
    RAWW = {(leg, W): np.full(n, np.nan) for leg in "AB" for W in WINDOWS}    # un-normalised wallets_per_musd
    TNL = {(leg, W): np.full(n, np.nan) for leg in "AB" for W in WINDOWS}
    IMB = {(leg, W): np.full(n, np.nan) for leg in "AB" for W in WINDOWS}
    r60 = {leg: np.full(n, np.nan) for leg in "AB"}
    max_end = -1

    # the market accumulators, over ALL coins in the flow directory
    allcoins = sorted(f[:-8] for f in os.listdir(FLOW_DIR) if f.endswith(".parquet"))
    mkt_liq = np.zeros(N)
    jgrid = CUT_PHASE + 30 * np.arange(NJ)
    exceed = np.zeros(NJ); nvalid = np.zeros(NJ)
    lc_cut = {}
    for ci, c in enumerate(allcoins):
        fl = pd.read_parquet(os.path.join(FLOW_DIR, f"{c}.parquet"), columns=["date"] + CORE)
        cols = {k: dense(fl, k) for k in CORE}
        del fl
        liq = np.nan_to_num(cols["liq_forced_long_usd"], nan=0.0) + np.nan_to_num(cols["liq_forced_short_usd"], nan=0.0)
        mkt_liq += liq
        # --- 1-minute closes -> cutoff-grid log closes (breadth, returns, correlation)
        b1 = pd.read_feather(HL_FUTURES_DIR / f"{c}-1m.feather", columns=["date", "close"])
        lc = np.full(N, np.nan)
        ix = minute_index(b1["date"].dt.tz_localize(None))
        ok = (ix >= 0) & (ix < N)
        lc[ix[ok]] = np.log(b1["close"].to_numpy(float)[ok])
        del b1
        # close at cutoff C is the 1m bar labelled C - 1
        lcj = lc[jgrid - 1]
        lc_cut[c] = lcj
        r60j = np.full(NJ, np.nan); r60j[2:] = lcj[2:] - lcj[:-2]            # 60-minute return at each cutoff
        sd = pd.Series(r60j).rolling(TRAIL, min_periods=MINVALID).std().to_numpy()
        sd_past = np.full(NJ, np.nan); sd_past[2:] = sd[:-2]                  # returns ending at or before C - 60
        v = np.isfinite(r60j) & np.isfinite(sd_past)
        exceed += np.where(v, np.abs(r60j) > 2 * sd_past, False)
        nvalid += v
        # --- legs
        ra, rb = np.flatnonzero(ta == c), np.flatnonzero(tb == c)
        if len(ra) + len(rb):
            buy, sell = cols["taker_buy_usd"], cols["taker_sell_usd"]
            TN = buy + sell
            core_cs = {k: cum_nan(cols[k]) for k in CORE if k != "twap_taker_usd"}
            nanc = core_cs["taker_buy_usd"][1]
            cs_tn = cum_nan(TN)[0]
            top3n = np.where(TN > 0, np.nan_to_num(cols["top3_taker_share"], nan=0.0) * TN, np.where(np.isnan(TN), np.nan, 0.0))
            cs_t3 = cum_nan(top3n)[0]
            cs_tw, nc_tw = cum_nan(cols["twap_taker_usd"])
            # the wallets-per-$M normaliser, on the cutoff grid, per window
            norm = {}
            for W in WINDOWS:
                wtot = cutoff_series(core_cs["n_taker_wallets"][0], nanc, W)
                tntot = cutoff_series(cs_tn, nanc, W)
                with np.errstate(divide="ignore", invalid="ignore"):
                    q = np.where(tntot > 0, wtot / (tntot / 1e6), np.nan)
                norm[W] = trailing_median(q, W)
            for leg, rr, s in (("A", ra, sA), ("B", rb, sB)):
                if not len(rr):
                    continue
                oo, sg, jr = o[rr], s[rr], jj[rr]
                max_end = max(max_end, int(oo.max()))
                # 60-minute log return of this leg (1-minute closes at C and C - 60)
                r60[leg][rr] = lc[oo - 1] - lc[oo - 61]
                for W in WINDOWS:
                    okw = (core_cs["taker_buy_usd"][1][oo] - core_cs["taker_buy_usd"][1][oo - W]) == 0
                    tn = np.where(okw, wsum(cs_tn, oo, W), np.nan)
                    b_, s_ = wsum(core_cs["taker_buy_usd"][0], oo, W), wsum(core_cs["taker_sell_usd"][0], oo, W)
                    with np.errstate(divide="ignore", invalid="ignore"):
                        pos = np.where(okw & (tn > 0), 1.0, np.nan)
                        TNL[(leg, W)][rr] = tn
                        IMB[(leg, W)][rr] = pos * (b_ - s_) / tn
                        pick = lambda kpos, kneg: np.where(sg > 0, wsum(core_cs[kpos][0], oo, W), wsum(core_cs[kneg][0], oo, W))
                        L[(leg, "forced_share", W)][rr] = pos * pick("liq_forced_short_usd", "liq_forced_long_usd") / tn
                        L[(leg, "backstop_share", W)][rr] = pos * wsum(core_cs["backstop_liq_usd"][0], oo, W) / tn
                        L[(leg, "adl_share", W)][rr] = pos * wsum(core_cs["adl_usd"][0], oo, W) / tn
                        op = pos * pick("open_buy_usd", "open_sell_usd") / tn
                        cp = pos * pick("close_buy_usd", "close_sell_usd") / tn
                        L[(leg, "open_push", W)][rr], L[(leg, "close_push", W)][rr] = op, cp
                        L[(leg, "open_close_ratio", W)][rr] = np.where((op + cp) > 0, op / (op + cp), np.nan)
                        L[(leg, "top3", W)][rr] = pos * wsum(cs_t3, oo, W) / tn
                        wpm = pos * wsum(core_cs["n_taker_wallets"][0], oo, W) / (tn / 1e6)
                        RAWW[(leg, W)][rr] = wpm
                        nm = norm[W][jr]
                        L[(leg, "wallets_per_musd", W)][rr] = np.where(nm > 0, wpm / nm, np.nan)
                        tw_ok = (nc_tw[oo] - nc_tw[oo - W]) == 0
                        L[(leg, "twap_share", W)][rr] = np.where(tw_ok, pos * wsum(cs_tw, oo, W) / tn, np.nan)
        if (ci + 1) % 20 == 0:
            print(f"  coin {ci + 1}/{len(allcoins)}  [{time.time() - t0:.0f}s]", flush=True)
    assert max_end <= N, "a window ended after the grid"

    # ---- net weights
    cA = d * r60["A"]
    cB = -d * beta * r60["B"]
    pa, pb = np.maximum(cA, 0), np.maximum(cB, 0)
    with np.errstate(invalid="ignore", divide="ignore"):
        wA = np.where((pa + pb) > 0, pa / (pa + pb), 0.5)
    wA = np.where(np.isfinite(cA) & np.isfinite(cB), wA, np.nan)
    wB = 1 - wA

    def net(xa, xb):
        a = np.where(wA > 0, wA * xa, 0.0); b = np.where(wB > 0, wB * xb, 0.0)
        out = a + b
        bad = ((wA > 0) & ~np.isfinite(xa)) | ((wB > 0) & ~np.isfinite(xb)) | ~np.isfinite(wA)
        return np.where(bad, np.nan, out)

    names, cols_out, grp, expect = [], [], [], []
    for g, qs in GROUPS.items():
        for q in qs:
            for W in WINDOWS:
                names.append(f"{g.lower().replace('-', '_')}_{q}_{W}"); grp.append(g); expect.append(EXPECT[q])
                cols_out.append(net(L[("A", q, W)], L[("B", q, W)]))
    # ---- market block
    mk = {}
    hole_cs = np.concatenate([[0], np.cumsum(hole)]).astype(np.int64)
    mkt_liq = np.where(hole, np.nan, mkt_liq)
    mcs, mnc = cum_nan(mkt_liq)
    breadth = np.where(nvalid > 0, exceed / np.maximum(nvalid, 1), np.nan)
    j_ = jj
    btc, eth = lc_cut["BTC"], lc_cut["ETH"]
    for W in WINDOWS:
        k = W // 30
        mk[f"market_btc_ret_{W}"] = d * (btc[j_] - btc[j_ - k])
        mk[f"market_eth_ret_{W}"] = d * (eth[j_] - eth[j_ - k])
        ser = cutoff_series(mcs, mnc, W)
        med = trailing_median(ser, W)
        mk[f"market_liq_usd_{W}"] = np.where(med[j_] > 0, ser[j_] / med[j_], np.nan)
    # 7d / 28d regime ratio: mean per valid minute over [C-7d, C) over [C-28d, C)
    D7, D28 = 7 * 1440, 28 * 1440
    ok28 = o - D28 >= 0
    s7 = np.where(o - D7 >= 0, mcs[o] - mcs[np.maximum(o - D7, 0)], np.nan)
    s28 = np.where(ok28, mcs[o] - mcs[np.maximum(o - D28, 0)], np.nan)
    v7 = D7 - (mnc[o] - mnc[np.maximum(o - D7, 0)]); v28 = D28 - (mnc[o] - mnc[np.maximum(o - D28, 0)])
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = (s7 / v7) / (s28 / v28)
    mk["market_liq_7d_ratio"] = np.where(ok28 & (s28 > 0) & np.isfinite(ratio), ratio, np.nan)
    mk["market_breadth_60"] = breadth[j_]
    # BTC correlation of 30-minute returns, trailing 7 days, ending at the trigger bar's close
    btc30 = np.full(NJ, np.nan); btc30[1:] = lc_cut["BTC"][1:] - lc_cut["BTC"][:-1]
    corr = {}
    for c in coins:
        r30 = np.full(NJ, np.nan); r30[1:] = lc_cut[c][1:] - lc_cut[c][:-1]
        corr[c] = pd.Series(r30).rolling(TRAIL, min_periods=MINVALID).corr(pd.Series(btc30)).to_numpy()
    ca = np.array([corr[t][j] for t, j in zip(ta, j_)]); cb = np.array([corr[t][j] for t, j in zip(tb, j_)])
    mk["market_btc_corr_7d"] = (ca + cb) / 2
    order = ["market_btc_ret_30", "market_btc_ret_60", "market_eth_ret_30", "market_eth_ret_60", "market_btc_corr_7d",
             "market_liq_usd_30", "market_liq_usd_60", "market_liq_7d_ratio", "market_breadth_60"]
    for nm in order:
        names.append(nm); grp.append("MARKET"); expect.append(""); cols_out.append(mk[nm])
    X = np.column_stack(cols_out).astype(np.float32)
    # ---- context columns
    stale = (meta.mins_since_trade_a.to_numpy(float) >= STALE_MIN) | (meta.mins_since_trade_b.to_numpy(float) >= STALE_MIN)
    hole60 = (hole_cs[o] - hole_cs[o - 60]) > 0
    Tn = pd.to_datetime(meta.entry_time).to_numpy()
    lo_, hi_ = Tn - np.timedelta64(335 * 30, "m"), Tn + np.timedelta64(20 * 30, "m")
    seam = np.zeros(n, bool)
    for sb in SEAM_BARS:
        seam |= (lo_ <= np.datetime64(sb)) & (np.datetime64(sb) <= hi_)
    ctx = {"lone_mover": np.where(np.isfinite(wA), (np.maximum(wA, wB) >= 0.8).astype(float), np.nan),
           "driver_is_A": np.where(np.isfinite(wA), (wA > wB).astype(float), np.nan),
           "flag_gap": (stale | seam).astype(float), "hole60": hole60.astype(float)}
    print(f"[BUILT] X {X.shape}  [{time.time() - t0:.0f}s]")
    print(f"  stale legs {int(stale.sum()):,}; span touches a seam bar {int(seam.sum()):,}; "
          f"flag_gap {int(ctx['flag_gap'].sum()):,}; hole minute in [C-60, C) {int(hole60.sum()):,}")
    np.savez_compressed(OUT, X=X, names=np.array(names), groups=np.array(grp), expect=np.array(expect),
                        **{k: v.astype(np.float32) for k, v in ctx.items()}, wA=wA.astype(np.float32), cutoff_offset=o)
    legs = {}
    for (leg, q, W), v in L.items():
        legs[f"{leg}_{q}_{W}"] = v.astype(np.float32)
    for (leg, W), v in TNL.items():
        legs[f"{leg}_tn_{W}"] = v.astype(np.float32)
    for (leg, W), v in IMB.items():
        legs[f"{leg}_imbalance_{W}"] = v.astype(np.float32)
    for (leg, W), v in RAWW.items():
        legs[f"{leg}_wallets_per_musd_raw_{W}"] = v.astype(np.float32)
    for leg in "AB":
        legs[f"{leg}_r60"] = r60[leg].astype(np.float32)
    np.savez_compressed(OUT_LEGS, **legs)
    print(f"[WROTE] {os.path.relpath(OUT, paths.RESEARCH)}, {os.path.relpath(OUT_LEGS, paths.RESEARCH)}")
    report(names, grp, X, ctx, wA, meta)


def report(names, grp, X, ctx, wA, meta):
    print()
    print(f"FEATURES: {len(names)} model inputs in {len(set(grp))} groups; context columns lone_mover, driver_is_A, flag_gap")
    print(f"  {'feature':<34}{'group':<9}{'NaN share':>10}")
    for j, nm in enumerate(names):
        print(f"  {nm:<34}{grp[j]:<9}{100 * np.isnan(X[:, j]).mean():>9.2f}%")
    for g in dict.fromkeys(grp):
        js = [j for j in range(len(names)) if grp[j] == g]
        anyn = np.isnan(X[:, js]).any(1)
        print(f"  GROUP {g:<8} {len(js)} features; rows with any NaN {int(anyn.sum()):,} ({100 * anyn.mean():.2f}%), "
              f"all NaN {int(np.isnan(X[:, js]).all(1).sum()):,}")
    tw = [j for j in range(len(names)) if grp[j] == "H3-TWAP"]
    print(f"  TWAP exists (finite) on {int(np.isfinite(X[:, tw[0]]).sum()):,} of {len(X):,} rows (NaN before 2025-07-27 08:00)")
    print(f"  lone_mover share {np.nanmean(ctx['lone_mover']):.3f}; driver_is_A share {np.nanmean(ctx['driver_is_A']):.3f}; "
          f"weights NaN {int(np.isnan(wA).sum()):,}")
    print("  PROXY CAVEAT: h3 top3 and wallets_per_musd are proxies (per-minute top-3 share and per-minute distinct wallets "
          "aggregated over the window), not window-level concentration.")


def validate():
    import flowvalid
    flowvalid.run()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["build", "validate"], required=True)
    a = ap.parse_args()
    {"build": build, "validate": validate}[a.stage]()
