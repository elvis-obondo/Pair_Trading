"""HL-BUILD1 B1 + B2: the Hyperliquid coin list and close-only bars from asset_ctxs.

SOURCE. s3://hyperliquid-archive/asset_ctxs/{YYYYMMDD}.csv.lz4, every day file
from 20250101 to the last in the archive, cached raw in ~/.cache/hl_asset_ctxs
(outside git). One row per coin per minute stamp.

LABEL (B0, build1_b0_timestamp.log). The row stamped T is the state at T: its
mid_px 1m returns line up with the candle opened at T-1m on all 5 test coins
(corr 0.94-1.00, margin >= 0.86). So row T is the CLOSE of the 1m bar labelled
T-1m. LABEL_SHIFT = -1 minute. Bar labelled t carries only what is observable
at t+1m: no look-ahead.

OFF-MINUTE ROWS (build1_offminute.log). 192 stamps in the archive are not on
the minute (e.g. 2025-01-05 13:50:57), the same 192 for every coin. In all 192
the floor minute (13:50) has no row: each is that minute's snapshot taken 1-59 s
late. Labelling it as the floor minute would be look-ahead (state at 13:50:57
called the state at 13:50), so these rows are DROPPED and counted; their floor
minute is then a 1-minute hole and falls under the <=5 fill rule below.

PRICE. mid_px only (not mark, not oracle). A row whose mid_px is missing or
<= 0 counts as a missing minute.

B1 COIN LIST. Every coin in any file 20250101..last, delisted ones included.
Names containing ':' (HIP-3) or starting with '@' (spot) are excluded and
counted. Hyperliquid names kept (kPEPE). first_date / last_date are the coin's
first / last stamp WITH A VALID mid. DELISTED RULE: a coin is delisted if its
last valid mid falls before the archive's last day, or it never has a valid mid
(no_valid). Corrected 2026-10-14 after run 3: the archive keeps delisted coins
(MATIC, RNDR, ...) as rows with an empty mid to the very end, so "absent from
the final day file" never fired (0 delisted). Today's exchange listing is never
consulted.

LISTED LIFE. The coin's 1m label grid from its first to its last stamp WITH A
VALID mid_px (shifted by LABEL_SHIFT). Never anything before the first or after
the last appearance. Rows before the first / after the last valid mid are
trimmed and the coins where that happened are counted.

DISK. Measured on 20260601: one day is 14 MB as per-coin feather parts and
16 MB as ctx files. Estimated peak ~13 GB (parts ~9 GB shrinking as each coin's
parts are deleted once its outputs pass their assertions, ctx ~10 GB and bars
~3 GB growing). Preflight aborts under MIN_FREE_GB free; every flush and every
coin re-checks and aborts under ABORT_FREE_GB.

MISSING MINUTES, DECISION RULE (from the brief, fixed before the run):
  - a run of <= 5 consecutive missing minutes inside the listed life is forward-
    filled from the last real close, and counted (filled_minutes);
  - longer runs stay NaN (nan_minutes) and are listed with start, end, length;
  - GATE: if more than 5% of coins have more than 1% of listed minutes filled or
    NaN -> STOP and report. The verdict is computed exactly so.
  Receipt split (report only, does not change the verdict): a minute where the
  archive has no row for ANY coin is an archive-wide hole; each run is tagged
  archive_wide when every minute in it is one.

30m BARS. Labels on the :00/:30 grid. The bar labelled H closes at the 1m bar
labelled H+29 (the minute H+29..H+30), so close_30m[H] = close_1m[H+29],
asserted equal (NaN==NaN) on every bar. A 30m bar is kept when its last minute
H+29 lies inside the listed life.

OUTPUT (schema of the OKX bar files): user_data/data/hyperliquid/futures/
{COIN}-{1m,30m}.feather, columns date (datetime64[ms, UTC], bar OPEN), open,
high, low, close, volume (float64). close = the price; open/high/low/volume are
NaN -- never faked. Extras (funding, open_interest, prev_day_px, day_ntl_vlm,
premium, oracle_px, mark_px, impact_bid_px, impact_ask_px) to
user_data/data/hyperliquid/ctx/{COIN}-1m-ctx.feather on the same 1m label grid,
raw (unfilled). Coin list to research/hyperliquid/coins.csv; long runs to
research/hyperliquid/nan_runs.csv.
"""
import glob, io, os, shutil, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, pandas as pd
from adapters.hyperliquid_futures import HL_FUTURES_DIR, HL_CTX_DIR, bar_file, ctx_file

CACHE = os.path.expanduser("~/.cache/hl_asset_ctxs")
PARTS = os.path.expanduser("~/.cache/hl_build1_parts")
OUTDIR = os.path.dirname(os.path.abspath(__file__))
FIRST_DAY = "20250101"
LABEL_SHIFT = pd.Timedelta(minutes=-1)
FILL_MAX = 5
COIN_GATE, SHARE_GATE = 0.01, 0.05
FLUSH_DAYS = 10
MIN_FREE_GB, ABORT_FREE_GB = 16.0, 3.0
EXTRA = ["funding", "open_interest", "prev_day_px", "day_ntl_vlm", "premium",
         "oracle_px", "mark_px", "impact_bid_px", "impact_ask_px"]
BAR = ["open", "high", "low", "close", "volume"]


def free_gb():
    return shutil.disk_usage(os.path.expanduser("~")).free / 1e9


def dir_gb(p):
    return sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(p) for f in fs) / 1e9


def guard(where):
    if free_gb() < ABORT_FREE_GB:
        sys.exit(f"[ABORT] {free_gb():.1f} GB free at {where}, under {ABORT_FREE_GB} GB")


def read_day(path):
    raw = subprocess.run(["lz4", "-dc", path], check=True, capture_output=True).stdout
    d = pd.read_csv(io.BytesIO(raw), dtype={"coin": str})
    d["time"] = pd.to_datetime(d.time, utc=True, format="%Y-%m-%dT%H:%M:%SZ")
    off = d.time.dt.second != 0
    return d[~off], int(off.sum()), int(d.time[off].nunique())


# ---------------------------------------------------------------- preflight
print(f"[DISK] free {free_gb():.1f} GB, preflight floor {MIN_FREE_GB} GB", flush=True)
if free_gb() < MIN_FREE_GB:
    sys.exit(f"[ABORT] preflight: {free_gb():.1f} GB free, under {MIN_FREE_GB} GB. Report; delete nothing.")

# ---------------------------------------------------------------- pass 1: split by coin
files = sorted(f for f in glob.glob(os.path.join(CACHE, "*.csv.lz4"))
               if os.path.basename(f)[:8] >= FIRST_DAY)
last_day = os.path.basename(files[-1])[:8]
print(f"[INFO] {len(files)} day files {os.path.basename(files[0])[:8]} -> {last_day}", flush=True)
shutil.rmtree(PARTS, ignore_errors=True); os.makedirs(PARTS)
buf, stamps, excluded, allnames = {}, set(), set(), set()
dups = 0; t0 = time.time(); off_rows = 0; off_stamps = 0
for k, f in enumerate(files):
    d, o_r, o_s = read_day(f); off_rows += o_r; off_stamps += o_s
    bad = d.coin.str.contains(":", regex=False) | d.coin.str.startswith("@")
    excluded |= set(d.coin[bad]); d = d[~bad]
    allnames |= set(d.coin)
    dups += int(d.duplicated(["time", "coin"]).sum())
    stamps |= set(d.time.unique())
    for c, g in d.groupby("coin", sort=False):
        buf.setdefault(c, []).append(g.drop(columns="coin"))
    if (k + 1) % FLUSH_DAYS == 0 or f == files[-1]:
        for c, gs in buf.items():
            os.makedirs(os.path.join(PARTS, c), exist_ok=True)
            pd.concat(gs, ignore_index=True).to_feather(os.path.join(PARTS, c, f"{k:04d}.feather"))
        buf = {}
        guard(f"pass 1 day {k+1}")
        print(f"  {k+1}/{len(files)} days, {time.time()-t0:.0f}s, {free_gb():.1f} GB free", flush=True)
assert dups == 0, f"{dups} duplicate (time, coin) rows"
print(f"[B1] off-minute rows dropped: {off_rows:,} rows on {off_stamps} distinct stamps")
# names from the DATA, not the PARTS listing: on a case-insensitive disk two
# such names already share one directory, so a listing could never show them
names = sorted(allnames)
low = pd.Series(names).str.lower()
coll = sorted(set(low[low.duplicated()]))
print(f"[B1] case-collision check: {len(names)} coin names, collisions {coll}")
assert not coll, "two coin names differ only by case on a case-insensitive disk"
print(f"[DISK] PARTS {dir_gb(PARTS):.2f} GB, free {free_gb():.1f} GB", flush=True)
print(f"[B1] excluded names (':' or '@'): {len(excluded)} {sorted(excluded)[:20]}")
stamps = pd.DatetimeIndex(sorted(stamps))
arch_lo, arch_hi = stamps[0], stamps[-1]
arch_grid = pd.date_range(arch_lo, arch_hi, freq="1min")
arch_has = pd.Series(False, index=arch_grid); arch_has[stamps] = True
print(f"[B1] archive stamps {len(stamps):,} of {len(arch_grid):,} minutes "
      f"{arch_lo} -> {arch_hi}; archive-wide missing {int((~arch_has).sum()):,}")

# ---------------------------------------------------------------- pass 2: per coin
for d_ in (HL_FUTURES_DIR, HL_CTX_DIR):
    os.makedirs(d_, exist_ok=True)
rows, runs = [], []
n30 = 0; trimmed = 0; no_valid = []
assert set(os.listdir(PARTS)) == set(names), "PARTS holds entries that are not coin names"
for c in names:
    g = pd.concat([pd.read_feather(p) for p in sorted(glob.glob(os.path.join(PARTS, c, "*.feather")))],
                  ignore_index=True).sort_values("time")
    assert g.time.is_unique
    v = g[g.mid_px > 0]
    if v.empty:
        no_valid.append(c)
        rows.append((c, g.time.iloc[0].date(), g.time.iloc[-1].date(), 0, 0, 0,
                     None, 0, True))
        shutil.rmtree(os.path.join(PARTS, c)); continue
    if len(v) < len(g) and (v.time.iloc[0] != g.time.iloc[0] or v.time.iloc[-1] != g.time.iloc[-1]):
        trimmed += 1
    first, last = v.time.iloc[0], v.time.iloc[-1]
    g = g[(g.time >= first) & (g.time <= last)]
    life = pd.date_range(first, last, freq="1min")
    g = g.set_index("time").reindex(life)
    mid = g.mid_px.where(g.mid_px > 0)
    miss = mid.isna().to_numpy()
    # runs of consecutive missing minutes
    edge = np.diff(np.r_[0, miss.astype(np.int8), 0])
    starts, ends = np.flatnonzero(edge == 1), np.flatnonzero(edge == -1)   # [start, end)
    fill = np.zeros(len(mid), bool)
    for s, e in zip(starts, ends):
        if e - s <= FILL_MAX:
            fill[s:e] = True
        else:
            runs.append((c, life[s] + LABEL_SHIFT, life[e - 1] + LABEL_SHIFT, e - s,
                         bool((~arch_has.reindex(life[s:e])).all())))
    filled = mid.ffill().where(fill, mid)
    assert not filled[fill].isna().any(), f"{c}: a fill run has no prior close"
    close = filled.to_numpy(float)
    lab = (life + LABEL_SHIFT).astype("datetime64[ms, UTC]")
    b1 = pd.DataFrame({"date": lab, "open": np.nan, "high": np.nan, "low": np.nan,
                       "close": close, "volume": np.nan})
    b1.to_feather(bar_file(c, "1m"))
    # 30m: bar H closes at 1m label H+29; keep H when H+29 is inside the life
    s1 = pd.Series(close, index=pd.DatetimeIndex(lab))
    H = pd.date_range(s1.index[0].floor("30min"), s1.index[-1], freq="30min")
    H = H[(H + pd.Timedelta(minutes=29) >= s1.index[0]) & (H + pd.Timedelta(minutes=29) <= s1.index[-1])]
    c30 = s1.reindex(H + pd.Timedelta(minutes=29)).to_numpy()
    b30 = pd.DataFrame({"date": H.astype("datetime64[ms, UTC]"), "open": np.nan, "high": np.nan,
                        "low": np.nan, "close": c30, "volume": np.nan})
    b30.to_feather(bar_file(c, "30m"))
    # the assertion the brief asks for, on the files as written: every 30m close
    # equals the 1m close labelled date+29 (NaN == NaN), and every bar has one
    r1 = pd.read_feather(bar_file(c, "1m")).set_index("date").close
    r30 = pd.read_feather(bar_file(c, "30m"))
    assert r1.index.is_unique and r30.date.is_unique
    m = r1.reindex(r30.date + pd.Timedelta(minutes=29))
    assert m.index.isin(r1.index).all(), f"{c}: a 30m bar's last minute is not a 1m bar"
    assert np.array_equal(r30.close.to_numpy(), m.to_numpy(), equal_nan=True), f"{c}: 30m close != last 1m close"
    n30 += len(r30)
    cx = g[EXTRA].reset_index(drop=True); cx.insert(0, "date", lab)
    cx.to_feather(ctx_file(c))
    rows.append((c, first.date(), last.date(), len(life), int(fill.sum()),
                 int(np.isnan(close).sum()), None,
                 int((~arch_has.reindex(life)).sum()), False))
    shutil.rmtree(os.path.join(PARTS, c))
    guard(f"coin {c}")

C = pd.DataFrame(rows, columns=["coin", "first_date", "last_date", "listed_minutes",
                                "filled_minutes", "nan_minutes", "delisted", "archive_wide_minutes",
                                "no_valid"])
C["delisted"] = np.where((pd.to_datetime(C.last_date) < pd.Timestamp(arch_hi.date())) | C.no_valid, "yes", "no")
C.to_csv(os.path.join(OUTDIR, "coins.csv"), index=False)
R = pd.DataFrame(runs, columns=["coin", "start_label", "end_label", "minutes", "archive_wide"])
R.to_csv(os.path.join(OUTDIR, "nan_runs.csv"), index=False)

Cg = C[~C.no_valid].copy()      # gate denominator: coins with a valid mid
Cg["bad_share"] = (Cg.filled_minutes + Cg.nan_minutes) / Cg.listed_minutes
over = Cg.bad_share > COIN_GATE
print(f"\n[B1] coins with no valid mid_px at all (no files written): {no_valid}")
print(f"[B1] coins whose life was trimmed to the first/last valid mid: {trimmed}")
print(f"[DISK] futures {dir_gb(HL_FUTURES_DIR):.2f} GB, ctx {dir_gb(HL_CTX_DIR):.2f} GB, free {free_gb():.1f} GB")
print(f"[B2] 30m close == 1m close at date+29 asserted on all {n30:,} bars of {int((~C.no_valid).sum())} coins")
print(f"[B1] coins {len(C)}  delisted {int((C.delisted=='yes').sum())}  "
      f"live at the archive's end {int((C.delisted=='no').sum())}")
print(f"[B2] filled minutes {int(C.filled_minutes.sum()):,}  nan minutes {int(C.nan_minutes.sum()):,}  "
      f"listed minutes {int(C.listed_minutes.sum()):,}")
print(f"[B2] long NaN runs {len(R):,}: archive-wide {int(R.archive_wide.sum()):,} "
      f"({int(R.minutes[R.archive_wide].sum()):,} min), coin-specific {int((~R.archive_wide).sum()):,} "
      f"({int(R.minutes[~R.archive_wide].sum()):,} min)")
print("[B2] bad_share quantiles: " + "  ".join(f"p{int(q*100)} {Cg.bad_share.quantile(q):.4f}"
                                                for q in (0.1, 0.5, 0.9, 1.0)))
# receipt split, report only
nx = (Cg.filled_minutes + Cg.nan_minutes - Cg.archive_wide_minutes).clip(lower=0) / Cg.listed_minutes
print(f"[B2] (receipt only) coins over 1% EXCLUDING archive-wide minutes: {int((nx > COIN_GATE).sum())} "
      f"of {len(Cg)} ({100*(nx > COIN_GATE).mean():.1f}%)")
print(f"[B2] GATE: coins with > {COIN_GATE:.0%} of listed minutes filled or NaN: "
      f"{int(over.sum())} of {len(Cg)} ({100*over.mean():.1f}%), threshold {SHARE_GATE:.0%}  "
      f"[denominator excludes {int(C.no_valid.sum())} no_valid coin(s); {len(C)} in coins.csv]")
if over.mean() > SHARE_GATE:
    print("[B2] STOP: the missing-minutes gate fails. Report; do not proceed to B3/B4.")
    sys.exit(2)
print("[B2] PASS")
