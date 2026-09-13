"""One scan cycle: refresh data, screen the universe, publish what is dislocated.

WHAT THIS IS, AND WHAT IT NO LONGER IS

It finds candidates. That is all it does now. It holds no positions, closes
nothing, and never writes the book -- `stop_monitor.py` owns all of that, because
the stop has to be watched between bars and a process that wakes every 30 minutes
cannot do it. See that module for why.

The split also removes a real hazard. Two processes appending to one ledger is
one of the two mechanisms that produce the corruption docs/HANDOFF.md records and
never explained. One writer removes it by construction.

SINGLE-SHOT BY DESIGN

A LaunchAgent (laptop) or a cron entry (VM) fires it every 30 minutes and it
exits. A long-lived process would have to survive sleep, network drops and memory
creep for weeks; one that starts, does a cycle and exits cannot leak, and a crash
costs one cycle rather than the run.

CYCLE COST, measured on this laptop:
    refresh 30m futures     ~80s   (the four-timeframe update_data.sh is 5m21s)
    load panel               ~2s
    scan 22,366 pairs        ~9s
    ------------------------------
    total                  ~100s   on a 30-minute clock, a 5% duty cycle

Usage:
    python research/live_scanner.py              # refresh data, then scan
    python research/live_scanner.py --no-refresh # scan whatever is on disk
    python research/live_scanner.py --dry-run    # scan and report, persist nothing
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import argparse
import json
import subprocess
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd

import book_state as cfg
from universe_panel import (load_panel, usable_tickers, tradeable_pairs,
                            drop_forming_bars)
from rolling_spread import min_bars_required
from scanner import scan, scan_summary

# How many candidates the monitor may choose from. It fills at most ten slots and
# the list is theta-ranked, so a hundred is far more than it can ever take -- the
# margin is there for pairs already held or blocked on concentration.
TOP_N_PUBLISHED = 100
TOP_N_DISPLAYED = 25

# Days of history to download. min_bars_required(0.5) is 671 bars = 14 days, so
# 30 leaves a fortnight of slack for gappy tickers. The laptop's research store
# keeps two years; this is deliberately not that.
REFRESH_DAYS = int(os.environ.get("PAIRS_REFRESH_DAYS", "30"))


def log(msg: str) -> None:
    line = f"{datetime.now(timezone.utc).isoformat(timespec='seconds')}  {msg}"
    print(line, flush=True)
    os.makedirs(os.path.dirname(cfg.SCANNER_LOG), exist_ok=True)
    with open(cfg.SCANNER_LOG, "a") as fh:
        fh.write(line + "\n")


def refresh_data(timeout_s: int = 900) -> bool:
    """Pull only the 30m futures candles.

    update_data.sh downloads four timeframes per ticker and takes 5m21s. The
    scanner reads only 30m futures, so asking for just that is roughly a quarter
    of the work -- the difference between a comfortable 30-minute cycle and a
    tight one.
    """
    cmd = ["docker", "compose", "run", "--rm", "freqtrade", "download-data",
           "--config", "user_data/config.json", "--exchange", "okx",
           "--trading-mode", "futures", "--timeframes", "30m",
           "--days", str(REFRESH_DAYS)]
    t0 = time.time()
    try:
        r = subprocess.run(cmd, cwd=cfg.PROJECT_ROOT, capture_output=True,
                           text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        log(f"data refresh TIMED OUT after {timeout_s}s — scanning stale data")
        return False
    except FileNotFoundError:
        log("docker not found — scanning whatever is already on disk")
        return False
    if r.returncode != 0:
        log(f"data refresh FAILED rc={r.returncode} — scanning stale data: "
            f"{r.stderr.strip().splitlines()[-1] if r.stderr.strip() else ''}")
        return False
    log(f"data refreshed in {time.time()-t0:.0f}s")
    return True


def _open_pairs() -> set:
    """Read the monitor's state READ-ONLY, for display only.

    Nothing here writes it. If the file is missing or mid-write the display just
    loses an annotation, which is why a failure is swallowed rather than raised.
    """
    try:
        with open(cfg.STATE_PATH) as fh:
            st = json.load(fh)
        return {(p["ticker_a"], p["ticker_b"]) for p in st.get("open_positions", [])}
    except (OSError, json.JSONDecodeError, KeyError):
        return set()


def write_candidates(cands: pd.DataFrame, bar_time) -> None:
    """Publish the ranked candidates at FULL precision, plus a readable view.

    The monitor sizes positions and places stops off these numbers, so the
    machine-readable block is never rounded. Rounding beta or sigma here would
    move a stop by an amount nobody could later account for. The rounded block is
    for `cat`, and is explicitly a different key.
    """
    held = _open_pairs()
    top = cands.head(TOP_N_PUBLISHED)

    machine = []
    for r in top.itertuples(index=False):
        machine.append({
            "ticker_a": r.ticker_a, "ticker_b": r.ticker_b,
            "entry_spread": float(r.entry_spread),
            "mu_at_entry": float(r.mu_at_entry),
            "sigma_at_entry": float(r.sigma_at_entry),
            "z_at_entry": float(r.z_at_entry),
            "beta_at_entry": float(r.beta_at_entry),
            "alpha_at_entry": float(r.alpha_at_entry),
            "theta_at_entry": (None if pd.isna(r.theta_at_entry)
                               else float(r.theta_at_entry)),
            "take_profit_level": float(r.take_profit_level),
            # Hedge quality. Recorded, never a gate -- but it has to travel with
            # the candidate or the monitor cannot put it on the ledger row, and
            # then "was this actually a pair trade" is unanswerable after the
            # fact. It was added to the signal and to the ledger schema on
            # 2026-09-13 and missed HERE, so the first positions under the new
            # schema carried a blank column.
            "r2_at_entry": (None if pd.isna(getattr(r, "r2_at_entry", float("nan")))
                            else float(r.r2_at_entry)),
        })

    display = []
    for r in top.head(TOP_N_DISPLAYED).itertuples(index=False):
        hl = (None if pd.isna(r.theta_at_entry)
              else round(float(np.log(2.0) / r.theta_at_entry), 2))
        display.append({
            "pair": f"{r.ticker_a}/{r.ticker_b}",
            "z": round(float(r.z_at_entry), 3),
            "theta": None if pd.isna(r.theta_at_entry) else round(float(r.theta_at_entry), 5),
            "half_life_hours": hl,
            "sigma": round(float(r.sigma_at_entry), 6),
            "already_open": (r.ticker_a, r.ticker_b) in held,
        })

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "bar_time": str(bar_time),
        "n_candidates": int(len(cands)),
        "n_ranked": int(cands["theta_at_entry"].notna().sum()) if len(cands) else 0,
        "candidates": machine,        # full precision — the monitor reads this
        "top_candidates": display,    # rounded — for humans
    }
    os.makedirs(cfg.DATA_DIR, exist_ok=True)
    tmp = cfg.CANDIDATES_PATH + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(payload, fh, indent=2)
    os.replace(tmp, cfg.CANDIDATES_PATH)   # atomic: never read half a file


def append_scan_history(cands: pd.DataFrame, bar_time) -> None:
    """One row per candidate per cycle, appended forever.

    scanner_candidates.json is overwritten every 30 minutes, so without this what
    the scanner saw is gone by the next cycle. With it, "what was dislocated at
    03:00 on the 14th, and why did we not take it" is answerable after the fact,
    and it reconciles against the monitor's trade ledger.

    This file belongs to the scanner and nothing else writes it, exactly as the
    ledger belongs to the monitor. Partitioned by day so it stays prunable.
    """
    if not len(cands):
        return
    os.makedirs(cfg.SCAN_HISTORY_DIR, exist_ok=True)
    d = cands.head(TOP_N_PUBLISHED).copy()
    d.insert(0, "bar_time", pd.Timestamp(bar_time))
    d.insert(1, "rank", range(1, len(d) + 1))
    day = pd.Timestamp(bar_time).strftime("%Y-%m-%d")
    path = os.path.join(cfg.SCAN_HISTORY_DIR, f"{day}.parquet")
    if os.path.exists(path):
        d = pd.concat([pd.read_parquet(path), d], ignore_index=True)
    d.to_parquet(path, index=False)

    # ~4,800 rows a day, forever, unless something deletes it. Cheap, but the VM
    # has an 11GB margin and nothing else is going to do this. Pruning here
    # rather than on a separate schedule keeps the rule next to the write.
    gone = cfg.prune_dated(cfg.SCAN_HISTORY_DIR, cfg.RETAIN_SCAN_HISTORY_DAYS)
    if gone:
        log(f"pruned {len(gone)} scan-history day(s) older than "
            f"{cfg.RETAIN_SCAN_HISTORY_DAYS}d")
    rotated = cfg.rotate_logs_in()
    if rotated:
        log(f"rotated at {cfg.LOG_MAX_BYTES // 1024 // 1024}MB: {', '.join(rotated)}")


def cycle(refresh: bool = True, dry_run: bool = False) -> pd.DataFrame:
    t0 = time.time()
    log("=== cycle start ===")
    if refresh:
        refresh_data()

    need = min_bars_required(cfg.BAR_HOURS)
    # Trim the still-forming bar BEFORE taking the tail. The newest bar is only
    # present for whichever instruments have ticked into it since it opened, and
    # using it both guts the universe and screens the survivors on a price that
    # is not a close. See universe_panel.drop_forming_bars.
    full = drop_forming_bars(load_panel(force=refresh))
    panel = full.tail(need)
    bar_time = panel.index[-1]
    age_min = (pd.Timestamp.utcnow().tz_localize(None) - bar_time).total_seconds() / 60
    log(f"panel {panel.shape[0]}x{panel.shape[1]} | last bar {bar_time} "
        f"({age_min:.0f} min old)")
    if age_min > 120:
        log(f"WARNING: data is {age_min:.0f} minutes stale — candidates may be wrong")

    tickers = usable_tickers(panel, cfg.BAR_HOURS)
    pairs = tradeable_pairs(tickers)

    t1 = time.time()
    cands = scan(panel, pairs, min_deviation_sigma=cfg.MIN_DEVIATION_SIGMA,
                 take_profit_pct=cfg.TAKE_PROFIT_PCT, bar_hours=cfg.BAR_HOURS)
    log(f"scan {len(pairs):,} pairs in {time.time()-t1:.1f}s — {scan_summary(cands)}")

    if not dry_run:
        write_candidates(cands, bar_time)
        append_scan_history(cands, bar_time)

    log(f"=== cycle done in {time.time()-t0:.0f}s ===")
    return cands


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-refresh", action="store_true",
                    help="skip the data download and scan what is on disk")
    ap.add_argument("--dry-run", action="store_true",
                    help="scan and report, but persist nothing")
    a = ap.parse_args()
    cycle(refresh=not a.no_refresh, dry_run=a.dry_run)
