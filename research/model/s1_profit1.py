"""HL-PROFIT1: a $1,000 cross-margin account trading S1's live picks (brief, rewritten 2026-11-08,
docs/prompts/HL_PROFIT1_LIVE_PICKS.md). Portfolio backtest, event-driven at 1-minute resolution.
24 runs (q in {1%, 0.5%, 0.1%} x stop in {0.5, 1, 2, none} sigma x fee in {taker, maker}), each one
continuous $1,000 account over test folds 1-7. No vault (H.assert_search_only guards every load). No
refit of S1. No per-coin position cap (brief).

    python -u research/model/s1_profit1.py > research/model/logs/s1/s1_profit1.log

PICKS AND p_cal. Rule A on raw p_10h (S1-F/S1-G), rebuilt from fold*_test_predictions.csv, asserted
against s1g_report.json's g7 cutoff_table per-fold n (as S1-H does -- s1h_recalibration.compute_picks
is called directly, not reimplemented). p_cal is S1-H's isotonic 10h correction, REFIT HERE by calling
s1h_recalibration.fit_and_apply per (fold, h=10) -- the same function S1-H used. Pooled top-1% mean
p_cal is asserted against S1-H's own reported value (0.678619..., NUMBERS.md's "67.9%"), tol 1e-6.

PRICE SOURCE -- ROUND 2 OF A FINDING (2026-11-09). Round 1 reconstructed price from ctxs (asset_ctxs
mid_px) and its own cross-check caught a PERVASIVE mismatch against v1 (median ~0.16 sigma at move[0],
not a handful of outliers) -- root-caused, with the user's and planner's sign-off, to the wrong SOURCE
entirely: v1 was never built on asset_ctxs mid_px. master_labels.py reads envelope.load_1m_series,
which reads user_data/data/hyperliquid/futures/*-1m.feather -- and those files, before they were lost
from the laptop, were build2's FILLS-ARCHIVE trade-price bars (HL-BUILD2, research/hyperliquid/
build2_assemble.py), not build1's asset_ctxs mid_px bars. CONFIRMED, not assumed: every one of the 206
locally-committed *-30m.feather files sha256-matches s3://pair-trading-hl-289869684922/build2/d3/asm/
futures/*-30m.feather exactly (206/206, 0 mismatches -- build3_swap.sh's own history already said d3/
asm was the variant promoted into user_data/data/hyperliquid/futures/). On the XLM/YZY example that
broke round 1, reading d3/asm/futures/{XLM,YZY}-1m.feather directly and looking up the label exactly as
envelope.load_1m_series would reproduces P[0] == z to the full displayed precision (-2.44959261011026
vs -2.449593). This script now reads s3://pair-trading-hl-289869684922/build2/d3/asm/futures/
{COIN}-1m.feather, cached locally under research/model/logs/profit1/build2_1m_cache/ (gitignored).
Funding and impact spread are UNCHANGED -- still ctxs/fundinghist (the planner's instruction: those
were never implicated, only the price series was wrong).

RECONSTRUCTION, build2's own fields, read exactly as envelope.load_1m_series does (dense minute-
indexed log-price arrays; duplicate minutes resolve to the LAST occurrence; gaps stay NaN; nothing is
forward-filled beyond what build2's own file already contains) -- build1's off-minute/<=5-min-fill
rules do NOT apply here, since build2's own pipeline (not this script) already decided what counts as
a hole (`gap_in_bar`) versus a real no-trade minute (`mins_since_trade` > 0, close carried from the
last trade, per build2_assemble.py's own CLOSES rule). This script adds no cleaning of its own:
  - price: log(close), dense-indexed, NaN where the minute is absent from the file.
  - any_filled (ruling 1, adapted 2026-11-09): mins_since_trade > 0 AND NOT gap_in_bar -- a build2-
    carried no-trade minute. These ARE real prices for both exits and liquidation, exactly as v1's own
    labels treat them (they are not holes, and master_labels.py's own path scored them the same way).
  - a TRUE GAP (NaN close, or gap_in_bar == True, or the minute absent from the file entirely) inside a
    picked event's 601-minute window is a cross-check mismatch under the SAME hard abort as an
    outcome/gross/minutes_to_mu mismatch (ruling 2 is withdrawn as of round 1, but the underlying
    principle -- v1's own label_gap=1 events are already excluded upstream, so every picked event had a
    gap-free window in the ORIGINAL archive -- still holds; a gap here is a reconstruction difference,
    never a v1 gap). The event is never placed in `paths` (what the simulation uses).

CROSS-CHECK (checker's requirement; hard abort, not a pass-rate threshold). check_path_match
classifies EVERY picked event: "gap"/"no_data" (automatic mismatch, see above) or a comparison of
outcome_s/gross_s (every stop) and minutes_to_mu against v1's labels.parquet, by the IDENTICAL formula
master_labels.py's chunk_labels uses; a v1 NaN counts as a mismatch, never a silent pass (checker B5).
Mismatch counts are printed per fold AND per q BEFORE the abort, and every mismatch (with a `reason`
column) is written to a parquet first, so a failure still leaves a receipt.

COVERAGE (planner condition 1, REDEFINED 2026-11-09 for build2 -- the old ctxs-era "<=5 min old" wording
does not map onto a source with no fixed fill window). Per fold (test month) AND per q, the share of
pick-minutes (both legs, m=0..600, a superset of any stop's actual span) with a finite close and
gap_in_bar == False. Alongside it, a staleness breakdown from mins_since_trade over that same covered
population: the share at exactly 0 (a real trade that minute), 1-5, 6-30, and over 30 minutes since the
last trade -- showing how often an exit or a liquidation would act on a carried, not a fresh, price.
Printed and written to report.json.

PERSISTENCE (user decision 2026-11-08, standing rule: "always keep the processed copy"; planner's
point 4 on the build2 switch). The cleaned price (now from build2 d3/asm) and impact (still ctxs)
series are saved -- local parquet AND s3://pair-trading-hl-289869684922/profit1_cleaned/, with a
manifest (coins, date range, row counts, sha256 of BOTH the derived parquet and the SOURCE build2
1m feather per coin, so the exact file this run read is on record, not just its own output) -- then
RELOADED from the just-written local files before anything else reads them (save_cleaned_series_local),
AND asserts the reload equals the in-memory build (checker M9): the engine runs on the persisted,
proven-equal copy. The S3 push itself (sync_cleaned_series_to_s3) happens only AFTER the v1 cross-check
passes (checker M10), so a reconstruction that disagreed with the archive never sits in
profit1_cleaned/ looking like a good processed copy.

FUNDING. The hourly, REALIZED rate from the public fundingHistory API (research/dataset/master_g7.py's
source; s3://pair-trading-hl-289869684922/fundinghist/{COIN}.parquet, "the row stamped at hour H
reports the hour that ENDED at H"), applied once per hour boundary crossed while a leg is open, on that
leg's CURRENT marked notional (checker M1), not its entry notional. dir_a = -sign(z), dir_b = sign(z) *
sign(beta) (shorting the spread when z > 0); a long leg (dir=+1) pays when that hour's fundingRate is
positive. funding_paid and funding_received are tracked separately (checker B7d).

SLIPPAGE. CONFIG["slippage_spread_share"] x the ctxs impact bid/ask spread AT THE FILL'S OWN LABEL --
slippage_frac() takes the wall-clock fill minute and applies the -1-minute shift itself (checker B1:
the earlier version passed the wall-clock minute straight into a label-indexed series, one minute
late). The share is applied once, in build_impact_series, to both the direct lookup and the 30-day
fallback (checker B14: runs 1-5 had no multiplier at all -- share was implicitly 1.0, the full spread,
against the brief's "half"). User decision 2026-11-09: share = 0.0 for the reported runs (the legs are
small); 0.5 (half the spread, the brief's original rule) ran once as a reference, not reported. Kept
as a CONFIG setting either way, not removed, so it can be turned back on. Fallback when impact data is
missing or non-positive: that coin's trailing 30-calendar-day median spread fraction, days strictly
BEFORE the fill's own day. Direct-hit, median-fallback and no-data-at-all (0.0) rates are each counted
separately (checker M4).

MONEY (checker M1/M2). move (sigma units) drives ONLY the exit rules (mu/stop/time-out), to keep the
v1 cross-check meaningful. Every dollar figure -- unrealised/realised P&L, fees, slippage, funding,
maintenance margin -- uses the two legs' own log-price paths (va, vb): leg_usd(m) = entry_leg_usd *
exp(log-price(m) - log-price(0)) is that leg's CURRENT dollar notional, and
P&L(m) = sum over legs of entry_leg_usd * dir * (exp(dlog) - 1).

DECISIONS THIS SCRIPT MAKES WHERE THE BRIEF LEAVES A CHOICE:
  - Same-minute ordering: mark-to-market/exit/liquidation for existing positions FIRST, then new
    admissions (highest p_cal first, seeded tie-break, H.score_fold's own convention) -- but a minute
    that liquidated admits NOTHING new at that same minute (checker B4).
  - Liquidation always closes at the TAKER fee rate and taker-side slippage, regardless of the run's own
    fee mode (brief; checker B3).
  - Win rate (planner ruling 3) = the share of trades exiting at mu (the exit_reason, not the sign of
    net). Mean win / mean loss / profit factor in the trade tables are by the SIGN of realised net USD
    P&L, both senses labelled separately in the report, never conflated.
  - MIN_RUN_EQUITY_USD (CONFIG, the "stop the run" floor): 2 x min_order_usd / (margin_frac x
    leverage_cap) = $40, rounded up to $50 -- the equity below which even the smallest two-leg position's
    required initial margin cannot buy the minimum order size at best-case leverage.

Trade logs: research/model/logs/profit1/trades_q{Q}_stop{S}_fee{F}.parquet (one row per trade, full
cost breakdown, exit_reason, p_cal_10h, leverage). Also per run: minute_equity_*.parquet (account state
every open minute), skips_*.parquet (every skipped pick with its reason), liquidations_*.parquet.
Report: research/model/logs/s1/s1_profit1_report.json. Mismatch receipt (if any):
research/model/logs/s1/s1_profit1_crosscheck_mismatches.parquet. NUMBERS section: a second script,
research/model/s1_profit1_numbers_gen.py (not yet written -- this script is the engine; the report
tables go to the checker separately before their numbers count).
"""
import json
import os
import subprocess
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "research", "dataset"))
sys.path.insert(0, os.path.join(ROOT, "research"))
import harness as H          # noqa: E402
import s1h_recalibration as S1H  # noqa: E402
import master_manifest as MF  # noqa: E402

LOG_DIR = os.path.join(HERE, "logs", "s1")
PROFIT_DIR = os.path.join(HERE, "logs", "profit1")
CTX_CACHE = os.path.join(PROFIT_DIR, "ctxs_cache")
FUND_CACHE = os.path.join(PROFIT_DIR, "fundinghist_cache")
BUILD2_CACHE = os.path.join(PROFIT_DIR, "build2_1m_cache")
BUCKET = "s3://pair-trading-hl-289869684922"
BUILD2_PREFIX = f"{BUCKET}/build2/d3/asm/futures"  # confirmed 2026-11-09: 206/206 sha256 match vs the
                                                     # committed 30m feathers; build3_swap.sh's own
                                                     # history already named d3/asm the promoted variant
AWS = os.path.expanduser("~/.local/bin/aws") if os.path.exists(os.path.expanduser("~/.local/bin/aws")) else "aws"
SEED = 20261108
MST_BUCKETS = [("0", lambda m: m == 0), ("1-5", lambda m: (m >= 1) & (m <= 5)),
               ("6-30", lambda m: (m >= 6) & (m <= 30)), (">30", lambda m: m > 30)]

# ---------------------------------------------------------------------------
# CONFIG -- one block, every value a setting, nothing hard-coded below it
# ---------------------------------------------------------------------------
CONFIG = dict(
    start_equity=1000.0,
    margin_frac=0.05,
    leverage_cap=10.0,
    max_open=10,
    fee_taker=0.00045,
    fee_maker=0.00015,
    slippage_on=True,
    funding_on=True,
    min_order_usd=10.0,
    qs=(0.01, 0.005, 0.001),
    stops=("0p5", "1p0", "2p0", "none"),
    fee_modes=("taker", "maker"),
    min_run_equity_usd=50.0,
    bootstrap_n=2000,
    bootstrap_level=0.9875,
    ev_quintiles=5,
    slippage_fallback_window_days=30,
    slippage_spread_share=0.0,     # user decision 2026-11-09: slippage = 0 for HL-PROFIT1 (the legs are
                                    # small). Kept as a setting, not removed, so it can be turned back
                                    # on; 0.5 (checker B14: half the impact spread, per the brief) ran
                                    # as run6, reference only, not the reported result
)
STOP_SIGMA = {"0p5": 0.5, "1p0": 1.0, "2p0": 2.0, "none": np.inf}


def log(msg):
    print(msg, flush=True)


# ---------------------------------------------------------------------------
# 1. Picks and p_cal (no refit of S1; reuses S1-H's own functions)
# ---------------------------------------------------------------------------
def load_picks_and_pcal():
    df, events = S1H.load_data()
    s1g_report = json.load(open(os.path.join(LOG_DIR, "s1g_report.json")))
    block_df, _ = S1H.compute_picks(df, s1g_report)
    folds = H.build_folds(events)

    iso_full = df.copy()
    iso_col = np.full(len(iso_full), np.nan)
    for k in range(1, 8):
        res = S1H.fit_and_apply(iso_full, folds, k, 10)
        iso_col[(iso_full["fold"] == k).to_numpy()] = res["iso_pred"]
    iso_full["p_cal_10h"] = iso_col
    pcal_map = iso_full.set_index("event_id")["p_cal_10h"]

    block_df = block_df.copy()
    block_df["p_cal_10h"] = block_df["event_id"].map(pcal_map)
    assert block_df["p_cal_10h"].notna().all(), "every picked event must have a p_cal_10h"

    top1 = block_df[block_df["pick_0.01"]]
    pooled_mean = float(top1["p_cal_10h"].mean())
    S1H_REPORTED = 0.6786192845636108
    assert abs(pooled_mean - S1H_REPORTED) < 1e-6, (
        f"pooled top-1% mean p_cal {pooled_mean} != S1-H's reported {S1H_REPORTED}")
    log(f"[PROFIT1] p_cal cross-check OK: pooled top-1% mean p_cal_10h = {pooled_mean:.10f} "
        f"(S1-H reported 0.6786192845636108 / NUMBERS.md '67.9%')")
    for q in CONFIG["qs"]:
        n_q = int(block_df[f"pick_{q}"].sum())
        log(f"[PROFIT1] q={q}: n={n_q:,}")
    return block_df


# ---------------------------------------------------------------------------
# 2. Event geometry, labels (for the cross-check) and leverage
# ---------------------------------------------------------------------------
def load_geometry_and_labels(event_ids):
    cols = ["ticker_a", "ticker_b", "beta", "alpha", "mu", "sigma", "z", "minutes_to_mu"]
    for s in CONFIG["stops"]:
        cols += [f"outcome_{s}", f"gross_{s}", f"net_{s}_taker", f"net_{s}_maker"]
    cols += ["fee_sigma_taker", "fee_sigma_maker"]
    ev = H.load_search_events(columns=cols)
    geo = ev.loc[event_ids, cols].copy()
    return geo


def load_leverage(event_ids):
    """a_max_leverage/b_max_leverage are OUT of inputs_v1_pair.csv's frozen IN list (A6:
    hindsight_static -- today's snapshot applied to the past), which guards MODEL FITTING against
    leakage; nothing is fitted here. Checker-approved 2026-11-09: read g4.parquet directly (NOT
    H.load_features, which enforces that gate), by event_id position, the same convention
    load_features uses internally -- sizing input, not a model input; OUT for fitting (A6
    hindsight_static), accepted as a known gap in the brief."""
    import pyarrow as pa
    import pyarrow.parquet as pq
    event_ids = np.asarray(event_ids)
    H._verify_once("g4.parquet")
    H._assert_positional_row_order("g4.parquet")
    f = os.path.join(MF.WORK, H.UNIT, "g4.parquet")
    tbl = pq.read_table(f, columns=["a_max_leverage", "b_max_leverage"])
    sliced = tbl.take(pa.array(event_ids))
    assert len(sliced) == len(event_ids), f"g4.parquet take() returned {len(sliced)} rows, expected {len(event_ids)}"
    lev = sliced.to_pandas()
    lev.index = event_ids
    assert lev.notna().all().all(), f"NaN leverage on {int(lev.isna().any(1).sum())} events -- cannot size a position"
    log(f"[PROFIT1] leverage: a_max_leverage [{lev['a_max_leverage'].min():.0f},{lev['a_max_leverage'].max():.0f}] "
        f"b_max_leverage [{lev['b_max_leverage'].min():.0f},{lev['b_max_leverage'].max():.0f}]")
    return lev


# ---------------------------------------------------------------------------
# 3. ctxs (price/funding/impact) -- S3 read-only, cached locally
# ---------------------------------------------------------------------------
def day_range():
    start = (H.TEST_BLOCK_STARTS[1] - pd.Timedelta(days=1)).strftime("%Y%m%d")
    end = (H.TEST_BLOCK_ENDS[7] + pd.Timedelta(days=1)).strftime("%Y%m%d")
    return pd.date_range(start, end, freq="D").strftime("%Y%m%d").tolist()


def ensure_ctxs_cached(days):
    os.makedirs(CTX_CACHE, exist_ok=True)
    failed = []
    missing = [d for d in days if not os.path.exists(os.path.join(CTX_CACHE, f"{d}.parquet"))]
    log(f"[PROFIT1] ctxs cache: {len(days) - len(missing)}/{len(days)} days already cached, "
        f"pulling {len(missing)}")
    for d in missing:
        dst = os.path.join(CTX_CACHE, f"{d}.parquet")
        cmd = [AWS, "s3", "cp", f"{BUCKET}/ctxs/{d}.parquet", dst, "--region", "ap-northeast-1",
               "--only-show-errors"]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            log(f"[PROFIT1] WARNING: ctxs {d} not pulled ({r.stderr.strip()[:200]})")
            failed.append(d)
    return failed


def ensure_fundinghist_cached(coins):
    os.makedirs(FUND_CACHE, exist_ok=True)
    missing = [c for c in coins if not os.path.exists(os.path.join(FUND_CACHE, f"{c}.parquet"))]
    log(f"[PROFIT1] fundinghist cache: {len(coins) - len(missing)}/{len(coins)} coins already cached, "
        f"pulling {len(missing)}")
    no_fund = []
    for c in coins:
        dst = os.path.join(FUND_CACHE, f"{c}.parquet")
        if not os.path.exists(dst):
            cmd = [AWS, "s3", "cp", f"{BUCKET}/fundinghist/{c}.parquet", dst, "--region", "ap-northeast-1",
                   "--only-show-errors"]
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode != 0:
                log(f"[PROFIT1] WARNING: fundinghist {c} not pulled ({r.stderr.strip()[:200]})")
        if not os.path.exists(dst):
            no_fund.append(c)
    return no_fund


def load_ctx_frame(days, coins):
    frames = []
    coin_set = set(coins)
    for d in days:
        f = os.path.join(CTX_CACHE, f"{d}.parquet")
        if not os.path.exists(f):
            continue
        part = pd.read_parquet(f, columns=["time", "coin", "mid_px", "impact_bid_px", "impact_ask_px"])
        part = part[part["coin"].isin(coin_set)]
        frames.append(part)
    out = pd.concat(frames, ignore_index=True)
    out["time"] = pd.to_datetime(out["time"], utc=True)
    return out


def clean_ctx_group(g):
    """Drops off-minute stamps (build1_bars.py's OFF-MINUTE ROWS rule -- flooring them is look-ahead),
    counted, BEFORE the label shift (no dedup step: duplicates are counted and asserted to zero below,
    never silently resolved). Checker's finding: a silent drop_duplicates("time")
    would hide a real duplicate (time, coin) row the way build1_bars.py's own `assert g.time.is_unique`
    does not let it. Counted and asserted zero here instead -- `g` is already one coin's rows (grouped
    by coin before this is called), so "time" alone is the full (time, coin) key within it. Returns
    (cleaned_g_with_label_col, n_offminute_dropped)."""
    offminute = (g["time"].dt.second != 0) | (g["time"].dt.microsecond != 0)
    n_off = int(offminute.sum())
    g = g[~offminute].sort_values("time").copy()
    n_dup = int(g["time"].duplicated().sum())
    assert n_dup == 0, f"{n_dup} duplicate (time, coin) row(s) in a ctxs group -- build1_bars.py's own " \
                        f"is_unique assert would have caught this; refusing to silently drop_duplicates"
    g["label"] = g["time"] - pd.Timedelta(minutes=1)
    return g, n_off


def ensure_build2_1m_cached(coins):
    """Pulls s3://pair-trading-hl-289869684922/build2/d3/asm/futures/{coin}-1m.feather -- the variant
    confirmed 2026-11-09 (206/206 sha256 match against the committed 30m feathers). Read-only, same
    pattern as ensure_ctxs_cached/ensure_fundinghist_cached."""
    os.makedirs(BUILD2_CACHE, exist_ok=True)
    missing = [c for c in coins if not os.path.exists(os.path.join(BUILD2_CACHE, f"{c}-1m.feather"))]
    log(f"[PROFIT1] build2 1m cache: {len(coins) - len(missing)}/{len(coins)} coins already cached, "
        f"pulling {len(missing)}")
    no_data = []
    for c in coins:
        dst = os.path.join(BUILD2_CACHE, f"{c}-1m.feather")
        if not os.path.exists(dst):
            cmd = [AWS, "s3", "cp", f"{BUILD2_PREFIX}/{c}-1m.feather", dst, "--region", "ap-northeast-1",
                   "--only-show-errors"]
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode != 0:
                log(f"[PROFIT1] WARNING: build2 1m {c} not pulled ({r.stderr.strip()[:200]})")
        if not os.path.exists(dst):
            no_data.append(c)
    return no_data


def build_dense_price(coins):
    """Per coin: {lo, price (log close), gap (bool, build2's own gap_in_bar -- a hole; TRUE gap, blocks
    both exits and liquidation, cross-check mismatch if inside a picked event's window), any_filled
    named `filled` here (bool, mins_since_trade > 0 AND NOT gap_in_bar -- a build2-carried no-trade
    minute; ruling 1, adapted 2026-11-09: real for both exits and liquidation, exactly as v1's own
    labels treat it, just counted)}. Reads s3://.../build2/d3/asm/futures/{coin}-1m.feather EXACTLY as
    envelope.load_1m_series does: duplicate minutes resolve to the LAST occurrence; gaps (minutes
    absent from the file) stay NaN; nothing is forward-filled beyond what build2's own pipeline already
    decided (no build1-era off-minute/<=5-min-fill rules -- those applied to a different source and do
    not apply here)."""
    out, diag = {}, {}
    for coin in coins:
        f = os.path.join(BUILD2_CACHE, f"{coin}-1m.feather")
        if not os.path.exists(f):
            continue
        d = pd.read_feather(f, columns=["date", "close", "mins_since_trade", "gap_in_bar"])
        ix = (pd.to_datetime(d["date"], utc=True).dt.tz_localize(None)
              .to_numpy().astype("datetime64[m]"))
        v = np.log(d["close"].to_numpy(float))
        mst = d["mins_since_trade"].to_numpy(float)
        gib = d["gap_in_bar"].to_numpy(bool)
        lo = ix.min()
        off = ((ix - lo) / np.timedelta64(1, "m")).astype(np.int64)
        n = int(off.max()) + 1
        price = np.full(n, np.nan, np.float64)
        mst_arr = np.full(n, np.nan, np.float64)
        gap_arr = np.ones(n, dtype=bool)          # absent minute = a gap by default
        price[off] = v                            # duplicates: last wins (envelope's own convention)
        mst_arr[off] = mst
        gap_arr[off] = gib
        filled_arr = (mst_arr > 0) & (~gap_arr) & ~np.isnan(price)
        # checker's m2: gap_in_bar is STRICTER than master_labels.py's own path, which reads only date
        # and close -- a gap_in_bar=True minute with a finite close would be flagged a true gap HERE
        # but not in v1. Moot on this run (0 gap events out of 35,629 picks), but worth knowing if a
        # future run finds any.
        true_gap_arr = gap_arr | np.isnan(price)
        out[coin] = dict(lo=lo, price=price, gap=true_gap_arr, filled=filled_arr, mst=mst_arr)
        diag[coin] = dict(n_minutes=n, n_true_gap=int(true_gap_arr.sum()), n_filled=int(filled_arr.sum()),
                           n_traded=int((mst_arr == 0).sum()))
    return out, diag


def window(arr, off, n):
    out = np.full(n, np.nan)
    lo, hi = max(off, 0), min(off + n, len(arr))
    if hi > lo:
        out[lo - off:hi - off] = arr[lo:hi]
    return out


def window_bool(arr, off, n, default=False):
    """Boolean window; out-of-range takes `default`."""
    out = np.full(n, default, dtype=bool)
    lo, hi = max(off, 0), min(off + n, len(arr))
    if hi > lo:
        out[lo - off:hi - off] = arr[lo:hi]
    return out


def build_impact_series(ctx_df):
    """Per coin: a pandas Series of SLIPPAGE fraction = slippage_spread_share x (ask-bid)/mid, indexed
    by LABEL minute, for the fill-time lookup and the 30-day trailing-median fallback. The multiplier
    is applied once here, in the one place both the direct lookup and the 30-day median fallback read
    from, so changing CONFIG["slippage_spread_share"] (checker B14 found runs 1-5 had no multiplier at
    all, i.e. share=1.0 regardless of the brief's "half the impact spread") always halves/zeroes both
    consistently, never just the direct hits. Impact/funding still come from ctxs (build1_bars.py's
    off-minute-drop rule applies here, via clean_ctx_group -- unaffected by the price-source switch to
    build2, which never used ctxs)."""
    share = CONFIG["slippage_spread_share"]
    log(f"[PROFIT1] slippage_spread_share = {share} (applied to both the direct impact-spread lookup "
        f"and the 30-day median fallback)")
    out = {}
    n_off_total = 0
    for coin, g in ctx_df.groupby("coin", sort=False):
        g, n_off = clean_ctx_group(g)
        n_off_total += n_off
        bid = g["impact_bid_px"].to_numpy(float)
        ask = g["impact_ask_px"].to_numpy(float)
        mid = g["mid_px"].to_numpy(float)
        frac = np.where((bid > 0) & (ask > 0) & (ask > bid) & (mid > 0), share * (ask - bid) / mid, np.nan)
        out[str(coin)] = pd.Series(frac, index=g["label"].to_numpy())
    return out, n_off_total


# ---------------------------------------------------------------------------
# 4. Move paths, per-leg price paths, the exit/outcome formula, coverage and cross-check
# ---------------------------------------------------------------------------
def compute_move_paths(block_top, geo, dense):
    """For every event_id in block_top: move (sigma units, exit rules), va/vb (per-leg log price,
    every dollar figure), any_filled (a build2-carried no-trade minute, real for exits+liquidation,
    ruling 1 adapted for build2). `status[eid]` is "ok" / "gap" (gap_in_bar or NaN close anywhere in
    the 601-minute window, either leg) / "no_data" (a leg's coin has no build2 1m file at all). Ruling
    2 is withdrawn -- v1's own 27,049 label_gap=1 events are already excluded upstream
    (H.load_search_events), so every picked event had a gap-free 601-minute window in the ORIGINAL
    archive; a gap or no-data status here is a reconstruction difference, not a v1 gap, and
    check_path_match treats it as a cross-check mismatch under the same hard abort -- "ok" events are
    the only ones placed in `paths` (what the simulation actually uses). coverage_rows: one dict per
    event (event_id, fold, covered, total=1202, and the mins_since_trade staleness buckets n0/n1_5/
    n6_30/n_gt30 over the covered minute-legs), for check_ctx_coverage to aggregate by fold and by q."""
    paths = {}
    coverage_rows = []
    status = {}
    for eid, t0, fold in zip(block_top["event_id"].to_numpy(), block_top["t0"].to_numpy(),
                              block_top["fold"].to_numpy()):
        row = geo.loc[eid]
        ta, tb = str(row["ticker_a"]), str(row["ticker_b"])
        if ta not in dense or tb not in dense:
            coverage_rows.append(dict(event_id=eid, fold=int(fold), covered=0, total=1202,
                                       n0=0, n1_5=0, n6_30=0, n_gt30=0))
            status[eid] = "no_data"
            continue
        start = pd.Timestamp(t0) - pd.Timedelta(minutes=1)
        da, db = dense[ta], dense[tb]
        off_a = int((np.datetime64(start, "m") - da["lo"]) / np.timedelta64(1, "m"))
        off_b = int((np.datetime64(start, "m") - db["lo"]) / np.timedelta64(1, "m"))
        va = window(da["price"], off_a, 601)
        vb = window(db["price"], off_b, 601)
        ga = window_bool(da["gap"], off_a, 601, default=True)
        gb = window_bool(db["gap"], off_b, 601, default=True)
        fa = window_bool(da["filled"], off_a, 601, default=False)
        fb = window_bool(db["filled"], off_b, 601, default=False)
        mst_a = window(da["mst"], off_a, 601)
        mst_b = window(db["mst"], off_b, 601)
        mst_covered = np.concatenate([mst_a[~ga], mst_b[~gb]])
        n0 = int((mst_covered == 0).sum())
        n1_5 = int(((mst_covered >= 1) & (mst_covered <= 5)).sum())
        n6_30 = int(((mst_covered >= 6) & (mst_covered <= 30)).sum())
        n_gt30 = int((mst_covered > 30).sum())
        # checker-approved fix (round 4 bug): covered must sum BOTH legs separately to match the
        # total=1202 denominator (601 minutes x 2 legs) -- the previous (~ga)&(~gb) AND-collapse gave
        # a 601-range count against a 1202 denominator, reading exactly 0.5 whenever both legs were
        # fully covered.
        covered = int((~ga).sum() + (~gb).sum())
        coverage_rows.append(dict(event_id=eid, fold=int(fold), covered=covered, total=1202,
                                   n0=n0, n1_5=n1_5, n6_30=n6_30, n_gt30=n_gt30))
        if ga.any() or gb.any() or np.isnan(va).any() or np.isnan(vb).any():
            status[eid] = "gap"
            continue
        status[eid] = "ok"
        beta, alpha, mu, sigma, z = (float(row[c]) for c in ("beta", "alpha", "mu", "sigma", "z"))
        P = (va - beta * vb - alpha - mu) / sigma
        s = 1.0 if z >= 0 else -1.0
        move = -(P - z) * s
        any_filled = fa | fb
        paths[eid] = dict(move=move, va=va, vb=vb, any_filled=any_filled)
    n_ok = sum(1 for v in status.values() if v == "ok")
    n_gap = sum(1 for v in status.values() if v == "gap")
    n_no_data = sum(1 for v in status.values() if v == "no_data")
    log(f"[PROFIT1] move paths: {n_ok:,} ok, {n_gap:,} with a true gap, {n_no_data:,} no data at all "
        f"(of {len(status):,} picks checked)")
    m0 = np.array([p["move"][0] for p in paths.values()])
    if len(m0):
        max_m0 = float(np.max(np.abs(m0)))
        log(f"[PROFIT1] move[0] check (status=ok events only): max |move[0]| = {max_m0:.3e}")
        assert max_m0 < 1e-6, f"move[0] should be ~0 by construction (P[0]==z); got max {max_m0}"
    return paths, coverage_rows, status


def exit_outcome_gross(seg, z_abs, stop_sigma):
    """seg: (600,) move for minutes 1..600. Identical formula to master_labels.py chunk_labels.
    Returns (outcome, gross, exit_minute_1based, t_mu_1based_or_inf)."""
    hit_mu = np.where(seg >= z_abs)[0]
    t_mu = hit_mu[0] + 1 if len(hit_mu) else np.inf
    if np.isinf(stop_sigma):
        t_st = np.inf
    else:
        hit_st = np.where(seg <= -stop_sigma)[0]
        t_st = hit_st[0] + 1 if len(hit_st) else np.inf
    outcome = 1.0 if t_mu < t_st else (-1.0 if t_st < t_mu else 0.0)
    ex = int(min(t_mu, t_st, 600))
    gross = float(seg[ex - 1])
    return outcome, gross, ex, t_mu


def check_ctx_coverage(coverage_rows, block_top):
    """Planner condition 1, REDEFINED 2026-11-09 for build2: per fold AND per q, the share of
    pick-minutes (both legs, m=0..600) with a finite close and gap_in_bar == False, plus a staleness
    breakdown from mins_since_trade (0 / 1-5 / 6-30 / >30) over that same covered population -- how
    often an exit or a liquidation would act on a carried, not a fresh, price."""
    cov = pd.DataFrame(coverage_rows)
    g = cov.groupby("fold").agg(covered=("covered", "sum"), total=("total", "sum"), n0=("n0", "sum"),
                                 n1_5=("n1_5", "sum"), n6_30=("n6_30", "sum"), n_gt30=("n_gt30", "sum"))
    g["share"] = g["covered"] / g["total"]
    log("[PROFIT1] build2 coverage (finite close, gap_in_bar=False) by test month (fold), "
        "pick-minutes both legs, m=0..600:")
    for k, r in g.iterrows():
        test_start = H.TEST_BLOCK_STARTS[k].date() if 0 <= k < len(H.TEST_BLOCK_STARTS) else "?"
        log(f"[PROFIT1]   fold {k} (test starts {test_start}): covered {int(r['covered']):,}/"
            f"{int(r['total']):,} = {r['share']:.6f}")
    log("[PROFIT1] staleness (mins_since_trade) by fold, share of COVERED pick-minutes:")
    for k, r in g.iterrows():
        tot = r["n0"] + r["n1_5"] + r["n6_30"] + r["n_gt30"]
        if tot == 0:
            continue
        log(f"[PROFIT1]   fold {k}: 0={r['n0']/tot:.4f} 1-5={r['n1_5']/tot:.4f} 6-30={r['n6_30']/tot:.4f} "
            f">30={r['n_gt30']/tot:.4f}  (n={int(tot):,})")
    log("[PROFIT1] build2 coverage and staleness by q:")
    for q in CONFIG["qs"]:
        q_eids = set(block_top.loc[block_top[f"pick_{q}"], "event_id"].to_numpy())
        sub = cov[cov["event_id"].isin(q_eids)]
        cov_share = sub["covered"].sum() / sub["total"].sum() if len(sub) else float("nan")
        tot = sub["n0"].sum() + sub["n1_5"].sum() + sub["n6_30"].sum() + sub["n_gt30"].sum()
        if tot == 0:
            log(f"[PROFIT1]   q={q}: coverage={cov_share:.6f} (no covered minutes)")
            continue
        log(f"[PROFIT1]   q={q}: coverage={cov_share:.6f} staleness 0={sub['n0'].sum()/tot:.4f} "
            f"1-5={sub['n1_5'].sum()/tot:.4f} 6-30={sub['n6_30'].sum()/tot:.4f} "
            f">30={sub['n_gt30'].sum()/tot:.4f} (n={int(tot):,})")
    return g


def check_path_match(block_top, geo, paths, status):
    """Classifies EVERY picked event (not just those in `paths`): a "gap" or "no_data" status is
    itself a mismatch (reason="gap"/"no_data") under the planner's withdrawn-ruling-2 decision -- v1's
    own 27,049 label_gap=1 events are already excluded upstream, so every picked event had a gap-free
    window in the original archive; a gap/no-data status here is a build2-vs-archive difference, not a
    v1 gap. For "ok" events, compares outcome_s/gross_s (every stop) and minutes_to_mu against v1's
    labels.parquet; a v1 NaN counts as a mismatch (checker B5), never a silent pass. Prints counts per
    fold and per q BEFORE the caller's hard abort; every mismatch (with a `reason` column) is returned
    for the parquet receipt."""
    fold_by_eid = dict(zip(block_top["event_id"].to_numpy(), block_top["fold"].to_numpy()))
    mismatches = []
    per_fold = {}
    for eid, fold in fold_by_eid.items():
        fold = int(fold)
        per_fold.setdefault(fold, {"n": 0, "mismatch": 0})
        per_fold[fold]["n"] += 1
        st = status.get(eid, "no_data")
        if st in ("no_data", "gap"):
            per_fold[fold]["mismatch"] += 1
            mismatches.append(dict(event_id=eid, fold=fold, stop=None, reason=st, outcome_sim=np.nan,
                                    gross_sim=np.nan, outcome_v1=np.nan, gross_v1=np.nan))
            continue
        row = geo.loc[eid]
        z_abs = abs(float(row["z"]))
        seg = paths[eid]["move"][1:601]
        v1_mu = row["minutes_to_mu"]
        v1_mu = float(v1_mu) if pd.notna(v1_mu) else np.inf
        event_mismatch = False
        for s_name, s_val in STOP_SIGMA.items():
            out_sim, gross_sim, _, t_mu_sim = exit_outcome_gross(seg, z_abs, s_val)
            out_v1_raw, gross_v1_raw = row[f"outcome_{s_name}"], row[f"gross_{s_name}"]
            v1_finite = pd.notna(out_v1_raw) and pd.notna(gross_v1_raw)
            match = (v1_finite and abs(out_sim - float(out_v1_raw)) <= 1e-9
                     and abs(gross_sim - float(gross_v1_raw)) <= 1e-6)
            if not match:
                event_mismatch = True
                mismatches.append(dict(event_id=eid, fold=fold, stop=s_name, reason="outcome_or_gross",
                                        outcome_sim=out_sim, gross_sim=gross_sim,
                                        outcome_v1=out_v1_raw, gross_v1=gross_v1_raw))
            if s_name == "none":
                mu_match = (np.isfinite(v1_mu) and np.isfinite(t_mu_sim) and abs(t_mu_sim - v1_mu) < 1e-6) or \
                           (not np.isfinite(v1_mu) and not np.isfinite(t_mu_sim))
                if not mu_match:
                    event_mismatch = True
                    mismatches.append(dict(event_id=eid, fold=fold, stop="minutes_to_mu",
                                            reason="minutes_to_mu", outcome_sim=t_mu_sim, gross_sim=np.nan,
                                            outcome_v1=v1_mu, gross_v1=np.nan))
        if event_mismatch:
            per_fold[fold]["mismatch"] += 1
    log("[PROFIT1] cross-check mismatch counts by fold (an event counts once if gap/no_data, or if "
        "ANY stop/minutes_to_mu comparison fails):")
    for k in sorted(per_fold):
        c = per_fold[k]
        log(f"[PROFIT1]   fold {k}: {c['mismatch']:,}/{c['n']:,} mismatched events")
    mismatched_eids = {m["event_id"] for m in mismatches}
    log("[PROFIT1] cross-check mismatch counts by q:")
    for q in CONFIG["qs"]:
        q_eids = set(block_top.loc[block_top[f"pick_{q}"], "event_id"].to_numpy())
        n_mis = len(q_eids & mismatched_eids)
        log(f"[PROFIT1]   q={q}: {n_mis:,}/{len(q_eids):,} mismatched events")
    return mismatches, per_fold


# ---------------------------------------------------------------------------
# 5. Funding
# ---------------------------------------------------------------------------
def load_funding_series(coins):
    out = {}
    for c in coins:
        f = os.path.join(FUND_CACHE, f"{c}.parquet")
        if not os.path.exists(f):
            continue
        d = pd.read_parquet(f, columns=["time", "fundingRate"])
        d["time"] = pd.to_datetime(d["time"], utc=True).dt.floor("h")
        out[c] = d.drop_duplicates("time").set_index("time")["fundingRate"].sort_index()
    return out


# ---------------------------------------------------------------------------
# 6. The portfolio simulation, one (q, stop, fee) run
# ---------------------------------------------------------------------------
SLIP_STATS_TEMPLATE = {"direct": 0, "fallback_median": 0, "fallback_none": 0}


def slippage_frac(impact_series, coin, fill_minute, fallback_cache, stats):
    """`fill_minute` is the WALL-CLOCK minute whose close prices the fill; impact_series is indexed by
    LABEL (= ctx stamp - 1 min), so the lookup shifts by -1 minute itself (checker B1: the earlier
    version passed the wall-clock minute straight in, one minute late)."""
    label_minute = pd.Timestamp(fill_minute) - pd.Timedelta(minutes=1)
    s = impact_series.get(coin)
    if s is not None and label_minute in s.index:
        v = s.loc[label_minute]
        if pd.notna(v):
            stats["direct"] += 1
            return float(v)
    key = (coin, label_minute.floor("D"))
    if key in fallback_cache:
        med = fallback_cache[key]
    elif s is None:
        med = 0.0
        fallback_cache[key] = med
    else:
        day0 = key[1]
        window_s = s[(s.index >= day0 - pd.Timedelta(days=CONFIG["slippage_fallback_window_days"])) & (s.index < day0)]
        med = float(window_s.median()) if len(window_s.dropna()) else 0.0
        fallback_cache[key] = med
    stats["fallback_none" if (s is None or med == 0.0) else "fallback_median"] += 1
    return med


def run_one(q, stop_name, fee_mode, picks, geo, lev, paths, impact_series, funding_series, rng):
    stop_sigma = STOP_SIGMA[stop_name]
    fee_rate = CONFIG["fee_taker"] if fee_mode == "taker" else CONFIG["fee_maker"]
    taker_rate = CONFIG["fee_taker"]
    picks = picks[picks[f"pick_{q}"]].copy()
    picks = picks[picks["event_id"].isin(paths.keys())]
    picks = picks.sort_values("t0", kind="stable")

    tie = rng.random(len(picks))
    order = np.lexsort((tie, -picks["p_cal_10h"].to_numpy(), picks["t0"].to_numpy()))
    picks = picks.iloc[order].reset_index(drop=True)
    pick_times = picks["t0"].tolist()   # tz-aware Timestamps preserved (checker M4: .to_numpy() strips tz)
    pick_pcal = picks["p_cal_10h"].to_numpy()
    pick_eids = picks["event_id"].to_numpy()

    cash = CONFIG["start_equity"]
    open_pos = {}
    margin_used = 0.0
    trades, skip_rows, liquidations, minute_rows = [], [], [], []
    skips = {"book_full": 0, "margin": 0, "min_order": 0, "below_floor": 0, "liquidated_minute": 0}
    slip_stats = dict(SLIP_STATS_TEMPLATE)
    n_funding_events = 0
    n_filled_held_minutes, n_exits_on_filled = 0, 0
    stopped_at = None

    i = 0
    n_picks = len(picks)
    fallback_cache = {}

    def mark_at(p, elapsed):
        elapsed = max(0, min(elapsed, 600))
        return 0.0 if elapsed == 0 else p["va"][elapsed] - p["va"][0], 0.0 if elapsed == 0 else p["vb"][elapsed] - p["vb"][0]

    def leg_pnl_and_usd(p, elapsed):
        da, db = mark_at(p, elapsed)
        leg_a_now = p["entry_leg_a_usd"] * np.exp(da)
        leg_b_now = p["entry_leg_b_usd"] * np.exp(db)
        pnl = p["entry_leg_a_usd"] * p["dir_a"] * (np.exp(da) - 1) + p["entry_leg_b_usd"] * p["dir_b"] * (np.exp(db) - 1)
        return pnl, leg_a_now, leg_b_now

    def account_value(cur_minute):
        v = cash
        for p in open_pos.values():
            elapsed = int((np.datetime64(cur_minute, "m") - p["start_label"]) / np.timedelta64(1, "m"))
            pnl, _, _ = leg_pnl_and_usd(p, elapsed)
            v += pnl
        return v

    def maintenance_total(cur_minute):
        total = 0.0
        for p in open_pos.values():
            elapsed = int((np.datetime64(cur_minute, "m") - p["start_label"]) / np.timedelta64(1, "m"))
            _, leg_a_now, leg_b_now = leg_pnl_and_usd(p, elapsed)
            total += leg_a_now / (2 * p["max_lev_a"]) + leg_b_now / (2 * p["max_lev_b"])
        return total

    def do_exit(eid, exit_minute_abs, reason, exit_rate):
        nonlocal cash, margin_used, n_exits_on_filled
        p = open_pos.pop(eid)
        if reason == "liquidation":
            elapsed = int((np.datetime64(exit_minute_abs, "m") - p["start_label"]) / np.timedelta64(1, "m"))
        else:
            elapsed = p["exit_rel"]
        elapsed = max(0, min(elapsed, 600))
        if p["any_filled"][elapsed]:
            n_exits_on_filled += 1
        pnl, leg_a_now, leg_b_now = leg_pnl_and_usd(p, elapsed)
        exit_fee = (leg_a_now + leg_b_now) * exit_rate
        label = pd.Timestamp(exit_minute_abs)
        sl_a = slippage_frac(impact_series, p["ticker_a"], label, fallback_cache, slip_stats) if CONFIG["slippage_on"] else 0.0
        sl_b = slippage_frac(impact_series, p["ticker_b"], label, fallback_cache, slip_stats) if CONFIG["slippage_on"] else 0.0
        exit_slip = leg_a_now * sl_a + leg_b_now * sl_b
        net = pnl - p["entry_fee"] - p["entry_slip"] - exit_fee - exit_slip - p["funding_paid"] + p["funding_received"]
        cash += pnl - exit_fee - exit_slip
        margin_used -= p["margin"]
        exit_reason = reason if reason == "liquidation" else {1.0: "mu", -1.0: "stop", 0.0: "timeout"}[p["outcome_sim"]]
        trades.append(dict(
            event_id=eid, ticker_a=p["ticker_a"], ticker_b=p["ticker_b"], t0=p["t0"], exit_time=label,
            exit_reason=exit_reason, exit_minute=elapsed, holding_minutes=elapsed, notional=p["notional"],
            leverage=p["leverage"], margin=p["margin"], p_cal_10h=p["p_cal_10h"], q=q, stop=stop_name,
            fee_mode=fee_mode, gross_pnl=pnl, entry_fee=p["entry_fee"], exit_fee=exit_fee,
            entry_slip=p["entry_slip"], exit_slip=exit_slip, funding_paid=p["funding_paid"],
            funding_received=p["funding_received"], net=net,
            exited_on_filled_minute=bool(p["any_filled"][elapsed]),
        ))

    cur_minute = pd.Timestamp(pick_times[0]) if n_picks else None
    while i < n_picks or open_pos:
        if not open_pos:
            cur_minute = pd.Timestamp(pick_times[i])
        liquidated_this_minute = False
        for eid in list(open_pos.keys()):
            p = open_pos[eid]
            elapsed = int((np.datetime64(cur_minute, "m") - p["start_label"]) / np.timedelta64(1, "m"))
            elapsed_c = max(0, min(elapsed, 600))
            if p["any_filled"][elapsed_c]:
                n_filled_held_minutes += 1
            if CONFIG["funding_on"] and cur_minute.minute == 0 and elapsed >= 0:
                _, leg_a_now, leg_b_now = leg_pnl_and_usd(p, elapsed_c)
                for leg, dirn, usd in (("a", p["dir_a"], leg_a_now), ("b", p["dir_b"], leg_b_now)):
                    fseries = funding_series.get(p[f"ticker_{leg}"])
                    if fseries is not None:
                        h = cur_minute.floor("h")
                        if h in fseries.index and h > p["last_funding_h"]:
                            rate = float(fseries.loc[h])
                            flow = -dirn * rate * usd
                            cash += flow
                            n_funding_events += 1
                            if flow < 0:
                                p["funding_paid"] += -flow
                            else:
                                p["funding_received"] += flow
                p["last_funding_h"] = cur_minute.floor("h")
            if elapsed >= p["exit_rel"]:
                do_exit(eid, cur_minute, "exit", fee_rate)
        if open_pos:
            av = account_value(cur_minute)
            maint = maintenance_total(cur_minute)
            if av < maint:
                for eid in list(open_pos.keys()):
                    do_exit(eid, cur_minute, "liquidation", taker_rate)
                liquidations.append(dict(time=cur_minute, account_value_before=av, maintenance=maint))
                liquidated_this_minute = True
                if cash < CONFIG["min_run_equity_usd"]:
                    stopped_at = cur_minute
                    break
        if liquidated_this_minute:
            # B4: a minute that liquidated admits nothing, including picks arriving at that exact
            # minute -- drained HERE (not deferred) so a later pass over this same calendar minute
            # (which the loop re-enters once open_pos is empty) cannot admit them after all.
            while i < n_picks and pd.Timestamp(pick_times[i]) == cur_minute:
                eid = int(pick_eids[i])
                i += 1
                skips["liquidated_minute"] += 1
                skip_rows.append(dict(event_id=eid, t0=cur_minute, reason="liquidated_minute"))
        else:
            while i < n_picks and pd.Timestamp(pick_times[i]) == cur_minute:
                eid = int(pick_eids[i])
                p_cal = float(pick_pcal[i])
                i += 1
                if len(open_pos) >= CONFIG["max_open"]:
                    skips["book_full"] += 1
                    skip_rows.append(dict(event_id=eid, t0=cur_minute, reason="book_full"))
                    continue
                av = account_value(cur_minute)
                if av < CONFIG["min_run_equity_usd"]:
                    skips["below_floor"] += 1
                    skip_rows.append(dict(event_id=eid, t0=cur_minute, reason="below_floor"))
                    continue
                g = geo.loc[eid]
                beta, alpha, mu, sigma, z = (float(g[c]) for c in ("beta", "alpha", "mu", "sigma", "z"))
                ta, tb = str(g["ticker_a"]), str(g["ticker_b"])
                lvrow = lev.loc[eid]
                max_lev_a, max_lev_b = float(lvrow["a_max_leverage"]), float(lvrow["b_max_leverage"])
                leverage = min(CONFIG["leverage_cap"], max_lev_a, max_lev_b)
                margin = CONFIG["margin_frac"] * av
                notional = margin * leverage
                leg_a_usd = notional / (1 + abs(beta))
                leg_b_usd = notional * abs(beta) / (1 + abs(beta))
                if leg_a_usd < CONFIG["min_order_usd"] or leg_b_usd < CONFIG["min_order_usd"]:
                    skips["min_order"] += 1
                    skip_rows.append(dict(event_id=eid, t0=cur_minute, reason="min_order"))
                    continue
                if margin_used + margin > av:
                    skips["margin"] += 1
                    skip_rows.append(dict(event_id=eid, t0=cur_minute, reason="margin"))
                    continue
                label0 = pd.Timestamp(cur_minute)
                p_obj = paths[eid]
                seg = p_obj["move"][1:601]
                z_abs = abs(z)
                outcome_sim, _, exit_rel_1based, _ = exit_outcome_gross(seg, z_abs, stop_sigma)
                sl_a = slippage_frac(impact_series, ta, label0, fallback_cache, slip_stats) if CONFIG["slippage_on"] else 0.0
                sl_b = slippage_frac(impact_series, tb, label0, fallback_cache, slip_stats) if CONFIG["slippage_on"] else 0.0
                entry_fee = (leg_a_usd + leg_b_usd) * fee_rate
                entry_slip = leg_a_usd * sl_a + leg_b_usd * sl_b
                cash -= (entry_fee + entry_slip)
                margin_used += margin
                dir_a = -1.0 if z >= 0 else 1.0
                dir_b = (1.0 if z >= 0 else -1.0) * (1.0 if beta >= 0 else -1.0)
                open_pos[eid] = dict(
                    t0=label0, start_label=np.datetime64(label0, "m"), va=p_obj["va"], vb=p_obj["vb"],
                    any_filled=p_obj["any_filled"], exit_rel=exit_rel_1based,
                    notional=notional, leverage=leverage,
                    margin=margin, entry_leg_a_usd=leg_a_usd, entry_leg_b_usd=leg_b_usd, ticker_a=ta,
                    ticker_b=tb, dir_a=dir_a, dir_b=dir_b, max_lev_a=max_lev_a, max_lev_b=max_lev_b,
                    last_funding_h=label0.floor("h"), funding_paid=0.0, funding_received=0.0,
                    outcome_sim=outcome_sim, p_cal_10h=p_cal, entry_fee=entry_fee, entry_slip=entry_slip,
                )
        av_now = account_value(cur_minute) if open_pos else cash
        maint_now = maintenance_total(cur_minute) if open_pos else 0.0
        minute_rows.append((cur_minute, av_now, cash, margin_used, maint_now, len(open_pos)))
        if not open_pos:
            continue
        cur_minute = cur_minute + pd.Timedelta(minutes=1)

    trade_log = pd.DataFrame(trades) if trades else pd.DataFrame(columns=[
        "event_id", "ticker_a", "ticker_b", "t0", "exit_time", "exit_reason", "exit_minute",
        "holding_minutes", "notional", "leverage", "margin", "p_cal_10h", "q", "stop", "fee_mode",
        "gross_pnl", "entry_fee", "exit_fee", "entry_slip", "exit_slip", "funding_paid",
        "funding_received", "net", "exited_on_filled_minute"])
    minute_equity = pd.DataFrame(minute_rows, columns=["time", "account_value", "cash", "margin_used",
                                                        "maintenance", "n_open"])
    skip_log = pd.DataFrame(skip_rows) if skip_rows else pd.DataFrame(columns=["event_id", "t0", "reason"])
    liq_log = pd.DataFrame(liquidations) if liquidations else pd.DataFrame(
        columns=["time", "account_value_before", "maintenance"])
    if len(trade_log):
        recon = CONFIG["start_equity"] + trade_log["net"].sum()
        assert abs(recon - cash) < 1e-3, f"net-sum reconciliation failed: start+sum(net)={recon} != final cash={cash}"
    if n_funding_events == 0 and CONFIG["funding_on"]:
        log(f"[PROFIT1] WARNING q={q} stop={stop_name} fee={fee_mode}: zero funding events applied")
    return dict(trade_log=trade_log, final_equity=cash, skips=skips, liquidations=liq_log,
                minute_equity=minute_equity, skip_log=skip_log, stopped_at=stopped_at,
                slip_stats=slip_stats, n_funding_events=n_funding_events,
                n_filled_held_minutes=n_filled_held_minutes, n_exits_on_filled=n_exits_on_filled)


# ---------------------------------------------------------------------------
# 7. Persist the cleaned series (user decision 2026-11-08: "always keep the processed copy")
# ---------------------------------------------------------------------------
CLEANED_S3_PREFIX = f"{BUCKET}/profit1_cleaned"


def save_cleaned_series_local(dense_price, price_diag, impact_series, impact_offminute, days, coins):
    """User decision 2026-11-08 (standing rule: always keep the processed copy). Writes the cleaned
    1-minute price and impact series this engine built in memory to LOCAL parquet (price/{coin}.parquet,
    impact/{coin}.parquet, manifest.json: coins, date range, row counts, sha256, the cleaning rules),
    then RELOADS from the just-written local files and ASSERTS the reload is identical to the in-memory
    build (checker M9 -- a silent dtype/tz change on the round-trip must not reach the cross-check or
    the simulation unseen). The engine runs on this reloaded copy. The S3 push happens separately, in
    sync_cleaned_series_to_s3(), AFTER the v1 cross-check passes (checker M10): a reconstruction that
    disagrees with the archive must never sit in profit1_cleaned/ looking like a good processed copy."""
    out_dir = os.path.join(PROFIT_DIR, "cleaned")
    price_dir, impact_dir = os.path.join(out_dir, "price"), os.path.join(out_dir, "impact")
    os.makedirs(price_dir, exist_ok=True)
    os.makedirs(impact_dir, exist_ok=True)
    manifest = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "coins": sorted(coins), "day_range": [days[0], days[-1]], "n_days": len(days),
        "price_source": {
            "variant": "build2 d3/asm (confirmed 2026-11-09: 206/206 sha256 match vs the committed "
                       "30m feathers)",
            "s3_prefix": BUILD2_PREFIX,
            "rule": "read exactly as envelope.load_1m_series: duplicate minutes resolve to the LAST "
                    "occurrence; gaps (minute absent, gap_in_bar, or NaN close) stay NaN/flagged; "
                    "nothing forward-filled beyond what build2's own pipeline already decided",
            "source_file_sha256": {c: MF.sha(os.path.join(BUILD2_CACHE, f"{c}-1m.feather"))
                                    for c in dense_price if os.path.exists(os.path.join(BUILD2_CACHE, f"{c}-1m.feather"))},
        },
        "funding_source": f"{BUCKET}/fundinghist/{{coin}}.parquet (unmodified, already existing, "
                           f"research/dataset/master_g7.py's source)",
        "files": {"price": {}, "impact": {}},
        "crosscheck_passed": None, "crosscheck_mismatch_count": None,
    }
    for coin, d in dense_price.items():
        n = len(d["price"])
        labels = d["lo"] + np.arange(n).astype("timedelta64[m]")
        df = pd.DataFrame({"label": labels, "log_close": d["price"], "gap_in_bar": d["gap"],
                            "filled": d["filled"], "mins_since_trade": d["mst"]})
        path = os.path.join(price_dir, f"{coin}.parquet")
        df.to_parquet(path, index=False)
        manifest["files"]["price"][coin] = {"n_rows": n, "sha256": MF.sha(path)}
    for coin, s in impact_series.items():
        df = s.rename("impact_frac").rename_axis("label").reset_index()
        path = os.path.join(impact_dir, f"{coin}.parquet")
        df.to_parquet(path, index=False)
        manifest["files"]["impact"][coin] = {"n_rows": len(df), "sha256": MF.sha(path)}
    mpath = os.path.join(out_dir, "manifest.json")
    json.dump(manifest, open(mpath, "w"), indent=2, default=str)
    log(f"[PROFIT1] cleaned series saved locally under {out_dir} ({len(dense_price)} price, "
        f"{len(impact_series)} impact coins); manifest {mpath}")

    dense_reloaded, impact_reloaded = {}, {}
    for coin, d in dense_price.items():
        df = pd.read_parquet(os.path.join(price_dir, f"{coin}.parquet"))
        lo = df["label"].to_numpy().astype("datetime64[m]")[0]
        price_r, gap_r, filled_r, mst_r = (df["log_close"].to_numpy(float), df["gap_in_bar"].to_numpy(bool),
                                            df["filled"].to_numpy(bool), df["mins_since_trade"].to_numpy(float))
        assert lo == d["lo"], f"{coin}: reloaded lo {lo} != in-memory lo {d['lo']}"
        assert np.array_equal(price_r, d["price"], equal_nan=True), f"{coin}: reloaded price != in-memory"
        assert np.array_equal(gap_r, d["gap"]), f"{coin}: reloaded gap mask != in-memory"
        assert np.array_equal(filled_r, d["filled"]), f"{coin}: reloaded filled mask != in-memory"
        assert np.array_equal(mst_r, d["mst"], equal_nan=True), f"{coin}: reloaded mins_since_trade != in-memory"
        dense_reloaded[coin] = dict(lo=lo, price=price_r, gap=gap_r, filled=filled_r, mst=mst_r)
    for coin, s in impact_series.items():
        df = pd.read_parquet(os.path.join(impact_dir, f"{coin}.parquet"))
        idx_r = pd.DatetimeIndex(df["label"])
        vals_r = df["impact_frac"].to_numpy(float)
        assert idx_r.equals(s.index), f"{coin}: reloaded impact index != in-memory (tz or values differ)"
        assert np.array_equal(vals_r, s.to_numpy(), equal_nan=True), f"{coin}: reloaded impact values != in-memory"
        impact_reloaded[coin] = pd.Series(vals_r, index=idx_r)
    log(f"[PROFIT1] cleaned series reloaded from local parquet and verified identical to the in-memory "
        f"build (M9): {len(dense_reloaded)} price, {len(impact_reloaded)} impact coins -- the engine "
        f"runs on these.")
    return dense_reloaded, impact_reloaded, manifest, out_dir


def sync_cleaned_series_to_s3(out_dir, manifest, n_mismatches):
    """Checker M10: called ONLY after the v1 cross-check has already asserted n_mismatches == 0.
    Stamps crosscheck_passed/crosscheck_mismatch_count into manifest.json (re-saved locally) before the
    S3 push, so profit1_cleaned/ never shows a reconstruction that disagreed with the archive as a good
    processed copy. Returns (sync_ok, manifest)."""
    manifest["crosscheck_passed"] = True
    manifest["crosscheck_mismatch_count"] = n_mismatches
    mpath = os.path.join(out_dir, "manifest.json")
    json.dump(manifest, open(mpath, "w"), indent=2, default=str)
    r = subprocess.run([AWS, "s3", "sync", out_dir, f"{CLEANED_S3_PREFIX}/", "--region", "ap-northeast-1",
                        "--only-show-errors"], capture_output=True, text=True)
    sync_ok = r.returncode == 0
    if not sync_ok:
        log(f"[PROFIT1] WARNING: S3 sync of cleaned series failed: {r.stderr.strip()[:300]}")
    else:
        log(f"[PROFIT1] cleaned series (post-cross-check) pushed to {CLEANED_S3_PREFIX}/")
    return sync_ok, manifest


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main():
    t0 = time.time()
    for name in ("s1_profit1.py", "s1h_recalibration.py", "harness.py"):
        p = os.path.join(HERE, name)
        if os.path.exists(p):
            log(f"[PROFIT1] sha256 {name}: {MF.sha(p)}")
    log(f"[PROFIT1] start {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} UTC; pid {os.getpid()}; "
        f"seed={SEED}; CONFIG={json.dumps(CONFIG)}")

    picks = load_picks_and_pcal()
    top1 = picks[picks["pick_0.01"]].copy()
    event_ids = top1["event_id"].to_numpy()
    geo = load_geometry_and_labels(event_ids)
    lev = load_leverage(event_ids)

    coins = sorted(set(geo["ticker_a"]) | set(geo["ticker_b"]))
    log(f"[PROFIT1] {len(coins)} distinct coins across q=1% picks")
    days = day_range()
    failed_days = ensure_ctxs_cached(days)                 # funding/impact still from ctxs
    no_fund_coins = ensure_fundinghist_cached(coins)
    no_build2_coins = ensure_build2_1m_cached(coins)        # price now from build2 d3/asm

    ctx_df = load_ctx_frame(days, coins)
    dense_price, price_diag = build_dense_price(coins)
    impact_series, impact_offminute = build_impact_series(ctx_df)
    funding_series = load_funding_series(coins)

    os.makedirs(PROFIT_DIR, exist_ok=True)
    dense_price, impact_series, save_manifest, cleaned_out_dir = save_cleaned_series_local(
        dense_price, price_diag, impact_series, impact_offminute, days, coins)

    paths, coverage_rows, status = compute_move_paths(top1, geo, dense_price)
    cov_table = check_ctx_coverage(coverage_rows, top1)
    mismatches, mismatch_per_fold = check_path_match(top1, geo, paths, status)

    if mismatches:
        mdf = pd.DataFrame(mismatches)
        mpath = os.path.join(LOG_DIR, "s1_profit1_crosscheck_mismatches.parquet")
        mdf.to_parquet(mpath, index=False)
        log(f"[PROFIT1] {len(mismatches):,} cross-check mismatches written to {mpath}")
    assert not mismatches, (
        f"{len(mismatches)} mismatches vs v1 (gap/no_data/outcome/gross/minutes_to_mu) -- see the parquet")

    sync_ok, save_manifest = sync_cleaned_series_to_s3(cleaned_out_dir, save_manifest, len(mismatches))

    report = {"config": CONFIG, "runs": {}, "coverage_by_fold": cov_table.to_dict(orient="index"),
              "cleaned_series_manifest": save_manifest, "cleaned_series_s3_sync_ok": sync_ok,
              "failed_ctxs_days": failed_days, "coins_without_fundinghist": no_fund_coins,
              "coins_without_build2_1m": no_build2_coins,
              "build2_price_diag": price_diag, "impact_offminute_dropped": impact_offminute}
    rng_master = np.random.default_rng(SEED)
    for q in CONFIG["qs"]:
        for stop in CONFIG["stops"]:
            for fee in CONFIG["fee_modes"]:
                key = f"q{q}_stop{stop}_fee{fee}"
                log(f"[PROFIT1] running {key} ...")
                rng = np.random.default_rng(rng_master.integers(0, 2**63 - 1))
                res = run_one(q, stop, fee, picks, geo, lev, paths, impact_series, funding_series, rng)
                for name, df_ in (("trades", res["trade_log"]), ("minute_equity", res["minute_equity"]),
                                   ("skips", res["skip_log"]), ("liquidations", res["liquidations"])):
                    out_path = os.path.join(PROFIT_DIR, f"{name}_q{q}_stop{stop}_fee{fee}.parquet")
                    df_.to_parquet(out_path, index=False)
                report["runs"][key] = dict(
                    final_equity=res["final_equity"], n_trades=len(res["trade_log"]), skips=res["skips"],
                    n_liquidations=len(res["liquidations"]),
                    stopped_at=str(res["stopped_at"]) if res["stopped_at"] is not None else None,
                    slip_stats=res["slip_stats"], n_funding_events=res["n_funding_events"],
                    n_filled_held_minutes=res["n_filled_held_minutes"], n_exits_on_filled=res["n_exits_on_filled"],
                )
                log(f"[PROFIT1] {key}: final_equity={res['final_equity']:.2f} n_trades={len(res['trade_log'])} "
                    f"skips={res['skips']} liquidations={len(res['liquidations'])} "
                    f"funding_events={res['n_funding_events']} slip={res['slip_stats']}")

    report_path = os.path.join(LOG_DIR, "s1_profit1_report.json")
    json.dump(report, open(report_path, "w"), indent=2, default=str)
    log(f"[PROFIT1] report written: {report_path}  [{time.time()-t0:.0f}s]")


if __name__ == "__main__":
    main()
