"""Autopsy the live book's stop-outs. Sections E and A of the stop investigation.

E -- ENTRY TIMING. Candidates are chosen at a 30-minute bar close and filled a
moment later at the live mid. `entry_bar_z` is where the spread was when the
scanner picked it; `entry_fill_z` is where it was when we actually got in. If
|fill| > |bar| the spread kept WIDENING while we were deciding -- we bought into
momentum, not reversion. If the losers systematically show that and the winners
do not, the problem is the entry, not the stop, and no amount of stop tuning
fixes it.

A -- TIME TO STOP. Live stops die at a median 16 minutes; the bar-close backtest
took 2 hours. If most deaths land inside the first half hour the stop is firing
on entry noise rather than on the trade being wrong, and the lever is an entry
grace period, not a wider stop.

THE SAMPLE IS SMALL AND THE COMPARISON IS LOPSIDED. Every close so far is a stop,
so there are no realized winners to compare against. The open book stands in for
them, scored at its current unrealized R. That is a legitimate contrast -- those
positions are alive and mostly profitable -- but it is a snapshot, not an
outcome, and this script says so rather than quietly treating it as one.

Run: python research/analyse_stops.py
"""
from __future__ import annotations

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json

import numpy as np
import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(PROJECT_ROOT, "research", "from_vm", "scanner_trades.csv")
POSITIONS = os.path.join(PROJECT_ROOT, "research", "from_vm", "open_positions.json")

W = 100


def rule(title: str = "") -> None:
    print("=" * W)
    if title:
        print(title)
        print("=" * W)


def load() -> tuple[pd.DataFrame, pd.DataFrame]:
    d = pd.read_csv(LEDGER)
    o = d[d.event.eq("open")].set_index("trade_num")
    c = d[d.event.eq("close")].set_index("trade_num")
    # book_reset rows are bookkeeping from an archived book, not trade outcomes.
    c = c[~c.exit_reason.eq("book_reset")]
    return o, c


def open_marks() -> dict:
    """Current unrealized R per open trade, from the monitor's last heartbeat."""
    try:
        with open(POSITIONS) as fh:
            return {p["trade_num"]: p for p in json.load(fh).get("positions", [])}
    except (OSError, json.JSONDecodeError, KeyError):
        return {}


def main() -> None:
    o, c = load()
    marks = open_marks()
    live_ids = [t for t in o.index if t not in c.index]

    # drift is signed in the direction of the TRADE, not of the spread: positive
    # means the spread moved further from mu between bar close and fill, which is
    # the direction that hurts, whichever side we are on.
    o = o.copy()
    o["drift_sigma"] = (o.entry_fill_z.abs() - o.entry_bar_z.abs())
    o["outcome"] = ["stopped" if t in c.index else "open" for t in o.index]
    o["R"] = [
        (c.loc[t, "r"] if t in c.index
         else marks.get(t, {}).get("unrealized_r", np.nan))
        for t in o.index
    ]

    rule("E — ENTRY TIMING: did the spread widen between the bar close and our fill?")
    print("  drift = |z at fill| - |z at bar close|, in sigma.")
    print("  positive = it kept moving AWAY from mu while we decided (we chased)")
    print("  negative = it had already started reverting before we got in\n")

    show = o[["ticker_a", "ticker_b", "entry_bar_z", "entry_fill_z",
              "drift_sigma", "outcome", "R"]].copy()
    show = show.sort_values("drift_sigma", ascending=False)
    print(show.to_string(float_format=lambda x: f"{x:+.3f}"))

    print()
    g = o.groupby("outcome").drift_sigma
    print("  drift by outcome")
    print(f"    {'':10s} {'n':>4s} {'mean':>8s} {'median':>8s} {'chased':>8s}")
    for name, s in g:
        chased = (s > 0).mean()
        print(f"    {name:10s} {len(s):4d} {s.mean():+8.3f} {s.median():+8.3f} {chased:7.0%}")

    both = o.dropna(subset=["drift_sigma", "R"])
    if len(both) > 2:
        r = np.corrcoef(both.drift_sigma, both.R)[0, 1]
        print(f"\n  corr(drift, R) = {r:+.3f}   "
              f"(negative = chasing costs money; n={len(both)}, far too few to be significant)")

    print()
    rule("A — TIME TO STOP: how long does a losing trade take to die?")
    if not len(c):
        print("  no closes yet")
        return

    h = c.hours_held.sort_values()
    print(f"  {len(h)} stops   median {h.median()*60:.0f} min   "
          f"mean {h.mean()*60:.0f} min   max {h.max():.1f} h\n")

    buckets = [(0, 0.25, "under 15 min"), (0.25, 0.5, "15-30 min"),
               (0.5, 1, "30-60 min"), (1, 3, "1-3 h"),
               (3, 6, "3-6 h"), (6, 1e9, "over 6 h")]
    print(f"  {'bucket':>14s} {'n':>4s} {'share':>7s} {'P&L $':>9s} {'mean R':>8s}   bar")
    for lo, hi, name in buckets:
        m = c[(c.hours_held >= lo) & (c.hours_held < hi)]
        if not len(m):
            continue
        print(f"  {name:>14s} {len(m):4d} {len(m)/len(c):6.0%} "
              f"{m.realized_pnl_net.sum():+9.2f} {m.r.mean():+8.3f}   "
              + "#" * len(m))

    fast = c[c.hours_held < 0.5]
    print(f"\n  dead inside 30 min: {len(fast)} of {len(c)} "
          f"({len(fast)/len(c):.0%}), {fast.realized_pnl_net.sum():+.2f} "
          f"of {c.realized_pnl_net.sum():+.2f} realized")

    print()
    print("  the open book, for contrast — these are the ones that survived the first hour")
    if live_ids:
        alive = o.loc[live_ids, ["ticker_a", "ticker_b", "R"]].copy()
        held = [marks.get(t, {}).get("hours_held", np.nan) for t in live_ids]
        alive["hours"] = held
        alive = alive.sort_values("hours")
        print("    " + alive.to_string(float_format=lambda x: f"{x:+.2f}").replace("\n", "\n    "))
        rr = alive.R.dropna()
        if len(rr):
            print(f"\n    {len(rr)} open, mean R {rr.mean():+.3f}, "
                  f"{(rr > 0).sum()} of {len(rr)} in profit  "
                  f"(UNREALIZED — a snapshot, not an outcome)")

    print()
    rule()


if __name__ == "__main__":
    main()
