"""What actually happened to every backtested trade, minute by minute.

The 30-minute backtest looks at 14:30, then 15:00. Everything between is
invisible to it, so a stop it books at 15:00 may have been crossed at 14:37 --
or crossed at 14:37, recovered by 14:50, and crossed again. The ledger cannot
tell those apart, and neither could we until the 1-minute history existed.

This describes, per trade:

  when the stop level was FIRST crossed, against when the bar close booked it
  how far past it went, and what a fill 0 / 5 / 15 / 30 minutes later would cost
  whether it came back inside, and how long each breach lasted
  whether the spread went on to reach mu, and when

It does NOT re-run the strategy, re-rank candidates, or model slots. These are
the trades that were taken; this is what happened to them.

THE QUESTION THAT MATTERS MOST is not about the losers. It is how many of the
backtest's WINNERS crossed the stop intrabar on their way to mu. Those are
trades the 30-minute engine kept because it was not looking, and a tick-speed
monitor would have killed. That number is the live book's missing take-profits.

Usage:
    python research/autopsy_stops.py
    python research/autopsy_stops.py --stop 1.0
"""
from __future__ import annotations

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import argparse

import numpy as np
import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATHS = os.path.join(PROJECT_ROOT, "research", "exit_study", "paths.npz")
DELAYS = (0, 5, 15, 30)


def one(path, entry, mu, direction, stop_dist, end=None):
    """Everything worth knowing about one trade's path. Minute 0 is the fill.

    `end` truncates the scan at the minute the trade actually closed. Without it
    a take-profit that reached mu at minute 50 and drifted past the stop at
    minute 600 -- long after it was flat -- would be counted as "crossed the stop
    on the way up", which it did not. That single omission inflated the headline
    winner-crossing rate from 43% to 60%.
    """
    if end is not None:
        path = path[:int(end) + 1]
    n = len(path)
    adverse = -direction * (path - entry)          # >0 = moved against us
    toward = direction * (path - mu)               # >=0 = reached mu
    breached = adverse >= stop_dist
    ok = np.isfinite(path)
    breached &= ok

    out = {
        "first_cross": -1, "n_breaches": 0, "first_breach_len": 0,
        "longest_breach": 0, "minutes_breached": int(breached[1:].sum()),
        "max_adverse_stops": float(np.nanmax(adverse[1:]) / stop_dist) if n > 1 else np.nan,
        "came_back": False, "reached_mu": -1,
    }
    for d in DELAYS:
        out[f"fill_{d}"] = np.nan

    idx = np.flatnonzero(breached[1:]) + 1
    if len(idx):
        out["first_cross"] = int(idx[0])
        # Contiguous runs of breach, separated by at least one minute inside.
        runs, start, prev = [], idx[0], idx[0]
        for i in idx[1:]:
            if i != prev + 1:
                runs.append((start, prev))
                start = i
            prev = i
        runs.append((start, prev))
        out["n_breaches"] = len(runs)
        out["first_breach_len"] = runs[0][1] - runs[0][0] + 1
        out["longest_breach"] = max(b - a + 1 for a, b in runs)
        out["came_back"] = runs[0][1] + 1 < n and np.any(ok[runs[0][1] + 1:])
        # What a fill costs if you act D minutes after the FIRST crossing.
        for d in DELAYS:
            j = out["first_cross"] + d
            if j < n and ok[j]:
                out[f"fill_{d}"] = float(adverse[j] / stop_dist)

    mu_idx = np.flatnonzero(ok[1:] & (toward[1:] >= 0)) + 1
    if len(mu_idx):
        out["reached_mu"] = int(mu_idx[0])
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--paths", default=PATHS)
    ap.add_argument("--stop", type=float, default=0.5,
                    help="stop width to measure breaches against")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    spreads = np.load(a.paths)["spreads"]
    m = pd.read_parquet(a.paths.replace(".npz", "_meta.parquet"))
    ent = m.entry_spread.to_numpy(float)
    mu = m.mu_at_entry.to_numpy(float)
    sg = m.sigma_at_entry.to_numpy(float)
    st = m.path_start.to_numpy(int)
    ln = m.path_len.to_numpy(int)
    dr = np.where(ent > mu, -1.0, 1.0)

    rows = []
    for i in range(len(m)):
        p = spreads[st[i]:st[i] + ln[i]]
        # TWO SCANS, because two different questions are being asked.
        #
        # Truncated at the close: "did this trade cross the stop WHILE IT WAS
        # OPEN". Scanning further would count a winner drifting past the level
        # hours after it was already flat.
        #
        # Full path: "what would have happened had we HELD". Truncating that one
        # censors exactly the evidence it needs -- every breach looks short
        # because the path ends, and every late fill looks cheap because only
        # the recovering trades survive to be measured.
        end = min(int(round(m.hours_held.iloc[i] * 60.0)), len(p) - 1)
        r = one(p, ent[i], mu[i], dr[i], a.stop * sg[i])          # full path
        held = one(p, ent[i], mu[i], dr[i], a.stop * sg[i], end=end)
        r["crossed_while_open"] = held["first_cross"] >= 0
        r["trade_num"] = m.trade_num.iloc[i]
        r["reason"] = m.exit_reason.iloc[i]
        r["booked_min"] = m.hours_held.iloc[i] * 60.0
        rows.append(r)
    d = pd.DataFrame(rows)
    d["lag"] = d.booked_min - d.first_cross

    W = 100
    print("=" * W)
    print(f"AUTOPSY — {len(d):,} backtested trades, stop measured at {a.stop} sigma")
    print("=" * W)
    print(d.reason.value_counts().to_string())

    print()
    print("=" * W)
    print("1. DID THE BACKTEST'S WINNERS CROSS THE STOP ON THE WAY UP?")
    print("=" * W)
    print("   A tick-speed monitor kills anything that touches the level. The 30-minute")
    print("   engine never saw these crossings, so it kept the trades and they reached mu.")
    print()
    for reason, g in d.groupby("reason"):
        crossed = g.crossed_while_open
        print(f"  {reason:<14} {len(g):5d} trades   crossed the stop intrabar: "
              f"{crossed.sum():5d} ({crossed.mean():5.1%})")
    tp = d[d.reason == "take_profit"]
    killed = tp.crossed_while_open.sum()
    print()
    print(f"  >>> {killed} of {len(tp)} take-profits ({killed/max(1,len(tp)):.0%}) touched the stop "
          f"before reaching mu.")
    print(f"      Watching every tick converts those to losses. That is the live book's")
    print(f"      missing take-profit rate, and it is not a coincidence.")

    print()
    print("=" * W)
    print("2. HOW LATE WAS THE BAR CLOSE?")
    print("=" * W)
    s = d[(d.reason == "adverse_move") & (d.first_cross >= 0)]
    print(f"  {len(s):,} stops with a detectable crossing")
    print(f"  lag from real crossing to the bar close that booked it:")
    for q in (.25, .5, .75, .9):
        print(f"    p{int(q*100):<3} {s.lag.quantile(q):6.1f} min")

    print()
    print("=" * W)
    print("3. WHAT A FILL COSTS, BY HOW LONG YOU WAIT AFTER THE CROSSING")
    print("=" * W)
    print("   In stop-distances. 1.00 = filled exactly at the level.")
    print()
    print(f"  {'wait':>6} {'median':>8} {'mean':>8} {'p90':>8}   n")
    for dl in DELAYS:
        c = s[f"fill_{dl}"].dropna()
        print(f"  {dl:>4}m  {c.median():8.3f} {c.mean():8.3f} {c.quantile(.9):8.3f}  {len(c):5d}")
    print()
    print("   measured live at ~100ms: 1.006x     measured at 30m bar close: 1.625x")

    print()
    print("=" * W)
    print("4. HOW LONG DOES A BREACH LAST? — this is the debounce answer")
    print("=" * W)
    b = d[d.first_cross >= 0]
    print(f"  {len(b):,} trades crossed the stop at some point.\n")
    print(f"  {'a debounce of':>14}  {'survives':>9}  {'of breaches':>12}")
    for w in (1, 2, 5, 10, 15, 20, 30, 45, 60):
        surv = (b.first_breach_len <= w).mean()
        print(f"  {w:>12}m  {surv:9.1%}  {'first breach ends within it':>12}")
    print()
    print("  first breach length (minutes):")
    for q in (.25, .5, .75, .9, .95):
        print(f"    p{int(q*100):<3} {b.first_breach_len.quantile(q):6.0f}")
    print(f"  came back inside at all: {b.came_back.mean():.1%}")
    print(f"  crossed more than once : {(b.n_breaches > 1).mean():.1%}")

    print()
    print("=" * W)
    print("5. OF THE TRADES THAT CROSSED, HOW MANY STILL REACHED mu?")
    print("=" * W)
    got = b.reached_mu >= 0
    print(f"  {got.sum():,} of {len(b):,} ({got.mean():.1%}) reached mu within 72h despite crossing")
    late = b[got & (b.reached_mu > b.first_cross)]
    print(f"  {len(late):,} reached it AFTER the crossing — these are the rescuable trades")
    if len(late):
        wait = late.reached_mu - late.first_cross
        print(f"  time from crossing to mu: median {wait.median():.0f} min, "
              f"p75 {wait.quantile(.75):.0f}, p90 {wait.quantile(.9):.0f}")

    if a.out:
        d.to_csv(a.out, index=False)
        print(f"\n[INFO] -> {a.out}")
    print()
    print("=" * W)


if __name__ == "__main__":
    main()
