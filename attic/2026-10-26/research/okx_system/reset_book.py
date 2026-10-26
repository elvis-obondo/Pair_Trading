"""Archive the live book and start a new one flat. Driven by scripts/reset_book.sh.

Runs inside the container so it sees the same paths the monitor does. The
monitor MUST be stopped first -- it is the only writer of the ledger and the
state file, and this moves both.

See scripts/reset_book.sh for why a reset is ever the right answer and what is
deliberately kept.

Usage:
    python research/reset_book.py --report     # what is in the book now
    python research/reset_book.py --dry-run
    python research/reset_book.py
"""
from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import argparse
import json
import math
import shutil
from datetime import datetime, timezone

import pandas as pd

import book_state as cfg

ARCHIVE_DIR = os.path.join(cfg.DATA_DIR, "archive")


def read_state() -> dict:
    try:
        with open(cfg.STATE_PATH) as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {"equity": cfg.ACCOUNT_EQUITY, "next_trade_num": 1, "open_positions": []}


def report() -> None:
    st = read_state()
    print(f"  equity          {st.get('equity', 0):.2f}")
    print(f"  open positions  {len(st.get('open_positions', []))}")
    print(f"  next trade num  {st.get('next_trade_num', 1)}")
    try:
        d = pd.read_csv(cfg.LEDGER_PATH)
        c = d[d.event.eq("close")]
        print(f"  ledger rows     {len(d)}  ({(d.event == 'open').sum()} opens, {len(c)} closes)")
        if len(c):
            print(f"  realized        {c.realized_pnl_net.sum():+.2f}")
            adv = c[c.exit_reason.eq("adverse_move")]
            if len(adv) and "overshoot_ratio" in adv:
                o = adv.overshoot_ratio.dropna()
                if len(o):
                    print(f"  overshoot       median {o.median():.3f}x over {len(o)} stop-outs"
                          f"   (POOLS across the reset — exit-side)")
    except (OSError, pd.errors.EmptyDataError):
        print("  ledger          empty")
    try:
        print(f"  equity curve    {sum(1 for _ in open(cfg.EQUITY_PATH)) - 1:,} rows")
    except OSError:
        print("  equity curve    empty")


def close_open_positions(stamp: str) -> list:
    """Book every open position at its last recorded mark, reason=book_reset.

    Marks come from open_positions.json, which the monitor wrote on its final
    heartbeat. A position it could not mark (blind) is booked at zero P&L rather
    than guessed at -- a made-up number in the ledger is worse than a flat one,
    and the reason column says it was a reset either way.
    """
    st = read_state()
    positions = st.get("open_positions", [])
    if not positions:
        return []

    marks = {}
    try:
        with open(cfg.POSITIONS_PATH) as fh:
            for p in json.load(fh).get("positions", []):
                marks[p["trade_num"]] = p
    except (OSError, json.JSONDecodeError):
        pass

    rows = []
    for p in positions:
        m = marks.get(p["trade_num"], {})
        pnl = m.get("unrealized_pnl")
        rows.append({
            "event": "close", "trade_num": p["trade_num"],
            "ticker_a": p["ticker_a"], "ticker_b": p["ticker_b"],
            "time": stamp, "opened_at": p["opened_at"], "closed_at": stamp,
            "exit_reason": "book_reset",
            "hours_held": m.get("hours_held"),
            "exit_spread": m.get("spread"),
            "realized_pnl_net": 0.0 if pnl is None else pnl,
            "net_pct": m.get("unrealized_pct"),
            "r": m.get("unrealized_r"),
            "feed_state": "blind_at_reset" if pnl is None else m.get("feed_state"),
            **p.get("signal", {}), **p.get("sizing", {}),
        })
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    if a.report:
        report()
        return

    stamp = datetime.now(timezone.utc)
    tag = stamp.strftime("%Y%m%dT%H%M%SZ")
    dest = os.path.join(ARCHIVE_DIR, tag)

    closed = close_open_positions(stamp.isoformat())
    print(f"  booking {len(closed)} open position(s) as book_reset")
    for r in closed:
        print(f"    #{r['trade_num']:<4} {r['ticker_a']}/{r['ticker_b']:<10} "
              f"{r['realized_pnl_net']:+8.2f}"
              + ("   (blind — booked flat)" if r["feed_state"] == "blind_at_reset" else ""))

    if a.dry_run:
        print(f"\n  would archive to {dest}")
        print("  would reset equity to "
              f"{cfg.ACCOUNT_EQUITY:.2f}, trade numbering to 1")
        print("  dry run — nothing written")
        return

    # Write the closes BEFORE archiving, so the archived ledger is complete.
    if closed:
        cfg.append_ledger(closed)

    os.makedirs(dest, exist_ok=True)
    moved = []
    for path in (cfg.LEDGER_PATH, cfg.STATE_PATH, cfg.EQUITY_PATH,
                 cfg.POSITIONS_PATH, cfg.CONSUMED_PATH):
        if os.path.exists(path):
            shutil.move(path, os.path.join(dest, os.path.basename(path)))
            moved.append(os.path.basename(path))
    print(f"\n  archived to {dest}")
    print(f"    {', '.join(moved)}")

    # Pre-create the ledger as a real FILE. docker-compose bind-mounts a missing
    # file path as an empty DIRECTORY rather than erroring, and the monitor then
    # crash-loops on the next restart.
    open(cfg.LEDGER_PATH, "a").close()
    with open(cfg.STATE_PATH, "w") as fh:
        json.dump({"saved_at": stamp.isoformat(), "equity": cfg.ACCOUNT_EQUITY,
                   "next_trade_num": 1, "open_positions": []}, fh, indent=1)

    print(f"  new book: equity {cfg.ACCOUNT_EQUITY:.2f}, flat, trade numbering from 1")
    print("  monitor_ticks/ kept — the new curve backfills from its first position")


if __name__ == "__main__":
    main()
