"""Pull the 1-minute spread path of every backtested trade. Stage 1 of the exit study.

WHY THIS EXISTS

The exit rule is a pure function of the spread path and the levels frozen at
entry. No rolling statistic, no ranking, no slot arithmetic -- none of it changes
once a position is open. So the whole (stop width x debounce x entry grace) space
can be evaluated by walking a stored array, instead of re-running the engine once
per combination. 560 combinations is 28 hours of engine time and about a second
of arithmetic over these paths.

THE PATH RUNS TO THE TIME STOP, NOT TO THE ORIGINAL EXIT

This is the point that makes the study possible. A trade the original run stopped
after 40 minutes may, under a debounce, still be open hours later -- and scoring
that needs prices the original ledger never reached. So every path is extracted
from entry to entry + MAX_HOLD_HOURS, which is the longest any position can live
under any setting. Extracting only entry..exit would silently cap every tolerant
setting at the intolerant one's answer.

WHAT IS DELIBERATELY NOT DONE HERE

No exit rule is applied. This module extracts and stores; sweep_exits.py decides.
Keeping them apart means a change to the rule never triggers a re-extraction, and
the expensive half runs once.

GAPS STAY NaN. A minute where either leg did not trade is not forward-filled. A
carried price is one nobody traded at, and testing a stop against it is the same
stale-mark mistake the live monitor refuses to make.

Usage:
    python research/extract_paths.py --trades research/rank_experiment/w35_s05_actual.csv
"""
from __future__ import annotations

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import argparse

import numpy as np
import pandas as pd

import intrabar
import book_state as cfg

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(PROJECT_ROOT, "research", "exit_study", "paths.npz")


def extract(trades_path: str, max_hold_hours: float, timeframe: str = "1m",
            bar_hours: float = 0.5):
    d = pd.read_csv(trades_path)
    d["opened"] = pd.to_datetime(d.opened_at)
    d = d.sort_values("opened").reset_index(drop=True)

    need = sorted(set(d.ticker_a) | set(d.ticker_b))
    have = set(intrabar.available(timeframe))
    missing = [t for t in need if t not in have]
    if missing:
        # Dropping these silently would bias the study toward whatever the
        # download happened to finish first, which is alphabetical, not random.
        raise SystemExit(
            f"[FAIL] {len(missing)} of {len(need)} tickers have no {timeframe} data "
            f"({', '.join(missing[:8])}...). Finish the download first.")

    lo = d.opened.min()
    hi = d.opened.max() + pd.Timedelta(hours=max_hold_hours + bar_hours)
    print(f"[INFO] loading {timeframe} panel for {len(need)} tickers, {lo} .. {hi}")
    fine = intrabar.load_panel(need, start=lo, end=hi, timeframe=timeframe)
    if fine.index.tz is not None:
        # The ledger's timestamps are naive UTC; the feed's are aware. Same
        # instant either way -- reconcile once, here, rather than at every use.
        fine.index = fine.index.tz_convert("UTC").tz_localize(None)
    print(f"[INFO] {len(fine):,} minutes x {len(fine.columns)} tickers")

    # A dense minute grid, so a trade's path is a contiguous slice and a missing
    # minute is a NaN in place rather than a row that simply is not there.
    grid = pd.date_range(fine.index.min(), fine.index.max(), freq="1min")
    fine = fine.reindex(grid)
    t0 = grid[0]
    horizon = int(round(max_hold_hours * 60))

    # THE BAR IS LABELLED BY ITS OPEN, AND THE TRADE FILLS AT ITS CLOSE.
    #
    # A 30-minute bar stamped 14:30 spans 14:30..14:59 and its close is the last
    # minute in it, 14:59. The engine trades that close, but the ledger records
    # the trade at the bar's label, 14:30. So a path started at the label begins
    # 29 minutes BEFORE the position existed, and those 29 minutes of price
    # action get scored as if the trade had been open through them.
    #
    # Verified rather than assumed: the 1m spread matches the ledger's
    # entry_spread to a median of 0.0000 sigma at offset 29, against 0.88 sigma
    # at offset 0. Without this the autopsy counts pre-entry stop crossings and
    # reports negative lags -- the bar close appearing to precede the breach it
    # reacted to.
    bar_minutes = int(round(bar_hours * 60))
    fill_offset = bar_minutes - 1

    flat, starts, lens, keep = [], [], [], []
    total = 0
    truncated = 0
    for i, r in d.iterrows():
        a = fine[r.ticker_a].to_numpy(float)
        b = fine[r.ticker_b].to_numpy(float)
        i0 = int((r.opened - t0).total_seconds() // 60) + fill_offset
        i1 = min(i0 + horizon + 1, len(grid))
        if i0 < 0 or i1 - i0 < 2:
            continue
        sp = a[i0:i1] - float(r.beta_at_entry) * b[i0:i1] - float(r.alpha_at_entry)
        if i1 - i0 < horizon + 1:
            truncated += 1
        starts.append(total)
        lens.append(len(sp))
        total += len(sp)
        flat.append(sp)
        keep.append(i)
        if (len(keep) % 200) == 0:
            print(f"  {len(keep):,}/{len(d):,} paths")

    spreads = np.concatenate(flat) if flat else np.array([])
    meta = d.loc[keep].copy()
    meta["path_start"] = starts
    meta["path_len"] = lens
    print(f"[INFO] {len(keep):,} paths, {len(spreads):,} minutes total "
          f"({spreads.nbytes/1e6:.0f}MB)")
    print(f"[INFO] {truncated:,} paths truncated by the end of the data "
          f"({truncated/max(1,len(keep)):.0%}) — they cannot be scored beyond "
          f"their last minute and sweep_exits.py flags them")
    nan = float(np.isnan(spreads).mean())
    print(f"[INFO] {nan:.1%} of minutes are NaN (a leg did not trade) — skipped, never filled")
    return spreads, meta


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trades", required=True,
                    help="a backtest ledger; use the ACTUAL-fill run, not a modelled one")
    ap.add_argument("--hold", type=float, default=cfg.MAX_HOLD_HOURS)
    ap.add_argument("--bar-hours", type=float, default=cfg.BAR_HOURS)
    ap.add_argument("--timeframe", default="1m")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()

    spreads, meta = extract(a.trades, a.hold, a.timeframe, a.bar_hours)

    # Assert the alignment rather than trust it: if the fill offset is wrong the
    # paths silently describe a different trade and every number downstream is
    # quietly, plausibly false.
    st = meta.path_start.to_numpy(int)
    ent = meta.entry_spread.to_numpy(float)
    sg = meta.sigma_at_entry.to_numpy(float)
    err = np.array([abs(spreads[st[i]] - ent[i]) / sg[i] for i in range(len(meta))])
    err = err[np.isfinite(err)]
    print(f"[INFO] path[0] vs ledger entry_spread: median {np.median(err):.4f} sigma, "
          f"p95 {np.quantile(err, .95):.4f}")
    if np.median(err) > 0.01:
        raise SystemExit("[FAIL] paths are not aligned to the fill — check the bar offset")
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    np.savez_compressed(a.out, spreads=spreads)
    meta.to_parquet(a.out.replace(".npz", "_meta.parquet"))
    print(f"[INFO] -> {a.out}")
    print(f"[INFO] -> {a.out.replace('.npz', '_meta.parquet')}")


if __name__ == "__main__":
    main()
