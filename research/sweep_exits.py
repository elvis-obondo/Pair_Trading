"""Walk the stop-width x debounce x entry-grace surface over stored 1m paths.

WHY R IS NOT THE METRIC HERE

R is P&L divided by the stop distance, and the stop distance is one of the things
being swept. Double the stop and every R in the book halves, with no change to a
single dollar earned. So R cannot compare settings of different width -- it is
measuring them in different units. This ranks on ret_gross -- realised dollars
over the gross notional at risk -- which is the same quantity at every width and
at every account size, and reports R alongside only at a fixed 0.5-sigma
reference so the numbers stay readable next to the existing results.

A SECOND REASON NOT TO RANK ON net_pct. Position.pnl charges
ROUND_TRIP_COST_FRAC against the spread move, which scales with leg A's
notional, while the constant is defined as a fraction of GROSS notional --
about twice as large. Measured on this ledger it charges 0.0993% where 0.1852%
was paid, so net_pct and every R built on it flatter each trade by roughly 0.09%
of notional. net_pct is still reported, unchanged, because every settled number
in this project uses it and they have to remain comparable.

THE THREE KNOBS, AND WHY GRACE IS NOT A DEBOUNCE

  stop width    how far the spread must move against entry before the stop exists
  debounce      how long a breach must PERSIST before it fires; the clock resets
                the moment the spread comes back inside
  entry grace   a window from ENTRY during which the stop cannot fire at all

Grace is separate because the live book's losses are front-loaded -- half its
stops land within 15 minutes of entry, which the bar-close backtest structurally
cannot do (its minimum hold is exactly 30 minutes). If that is the spread still
moving as we fill, grace removes it without loosening the stop for the rest of
the trade's life. A debounce loosens it everywhere, forever.

A debounce should also BEAT the bar-close behaviour it resembles rather than
merely copy it. Bar-close takes one sample every 30 minutes, so a trade breached
at 14:59 that recovers at 15:01 lives or dies on where the sample happens to
land. A debounce reads every minute and asks whether the breach held. Same
tolerance, strictly more information.

WHAT THIS CANNOT ANSWER

Slot contention. A trade a debounce keeps alive occupies a slot, and some later
entry the real book would have taken never happens. These are per-trade
economics with the portfolio removed. Use it to find candidates, then confirm the
shortlist in the engine -- that is stage 2 and there is no shortcut to it.

Usage:
    python research/sweep_exits.py
    python research/sweep_exits.py --top 20
"""
from __future__ import annotations

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import argparse
import itertools

import numpy as np
import pandas as pd

import book_state as cfg
from portfolio import ROUND_TRIP_COST_FRAC

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATHS = os.path.join(PROJECT_ROOT, "research", "exit_study", "paths.npz")

STOP_WIDTHS = (0.5, 0.75, 1.0, 1.5)
DEBOUNCES = (0, 5, 10, 15, 20, 25, 30)
GRACES = (0, 15, 30, 45, 60)

REASON = {0: "open_at_end", 1: "adverse_move", 2: "take_profit", 3: "time_stop"}


def walk(path, entry, mu, direction, stop_dist, debounce, grace, horizon):
    """First exit along one path. Returns (minute, spread, reason code).

    Minute 0 is entry and is never an exit: the position is opened there.
    """
    n = len(path)
    breach_at = -1
    for t in range(1, n):
        sp = path[t]
        if sp != sp:                      # NaN: a leg did not trade this minute
            continue                      # never decide on a price nobody made
        if t >= horizon:
            return t, sp, 3
        # Take profit is never debounced or graced -- a full reversion to mu is
        # the outcome the trade exists for, and waiting only risks giving it back.
        #
        # direction is -1 when SHORT the spread (entry above mu), so profit is
        # the spread falling: direction*(sp-mu) turns positive exactly when the
        # spread has reached mu from whichever side it started. The level is mu
        # because TAKE_PROFIT_PCT is 1.0; at any other setting this would need
        # take_profit_level from the ledger instead.
        if direction * (sp - mu) >= 0.0:
            return t, sp, 2
        if t < grace:
            breach_at = -1
            continue
        if direction * (sp - entry) <= -stop_dist:
            if breach_at < 0:
                breach_at = t
            if t - breach_at >= debounce:
                return t, sp, 1
        else:
            breach_at = -1
    return n - 1, path[n - 1], 0


def score(spreads, meta, stop_sigma, debounce, grace, horizon):
    n = len(meta)
    ex_t = np.empty(n); ex_s = np.empty(n); ex_r = np.empty(n, int)
    ent = meta.entry_spread.to_numpy(float)
    mu = meta.mu_at_entry.to_numpy(float)
    sg = meta.sigma_at_entry.to_numpy(float)
    st = meta.path_start.to_numpy(int)
    ln = meta.path_len.to_numpy(int)
    # direction: short the spread when entry sits above mu, long it when below --
    # Position.direction, reproduced rather than re-derived.
    dr = np.where(ent > mu, -1.0, 1.0)
    for i in range(n):
        p = spreads[st[i]:st[i] + ln[i]]
        ex_t[i], ex_s[i], ex_r[i] = walk(
            p, ent[i], mu[i], dr[i], stop_sigma * sg[i], debounce, grace, horizon)

    move = dr * (ex_s - ent)
    leg_a = meta.leg_a_notional.to_numpy(float)
    gross = meta.gross_notional.to_numpy(float)
    dollars = move * leg_a - ROUND_TRIP_COST_FRAC * gross

    # TWO RETURN MEASURES, because the project's own two disagree.
    #
    # net_pct is Position.pnl's definition, reproduced exactly so these numbers
    # sit beside every existing result. It charges ROUND_TRIP_COST_FRAC against
    # the MOVE, which scales with leg A's notional -- but the constant is defined
    # as a fraction of GROSS notional, roughly twice as large. Measured on this
    # ledger: it charges 0.0993% where 0.1852% was actually paid. So net_pct, and
    # every R derived from it, flatters each trade by about 0.09% of notional.
    #
    # ret_gross is the honest one: realised dollars over the gross notional at
    # risk. Size independent, so it compares trades opened at $300 and $5,000,
    # and it charges the cost that was actually paid. Rank on this.
    net_pct = (move - ROUND_TRIP_COST_FRAC) * 100.0
    ret_gross = dollars / gross * 100.0
    return pd.DataFrame({
        "trade_num": meta.trade_num.to_numpy(),
        "exit_min": ex_t, "exit_spread": ex_s,
        "reason": [REASON[c] for c in ex_r],
        "ret_gross": ret_gross, "net_pct": net_pct, "dollars": dollars,
        # R at a FIXED 0.5-sigma reference, so it is comparable across widths.
        "r_ref": net_pct / (100.0 * sg * 0.5),
        "truncated": ln < horizon + 1,
    })


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--paths", default=PATHS)
    ap.add_argument("--hold", type=float, default=cfg.MAX_HOLD_HOURS)
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    spreads = np.load(a.paths)["spreads"]
    meta = pd.read_parquet(a.paths.replace(".npz", "_meta.parquet"))
    horizon = int(round(a.hold * 60))
    print(f"[INFO] {len(meta):,} trades, {len(spreads):,} minutes of path")
    print(f"[INFO] {len(STOP_WIDTHS)*len(DEBOUNCES)*len(GRACES)} combinations\n")

    rows = []
    for k, (sw, db, gr) in enumerate(itertools.product(STOP_WIDTHS, DEBOUNCES, GRACES), 1):
        t = score(spreads, meta, sw, db, gr, horizon)
        tp = (t.reason == "take_profit").mean()
        rows.append({
            "stop": sw, "debounce": db, "grace": gr,
            "ret_gross": t.ret_gross.mean(), "net_pct": t.net_pct.mean(),
            "r_ref": t.r_ref.mean(), "tp_rate": tp,
            "stop_rate": (t.reason == "adverse_move").mean(),
            "open_at_end": (t.reason == "open_at_end").mean(),
            "median_hold_h": t.exit_min.median() / 60.0,
            "win_rate": (t.net_pct > 0).mean(),
        })
        if k % 40 == 0:
            print(f"  {k}/{len(STOP_WIDTHS)*len(DEBOUNCES)*len(GRACES)}")

    res = pd.DataFrame(rows).sort_values("ret_gross", ascending=False)
    print()
    print("=" * 110)
    print(f"TOP {a.top} BY MEAN ret_gross — realised dollars over gross notional, the honest measure.")
    print("net_pct is Position.pnl's definition, kept for comparability; it undercharges cost ~2x.")
    print("=" * 110)
    print(res.head(a.top).to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print()
    print("BASELINE — the settings each run used")
    base = res[(res.debounce == 0) & (res.grace == 0)]
    print(base.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    if a.out:
        res.to_csv(a.out, index=False)
        print(f"\n[INFO] -> {a.out}")


if __name__ == "__main__":
    main()
