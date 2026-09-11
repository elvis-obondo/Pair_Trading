"""
Runs nautilus/run_backtest.py once per pair across the tradeable-pair list
returned by research/pair_analysis.py's discovery process
(analyze_top_pairs -> get_tradeable_pairs) for a single, fixed historical
window, and pools every pair's completed trades -- enriched with run/
discovery/config metadata -- into one cumulative Parquet dataset
(research/trade_pool.parquet).

This is deliberately SAME-WINDOW pooling: every pair in one batch is
discovered AND backtested against the same fixed historical anchor
(DISCOVERY_END_DATE), not a walk-forward holdout after it -- pair discovery
itself needs a fixed window to find cointegrated pairs in the first place.
Walk-forward (discover on one window, backtest the following one) is a
separate, later concern -- see nautilus/run_backtest.py's own
BACKTEST_END_DATE mechanism and research/run_all.py's WALKFORWARD_DAYS_BACK
for that.

Pair selection is NOT a hardcoded list (the old TRADEABLE_PAIRS constant this
replaced was a dated, hand-frozen snapshot that had already drifted from
get_tradeable_pairs()'s actual current filters). Instead:

    tradeable = get_tradeable_pairs(analyze_top_pairs(days=DISCOVERY_DAYS, end_date=DISCOVERY_END_DATE))

cached per (end_date, days) in research/discovery_cache/ -- analyze_top_pairs
is a full-universe cointegration scan and historically takes ~15-20 minutes,
so re-running the same window reuses the cached result instead of rescanning.

Each pair still runs as its own subprocess (~4s each observed) -- same
reason as the version this replaces: nautilus's BacktestEngine is not
documented as safe to instantiate repeatedly in one long-lived process, and
a subprocess crash on one pair (bad data, degenerate fit) can't take down
the rest of the batch. A pair whose subprocess errors, times out, or
produces no parseable balance is skipped (logged, batch continues) -- never
fatal to the batch.

Each subprocess writes its own trade log to a unique temp JSON path
(TRADE_LOG_OUTPUT_PATH env var -- see nautilus/run_backtest.py and
pairs_strategy.py's on_stop()) instead of the fixed
research/trade_log_dump.json a solo run uses, so pairs in the same batch
never clobber each other and a concurrent/later solo `python
nautilus/run_backtest.py` run is completely unaffected. Temp files are read
into the pool then deleted immediately -- no clutter left behind.

GAP_DAYS env var (optional, e.g. "2"): switches to gap-window evaluation --
same discovery (identical window, identical cache -- GAP_DAYS never affects
discovery), but the backtest window no longer ends at DISCOVERY_END_DATE; it
STARTS at DISCOVERY_END_DATE + GAP_DAYS days and runs forward LOOKBACK_DAYS
(via nautilus/run_backtest.py's BACKTEST_START_DATE, not BACKTEST_END_DATE),
so the strategy trades entirely on data discovery never saw, with GAP_DAYS
of buffer after discovery's own anchor. Unset (default): today's exact
behavior, unchanged -- BACKTEST_END_DATE, research/trade_pool.parquet. Set
(including "0"): writes to a SEPARATE file, research/trade_pool_gap.parquet,
with a gap_days column -- never touches the original pool, and "gap=0" under
this mechanism ([X, X+LOOKBACK_DAYS]) is NOT the same window as the original
pool's implicit gap=0 ([X-LOOKBACK_DAYS, X]) -- see the conversation this
was built from for why these aren't interchangeable.

Usage:
    .venv/bin/python scripts/batch_backtest.py
    DISCOVERY_END_DATE=2026-08-17 DISCOVERY_DAYS=30 .venv/bin/python scripts/batch_backtest.py
    DISCOVERY_END_DATE=2026-08-17 GAP_DAYS=2 .venv/bin/python scripts/batch_backtest.py

Writes:
  - research/discovery_cache/pairs_{end_date}_{days}d.csv  (cached discovery result;
    reused on a later run with the exact same end_date/days, GAP_DAYS or not)
  - research/trade_pool.parquet  (GAP_DAYS unset only -- cumulative pooled trades,
    read-existing, concat this batch's new rows, rewrite whole file; nothing dropped)
  - research/trade_pool_gap.parquet  (GAP_DAYS set only -- same append semantics,
    separate file, adds a gap_days column)
  - research/batch_backtest_results.csv  (per-pair summary, same shape/purpose
    as before -- quick human scan of return%/trade counts per pair; overwritten
    each run regardless of GAP_DAYS, so it always reflects the most recent run only)
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))  # must run before any `research.*` import below

from research.pair_analysis import analyze_top_pairs, get_tradeable_pairs  # noqa: E402
from research.data_loader import get_price_levels  # noqa: E402
from research.metrics import compute_metrics, format_report, normalize_trades  # noqa: E402

PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"
CAPITAL = 300.0  # must match nautilus/run_backtest.py's CAPITAL constant

DISCOVERY_CACHE_DIR = PROJECT_ROOT / "research" / "discovery_cache"
TRADE_POOL_PATH = PROJECT_ROOT / "research" / "trade_pool.parquet"
TRADE_POOL_GAP_PATH = PROJECT_ROOT / "research" / "trade_pool_gap.parquet"
RESULTS_CSV_PATH = PROJECT_ROOT / "research" / "batch_backtest_results.csv"
TMP_LOG_DIR = PROJECT_ROOT / "research" / "tmp_batch_trade_logs"

# Env var overrides, same style as nautilus/run_backtest.py's PAIR_A/PAIR_B --
# e.g. DISCOVERY_END_DATE=2026-08-17 DISCOVERY_DAYS=30 .venv/bin/python scripts/batch_backtest.py
# DISCOVERY_END_DATE unset (None) resolves to the true latest bar across the
# loaded universe (see _resolve_end_date) rather than staying an open-ended
# "latest" -- caching under a literal "latest" label would silently go stale
# every time new data lands (data refreshes every 12h -- scripts/update_data.sh).
# Resolving it once, up front, to a concrete timestamp makes the cache key
# (and the "same fixed historical window" every pair in this batch shares)
# unambiguous.
DISCOVERY_END_DATE = os.environ.get("DISCOVERY_END_DATE")
DISCOVERY_DAYS = int(os.environ.get("DISCOVERY_DAYS", "30"))
# None (unset) -- today's exact behavior, BACKTEST_END_DATE mechanism, research/trade_pool.parquet.
# Set (including "0") -- BACKTEST_START_DATE mechanism, research/trade_pool_gap.parquet. See
# module docstring for why these two are not the same "gap=0".
_gap_days_str = os.environ.get("GAP_DAYS")
GAP_DAYS = int(_gap_days_str) if _gap_days_str is not None else None

BALANCE_RE = re.compile(r"Account balance:\s*([\d.]+)")
CONFIG_RE = re.compile(r"^\[CONFIG\] (\{.*\})$", re.MULTILINE)


def _resolve_end_date(end_date: str | None) -> str:
    """None -> the true latest bar across the loaded universe, as an ISO
    date string. A caller-supplied end_date passes through unchanged.
    Mirrors research/run_all.py's own `true_max = get_price_levels(...).index.max()`
    pattern for resolving "now"."""
    if end_date is not None:
        return end_date
    
    true_max = get_price_levels(align=False).index.max()
    return str(true_max.date())


def _discovery_cache_path(end_date: str, days: int) -> Path:
    return DISCOVERY_CACHE_DIR / f"pairs_{end_date}_{days}d.csv"


def get_or_discover_pairs(end_date: str, days: int) -> pd.DataFrame:
    """Tradeable-pairs table for (end_date, days), from cache if present,
    otherwise a fresh call to analyze_top_pairs -> get_tradeable_pairs
    (cached afterward). Exact (end_date, days) match only -- no fuzzy reuse
    across nearby windows."""
    cache_path = _discovery_cache_path(end_date, days)
    if cache_path.exists():
        print(f"[INFO] Using cached discovery result: {cache_path}")
        return pd.read_csv(cache_path)

    print(f"[INFO] No cache for end_date={end_date} days={days} -- running discovery "
          f"(this is the full-universe cointegration scan; can take a while)...")
    
    summary = analyze_top_pairs(days=days, end_date=end_date)
    tradeable = get_tradeable_pairs(summary)

    DISCOVERY_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tradeable.to_csv(cache_path, index=False)
    print(f"[INFO] Cached {len(tradeable)} tradeable pairs to {cache_path}")
    return tradeable


def run_one(
    ticker_a: str, ticker_b: str, end_date: str, run_id: str,
    gap_days: int | None,
) -> tuple[dict, list[dict]]:
    """Runs one pair's backtest as a subprocess. Returns (summary_row, trades),
    where trades is the enriched list of trade records read from that pair's
    temp trade log (empty list if the pair produced zero completed trades,
    or if the subprocess failed/timed out/errored).

    gap_days=None: BACKTEST_END_DATE=end_date (today's exact behavior --
    window ends at end_date). gap_days=int: BACKTEST_START_DATE=end_date+gap_days
    (window starts gap_days after end_date instead) -- see module docstring."""
    env = os.environ.copy()
    env["PAIR_A"] = ticker_a
    env["PAIR_B"] = ticker_b
    if gap_days is None:
        env["BACKTEST_END_DATE"] = end_date
    else:
        start_date = pd.Timestamp(end_date) + pd.Timedelta(days=gap_days)
        env["BACKTEST_START_DATE"] = str(start_date.date())

    TMP_LOG_DIR.mkdir(parents=True, exist_ok=True)
    tmp_path = TMP_LOG_DIR / f"tmp_trade_log_{run_id}_{ticker_a}_{ticker_b}.json"
    env["TRADE_LOG_OUTPUT_PATH"] = str(tmp_path)

    try:
        result = subprocess.run(
            [str(PYTHON), "nautilus/run_backtest.py"],
            cwd=PROJECT_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        return {"ticker_a": ticker_a, "ticker_b": ticker_b, "status": "timeout"}, []

    if result.returncode != 0:
        # Keep the last line of stderr as a compact reason -- full output not
        # needed for a batch summary, just enough to tell failures apart.
        reason = result.stderr.strip().splitlines()[-1] if result.stderr.strip() else "unknown error"
        return {"ticker_a": ticker_a, "ticker_b": ticker_b, "status": "error", "error": reason}, []

    m = BALANCE_RE.search(result.stdout)
    if not m:
        return {"ticker_a": ticker_a, "ticker_b": ticker_b, "status": "no_balance_found"}, []
    balance = float(m.group(1))
    return_pct = round((balance - CAPITAL) / CAPITAL * 100, 2)

    cfg_match = CONFIG_RE.search(result.stdout)
    run_config = json.loads(cfg_match.group(1)) if cfg_match else {}

    # Read this pair's trade log (may not exist at all if the strategy
    # completed zero trades -- pairs_strategy.py's on_stop() returns before
    # writing anything in that case; that's a valid outcome, not an error).
    trades: list[dict] = []
    if tmp_path.exists():
        with open(tmp_path) as fh:
            trades = json.load(fh)
        tmp_path.unlink()  # no clutter left behind, per design

    for t in trades:
        t["run_id"] = run_id
        t["discovery_end_date"] = end_date
        t["discovery_days"] = DISCOVERY_DAYS
        t["gap_days"] = gap_days  # None for the original (BACKTEST_END_DATE) mechanism
        for cfg_key, cfg_val in run_config.items():
            t[f"cfg_{cfg_key}"] = cfg_val

    row = {
        "ticker_a": ticker_a, "ticker_b": ticker_b, "status": "ok",
        "final_balance": balance, "return_pct": return_pct,
        "n_trades": len(trades),
    }
    return row, trades


def append_to_pool(new_trades: list[dict], pool_path: Path) -> int:
    """Read-existing + concat + rewrite `pool_path` (either TRADE_POOL_PATH or
    TRADE_POOL_GAP_PATH, chosen by the caller based on GAP_DAYS). Returns the
    pool's total row count after appending. No-op (returns the existing
    count, or 0) if new_trades is empty -- an empty batch never touches the
    file on disk."""
    if not new_trades:
        if pool_path.exists():
            return len(pd.read_parquet(pool_path))
        return 0

    new_df = pd.DataFrame(new_trades)
    if pool_path.exists():
        existing = pd.read_parquet(pool_path)
        combined = pd.concat([existing, new_df], ignore_index=True)
    else:
        combined = new_df
    combined.to_parquet(pool_path, index=False)
    return len(combined)


if __name__ == "__main__":
    end_date = _resolve_end_date(DISCOVERY_END_DATE)
    days = DISCOVERY_DAYS
    pool_path = TRADE_POOL_PATH if GAP_DAYS is None else TRADE_POOL_GAP_PATH
    run_id = (
        f"{end_date}_{days}d_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        if GAP_DAYS is None else
        f"{end_date}_{days}d_gap{GAP_DAYS}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    )

    print(f"[INFO] Discovery window: end_date={end_date}, days={days}")
    if GAP_DAYS is not None:
        print(f"[INFO] GAP_DAYS={GAP_DAYS} -- evaluation window starts {GAP_DAYS}d after "
              f"end_date instead of ending at it. Writing to {pool_path}, NOT {TRADE_POOL_PATH}.")
    print(f"[INFO] run_id={run_id}")

    tradeable = get_or_discover_pairs(end_date, days)
    pairs = list(zip(tradeable["ticker_a"], tradeable["ticker_b"]))

    if not pairs:
        print("[INFO] No tradeable pairs for this window -- nothing to backtest.")
        sys.exit(0)

    # Say plainly whether these results are in-sample. The same-window default
    # is deliberate (see module docstring -- discovery needs a fixed window),
    # but the consequence is easy to forget when reading the metrics block at
    # the end: with GAP_DAYS unset the backtest window [end-LOOKBACK, end] sits
    # ENTIRELY INSIDE the discovery window [end-DISCOVERY_DAYS, end], so the
    # pairs were chosen using the same bars they are then scored on. A batch
    # was read as evidence of edge on exactly this confusion -- 90% win rate,
    # +41% on one pair -- before anyone re-checked which window was which.
    if GAP_DAYS is None:
        print("=" * 78)
        print(f"[WINDOW] IN-SAMPLE. Discovery window [{end_date} -{DISCOVERY_DAYS}d, "
              f"{end_date}] contains")
        print(f"[WINDOW] the backtest window, which also ends {end_date}. "
              "Pairs were selected")
        print("[WINDOW] using the bars they are scored on. Returns here are NOT evidence")
        print("[WINDOW] of out-of-sample edge. For a holdout, set an earlier")
        print("[WINDOW] DISCOVERY_END_DATE and GAP_DAYS=1.")
        print("=" * 78)
    else:
        start = pd.Timestamp(end_date) + pd.Timedelta(days=GAP_DAYS)
        print("=" * 78)
        print(f"[WINDOW] HOLDOUT. Discovery ends {end_date}; evaluation starts "
              f"{start.date()}")
        print(f"[WINDOW] ({GAP_DAYS}d gap) on data selection never saw. These returns "
              "are out-of-sample.")
        print("=" * 78)

    print(f"[INFO] Running {len(pairs)} backtests (CAPITAL={CAPITAL}, sequential, "
          f"same window end_date={end_date})...")

    rows = []
    all_trades: list[dict] = []
    for i, (a, b) in enumerate(pairs):
        row, trades = run_one(a, b, end_date, run_id, GAP_DAYS)
        rows.append(row)
        all_trades.extend(trades)
        status = row["status"]
        detail = (f"return={row.get('return_pct')}% n_trades={row.get('n_trades')}"
                  if status == "ok" else row.get("error", status))
        print(f"  [{i+1}/{len(pairs)}] {a}/{b}: {detail}")

    df = pd.DataFrame(rows)
    df.to_csv(RESULTS_CSV_PATH, index=False)
    print(f"\nWritten to {RESULTS_CSV_PATH}")

    ok = df[df["status"] == "ok"].sort_values("return_pct", ascending=False)
    failed = df[df["status"] != "ok"]
    print(f"\n{len(ok)} succeeded, {len(failed)} failed")
    print("\n=== Top 15 by return% ===")
    print(ok.head(15)[["ticker_a", "ticker_b", "return_pct", "n_trades"]].to_string(index=False))

    pool_size = append_to_pool(all_trades, pool_path)
    print(f"\n[INFO] Appended {len(all_trades)} trades from this batch to {pool_path}")
    print(f"[INFO] Pool now holds {pool_size} trades total (cumulative across all batches).")

    # This batch's own trades only (not the whole pool) -- pooled vs
    # per-pair-averaged, side by side, via research/metrics.py (the single
    # source of truth for these calculations; nothing computed inline here).
    if all_trades:
        batch_df = normalize_trades(pd.DataFrame(all_trades))
        report = compute_metrics(batch_df)
        print()
        print(format_report(report, title="=== This batch's metrics (pooled vs per-pair-avg) ==="))
    else:
        print("\n[INFO] No trades this batch -- nothing to report.")
