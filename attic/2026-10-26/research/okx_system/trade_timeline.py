"""Every trade's full life at 1-minute resolution. No verdicts, just the record.

WHAT THIS IS FOR

The sweep answers "which rule pays best" and throws the trades away. This throws
the rule away and keeps the trades. One row per position, carrying when it
crossed the stop, how many times, how long it stayed out, when it reached mu, and
what it was still worth at the 72-hour horizon.

THE PATH RUNS TO THE HORIZON, NOT TO THE ENGINE'S EXIT

Every crossing column is measured over the FULL 72 hours, including the part
after the engine closed the position. That is deliberate: the question is what
the spread did, not what the current rule saw. Columns describing what the engine
actually did are prefixed `eng_` so the two can never be confused.

`autopsy_stops.py` does the opposite -- it truncates at the real exit, because it
is asking what the rule experienced. Both are right for their own question. Where
they disagree on a number, that is why.

GAPS STAY NaN. A minute where either leg did not trade is not forward-filled, so
a crossing is never credited to a price nobody made.

Usage:
    python research/trade_timeline.py
    python research/trade_timeline.py --stop 1.0 --detail 20
"""
from __future__ import annotations

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import argparse

import numpy as np
import pandas as pd

import book_state as cfg
from portfolio import ROUND_TRIP_COST_FRAC

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATHS = os.path.join(PROJECT_ROOT, "research", "exit_study", "paths.npz")
META = os.path.join(PROJECT_ROOT, "research", "exit_study", "paths_meta.parquet")
OUT = os.path.join(PROJECT_ROOT, "research", "exit_study", "timeline.csv")


def runs_of(idx: np.ndarray):
    """Contiguous runs in a sorted index array, as (start, end) inclusive."""
    if not len(idx):
        return []
    out, start, prev = [], idx[0], idx[0]
    for i in idx[1:]:
        if i != prev + 1:
            out.append((start, prev))
            start = i
        prev = i
    out.append((start, prev))
    return out


def timeline(path, entry, mu, sigma, direction, stop_sigma, leg_a, gross, margin):
    """One trade, start to horizon."""
    n = len(path)
    ok = np.isfinite(path)
    adverse = -direction * (path - entry)       # >0 moved against us, spread units
    favour = direction * (path - entry)         # >0 moved our way
    toward = direction * (path - mu)            # >=0 has reached mu
    stop_dist = stop_sigma * sigma

    r = {
        "path_minutes": n - 1,
        "gap_minutes": int((~ok).sum()),
        # --- the stop level, and every time the spread was beyond it ---
        "stop_level_sigma": stop_sigma,
        "first_cross_min": -1, "n_crossings": 0,
        "minutes_beyond_stop": 0, "longest_breach_min": 0,
        "back_inside_min": -1,
        # --- how far it ever went, either way ---
        "max_adverse_sigma": float(np.nanmax(adverse[1:]) / sigma) if n > 1 else np.nan,
        "max_adverse_min": -1,
        "max_favour_sigma": float(np.nanmax(favour[1:]) / sigma) if n > 1 else np.nan,
        "max_favour_min": -1,
        # --- mu ---
        "reached_mu": False, "first_mu_min": -1,
        "mu_before_cross": False, "cross_to_mu_min": -1,
        # --- margin ---
        "max_drawdown_usd": float(np.nanmax(adverse[1:]) * abs(leg_a)) if n > 1 else np.nan,
        "margin_usd": float(margin), "liquidated": False, "liquidated_min": -1,
    }
    if n > 1:
        r["max_adverse_min"] = int(np.nanargmax(np.where(ok[1:], adverse[1:], -np.inf)) + 1)
        r["max_favour_min"] = int(np.nanargmax(np.where(ok[1:], favour[1:], -np.inf)) + 1)

    beyond = np.flatnonzero((adverse[1:] >= stop_dist) & ok[1:]) + 1
    if len(beyond):
        rr = runs_of(beyond)
        r["first_cross_min"] = int(beyond[0])
        r["n_crossings"] = len(rr)
        r["minutes_beyond_stop"] = int(len(beyond))
        r["longest_breach_min"] = int(max(b - a + 1 for a, b in rr))
        # First minute at or after the first crossing that is back inside the
        # level. Measured from the crossing, which is what a debounce would time.
        fc = r["first_cross_min"]
        inside = np.flatnonzero(ok[fc:] & (adverse[fc:] < stop_dist))
        r["back_inside_min"] = int(inside[0]) if len(inside) else -1

    mu_idx = np.flatnonzero(ok[1:] & (toward[1:] >= 0)) + 1
    if len(mu_idx):
        r["reached_mu"] = True
        r["first_mu_min"] = int(mu_idx[0])
        if r["first_cross_min"] >= 0:
            r["mu_before_cross"] = mu_idx[0] < r["first_cross_min"]
            after = mu_idx[mu_idx > r["first_cross_min"]]
            if len(after):
                r["cross_to_mu_min"] = int(after[0] - r["first_cross_min"])
        else:
            r["mu_before_cross"] = True

    liq = np.flatnonzero(ok[1:] & (adverse[1:] * abs(leg_a) > margin)) + 1
    if len(liq):
        r["liquidated"] = True
        r["liquidated_min"] = int(liq[0])

    # What the position was worth at the horizon with no rule acting at all.
    good = path[ok]
    if len(good):
        move = direction * (good[-1] - entry)
        r["ret_gross_at_horizon"] = (move * leg_a - ROUND_TRIP_COST_FRAC * gross) / gross * 100
    else:
        r["ret_gross_at_horizon"] = np.nan
    return r


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--paths", default=PATHS)
    ap.add_argument("--meta", default=META)
    # 0.5, NOT cfg.STOP_SIGMA. The live book runs 1.0 as an experiment, but these
    # trades were generated at 0.5 and the crossings have to be measured against
    # the level the engine actually used, or the record describes a book that
    # never existed. Pass --stop to ask a what-if.
    ap.add_argument("--stop", type=float, default=0.5)
    ap.add_argument("--detail", type=int, default=12, help="trades to print in full")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()

    meta = pd.read_parquet(a.meta)
    spreads = np.load(a.paths)["spreads"]
    ent = meta.entry_spread.to_numpy(float)
    mu = meta.mu_at_entry.to_numpy(float)
    sg = meta.sigma_at_entry.to_numpy(float)
    st = meta.path_start.to_numpy(int)
    ln = meta.path_len.to_numpy(int)
    dr = np.where(ent > mu, -1.0, 1.0)
    leg_a = meta.leg_a_notional.to_numpy(float)
    gross = meta.gross_notional.to_numpy(float)
    marg = meta.margin.to_numpy(float)

    print(f"[INFO] {len(meta):,} trades | stop {a.stop} sigma | paths run to "
          f"{cfg.MAX_HOLD_HOURS:.0f}h regardless of when the engine closed")

    rows = [timeline(spreads[st[i]:st[i] + ln[i]], ent[i], mu[i], sg[i], dr[i],
                     a.stop, leg_a[i], gross[i], marg[i]) for i in range(len(meta))]
    t = pd.DataFrame(rows)

    keep = ["trade_num", "ticker_a", "ticker_b", "opened_at", "closed_at",
            "hours_held", "exit_reason", "z_at_entry", "beta_at_entry",
            "theta_at_entry", "sigma_at_entry", "entry_spread", "mu_at_entry",
            "leg_a_notional", "gross_notional", "realized_pnl_net"]
    head = meta[keep].rename(columns={
        "closed_at": "eng_closed_at", "hours_held": "eng_hours_held",
        "exit_reason": "eng_exit_reason", "realized_pnl_net": "eng_pnl_usd"})
    head["direction"] = np.where(dr < 0, "short_spread", "long_spread")
    out = pd.concat([head, t], axis=1)
    out.to_csv(a.out, index=False)
    print(f"[INFO] full per-trade record -> {a.out}  ({len(out)} rows, {len(out.columns)} columns)\n")
    print_report(out, a.stop, a.detail)


def pct(s):
    return f"{s.mean() * 100:5.1f}%"


def dist(name, s, unit="min"):
    s = pd.Series(s).dropna()
    s = s[s >= 0]
    if not len(s):
        return
    print(f"  {name:38s} n={len(s):5d}  median {s.median():8.1f} {unit}  "
          f"p25 {s.quantile(.25):8.1f}  p75 {s.quantile(.75):8.1f}  p90 {s.quantile(.9):8.1f}  max {s.max():9.1f}")


def print_report(d: pd.DataFrame, stop_sigma: float, n_detail: int) -> None:
    n = len(d)
    print("=" * 118)
    print(f"1. WHAT THE ENGINE DID  ({n:,} trades, stop {stop_sigma} sigma, bar-close checking)")
    print("=" * 118)
    g = d.groupby("eng_exit_reason").agg(
        trades=("trade_num", "size"), pnl_usd=("eng_pnl_usd", "sum"),
        mean_usd=("eng_pnl_usd", "mean"), median_h=("eng_hours_held", "median"))
    print(g.round(3).to_string())
    print(f"\n  total P&L ${d.eng_pnl_usd.sum():+,.2f} over {n:,} trades")

    print()
    print("=" * 118)
    print(f"2. THE {stop_sigma} SIGMA STOP LEVEL — every crossing in the full 72 hours")
    print("=" * 118)
    crossed = d.first_cross_min >= 0
    print(f"  trades that ever cross the level   : {crossed.sum():5d}  ({pct(crossed)})")
    print(f"  trades that never cross it         : {(~crossed).sum():5d}  ({pct(~crossed)})")
    c = d[crossed]
    dist("time from entry to FIRST crossing", c.first_cross_min)
    dist("crossings per trade", c.n_crossings, "x")
    dist("total minutes spent beyond the level", c.minutes_beyond_stop)
    dist("longest single breach", c.longest_breach_min)
    dist("first crossing -> back inside", c.back_inside_min)
    never = (c.back_inside_min < 0).sum()
    print(f"  {'crossed and NEVER came back inside':38s} n={never:5d}  ({never / len(c) * 100:.1f}% of crossers)")

    print()
    print("=" * 118)
    print("3. MU — when the spread fully reverted")
    print("=" * 118)
    print(f"  trades that reach mu inside 72h    : {d.reached_mu.sum():5d}  ({pct(d.reached_mu)})")
    dist("time from entry to mu", d.loc[d.reached_mu, "first_mu_min"])
    both = d[crossed & d.reached_mu]
    print(f"\n  crossed the stop AND reached mu    : {len(both):5d}  ({len(both) / n * 100:.1f}% of all trades)")
    print(f"    reached mu BEFORE first crossing  : {both.mu_before_cross.sum():5d}")
    after = both[~both.mu_before_cross]
    print(f"    reached mu AFTER first crossing   : {len(after):5d}")
    dist("  first crossing -> mu", after.cross_to_mu_min)

    print()
    print("=" * 118)
    print("4. HOW FAR IT TRAVELLED, EITHER WAY (sigma from entry)")
    print("=" * 118)
    dist("max move AGAINST", d.max_adverse_sigma, "sig")
    dist("  ... minute it happened", d.max_adverse_min)
    dist("max move FOR", d.max_favour_sigma, "sig")
    dist("  ... minute it happened", d.max_favour_min)

    print()
    print("=" * 118)
    print("5. MARGIN — unrealised loss against the posted margin, if nothing closed it")
    print("=" * 118)
    print(f"  posted margin per position         : ${d.margin_usd.median():.2f} on "
          f"${d.gross_notional.median():.0f} gross")
    dist("worst unrealised loss", d.max_drawdown_usd, "usd")
    print(f"  trades breaching margin in 72h     : {d.liquidated.sum():5d}  ({pct(d.liquidated)})")
    dist("  ... minute of first breach", d.loc[d.liquidated, "liquidated_min"])

    print()
    print("=" * 118)
    print(f"6. {n_detail} TRADES IN FULL — longest-held first")
    print("=" * 118)
    cols = ["trade_num", "ticker_a", "ticker_b", "eng_exit_reason", "eng_hours_held",
            "z_at_entry", "beta_at_entry", "first_cross_min", "n_crossings",
            "minutes_beyond_stop", "back_inside_min", "first_mu_min",
            "cross_to_mu_min", "max_adverse_sigma", "max_drawdown_usd",
            "liquidated", "eng_pnl_usd", "ret_gross_at_horizon"]
    s = d.sort_values("eng_hours_held", ascending=False).head(n_detail)
    print(s[cols].round(3).to_string(index=False))
    print()
    print("  legend: minutes are from the fill. -1 = never happened.")
    print("  first_cross/n_crossings/mu are over the FULL 72h, including after the engine closed it.")


if __name__ == "__main__":
    main()
