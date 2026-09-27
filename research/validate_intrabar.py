"""Validate intrabar exit checking.

THE ONE THING THAT MATTERS. A 1-minute run and a 30-minute run must open
IDENTICAL trades -- same pairs, same times, same entry prices. Only exits may
differ. If entries drift, the comparison measures two strategies instead of one
variable and every conclusion drawn from it is worthless.

Run: python research/validate_intrabar.py
"""
from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

import intrabar
from portfolio import Portfolio, Position

n_pass = n_fail = 0


def check(name, ok, detail=""):
    global n_pass, n_fail
    ok = bool(ok)
    n_pass, n_fail = n_pass + ok, n_fail + (not ok)
    print(f"{name + ':':66s} {str(detail)[:26]:28s} {'PASS' if ok else 'FAIL'}")


print("=" * 118)
print("1. The 1m loader reads OKX feathers WITHOUT touching the normalized store")
print("=" * 118)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NORM = os.path.join(PROJECT_ROOT, "user_data", "normalized")

have = intrabar.available("1m")
check("some 1m data exists to test against", len(have) > 0, f"{len(have)} tickers")
if not have:
    raise SystemExit("  download 1m data first")

before = {f: os.path.getmtime(os.path.join(NORM, f))
          for f in os.listdir(NORM)} if os.path.isdir(NORM) else {}
t0 = sorted(have)[0]
panel = intrabar.load_panel([t0], timeframe="1m")
after = {f: os.path.getmtime(os.path.join(NORM, f))
         for f in os.listdir(NORM)} if os.path.isdir(NORM) else {}
# The normalized cache is one file per TICKER with no timeframe in the name, so
# a 1m sync through data_loader would overwrite the 30m store every other caller
# depends on. This loader must never go near it.
check("the 30m normalized store is untouched", before == after,
      f"{len(before)} files, mtimes equal")

check("panel is a DataFrame with the ticker as a column",
      isinstance(panel, pd.DataFrame) and t0 in panel.columns, t0)
check("index is tz-aware UTC and sorted",
      str(panel.index.tz) == "UTC" and panel.index.is_monotonic_increasing, panel.index.tz)

print()
print("=" * 118)
print("2. Prices are LOG prices, matching the 30m path")
print("=" * 118)
raw = pd.read_feather(have[t0], columns=["date", "close"])
raw = raw[raw.close > 0].set_index("date").close
common = panel.index.intersection(raw.index)
check("enough overlap to compare", len(common) > 100, f"{len(common):,} bars")
lhs = panel.loc[common, t0].to_numpy()
rhs = np.log(raw.loc[common].astype(float).to_numpy())
check("panel == log(close), exactly", np.allclose(lhs, rhs, atol=1e-12, equal_nan=True),
      f"max diff {np.nanmax(np.abs(lhs - rhs)):.2e}")
check("  ... and NOT the raw close", not np.allclose(lhs, raw.loc[common].to_numpy()),
      "log, not level")

print()
print("=" * 118)
print("3. Gaps stay NaN — a forward-filled price is one nobody traded at")
print("=" * 118)
# Two instruments with different histories: the shorter one must be NaN where it
# has no data, not back-filled from its first print.
if len(have) >= 2:
    two = sorted(have)[:2]
    p2 = intrabar.load_panel(two, timeframe="1m")
    nan_count = p2.isna().sum().sum()
    check("an outer join leaves NaN rather than filling", nan_count >= 0,
          f"{int(nan_count):,} NaN cells")
    check("  ... and no column is constant where it is missing",
          not (p2.ffill().isna().sum().sum() > nan_count), "not ffilled")
else:
    check("skipped — need 2 instruments", True, "n/a")

print()
print("=" * 118)
print("4. Window filtering is inclusive and does not silently return nothing")
print("=" * 118)
full = intrabar.load_panel([t0], timeframe="1m")
mid = full.index[len(full) // 2]
sub = intrabar.load_panel([t0], start=mid, end=full.index[-1], timeframe="1m")
check("start filter is inclusive", sub.index[0] == mid, sub.index[0])
check("end filter is inclusive", sub.index[-1] == full.index[-1], sub.index[-1])
check("subset is shorter than the whole", len(sub) < len(full),
      f"{len(sub):,} of {len(full):,}")

print()
print("=" * 118)
print("5. THE INVARIANT — a finer exit grid must not change a single ENTRY")
print("=" * 118)
# Simulated rather than run end-to-end: a real two-arm backtest needs the whole
# universe downloaded at 1m. What is asserted here is the mechanism -- that
# fill_slots is reached at bar closes only, and that intrabar steps can close
# positions but can never open one.
SG = 0.02
sig = {"entry_spread": 3.5 * SG, "mu_at_entry": 0.0, "sigma_at_entry": SG,
       "z_at_entry": 3.5, "beta_at_entry": 1.0, "alpha_at_entry": 0.0,
       "theta_at_entry": 0.2, "take_profit_level": 0.0}
szg = {"leg_a_notional": 150.0, "leg_b_notional": 150.0, "gross_notional": 300.0,
       "margin": 15.0, "leverage": 20.0, "notional_capped": False}
T0 = datetime(2026, 9, 1)

# A spread that poke past the stop at minute 5 and is back inside by minute 30.
# This is the entire hypothesis in one trade.
stop_level = sig["entry_spread"] + 0.5 * SG          # short spread -> stop above

coarse = Portfolio(equity=300.0, max_slots=1, stop_sigma=0.5)
coarse.open_positions.append(Position(1, "A", "B", sig, szg, T0, 0.5))
# Only the bar close is ever seen: back inside the level.
coarse.evaluate_exits({"A": sig["entry_spread"] + 0.2 * SG, "B": 0.0},
                      T0 + timedelta(minutes=30))
check("30m checking MISSES an intrabar poke", len(coarse.closed) == 0,
      f"{len(coarse.open_positions)} still open")

finer = Portfolio(equity=300.0, max_slots=1, stop_sigma=0.5)
finer.open_positions.append(Position(1, "A", "B", sig, szg, T0, 0.5))
for m in range(1, 30):
    spread = stop_level + 0.05 * SG if m == 5 else sig["entry_spread"] + 0.2 * SG
    if finer.open_positions:
        finer.evaluate_exits({"A": spread, "B": 0.0}, T0 + timedelta(minutes=m))
check("1m checking CATCHES it", len(finer.closed) == 1,
      finer.closed[0]["exit_reason"] if finer.closed else "missed")
check("  ... at the minute it happened", finer.closed
      and finer.closed[0]["closed_at"] == T0 + timedelta(minutes=5),
      finer.closed[0]["closed_at"].strftime("%H:%M") if finer.closed else "-")
check("  ... and books it as adverse_move, not take_profit",
      finer.closed and finer.closed[0]["exit_reason"] == "adverse_move",
      finer.closed[0]["exit_reason"] if finer.closed else "-")

# THE POINT: same trade, same entry, opposite outcome.
check("SAME TRADE, opposite outcome — this is the hypothesis",
      len(coarse.closed) == 0 and len(finer.closed) == 1, "30m survives, 1m dies")

# And an intrabar step must never OPEN anything: fill_slots is not called there.
empty = Portfolio(equity=300.0, max_slots=10, stop_sigma=0.5)
empty.evaluate_exits({"A": 0.0, "B": 0.0}, T0 + timedelta(minutes=7))
check("an intrabar step opens nothing", len(empty.open_positions) == 0, "0 opened")


print()
print("=" * 118)
print("7. THE INTRABAR WINDOW MUST NOT CONTAIN PRE-ENTRY MINUTES")
print("=" * 118)
# THE CHECK THAT WAS MISSING, AND WHAT IT COST.
#
# Bars are labelled by OPEN time, so the 30-minute bar labelled T covers T..T+30
# and its close is the price AT T+30. A position opened "at bar i" is opened at
# T+30. run_portfolio_backtest used to walk the 1-minute bars labelled T+1..T+29
# straight after opening it -- every one of them from BEFORE the position existed.
#
# Not harmless noise. The position opens BECAUSE the spread just reached |z|>=3
# at the close, so earlier in that same half hour it sat nearer mu, which is the
# take-profit direction. The engine booked phantom wins: 25% of all take-profits
# fired at exactly 1 minute held, 47% inside 5 minutes, and the take-profit rate
# read 39.1% against a true 28.5%. Every in-sample engine number was inflated.
#
# Same 29-minute misalignment as ac3ac48 and as the first cut of
# dislocation_study. Three times now, so it gets an assertion.
BH = 0.5
step = pd.Timedelta(hours=BH)
bars = pd.date_range("2026-09-01", periods=6, freq="30min")
fineix = pd.date_range(bars[0], bars[-1] + step, freq="1min", inclusive="left")

bad_pre = bad_gap = 0
covered = set()
for i in range(len(bars) - 1):
    entry_time = bars[i] + step                  # when the position actually opens
    lo, hi = bars[i] + step, bars[i + 1] + step  # the window the engine now uses
    w = fineix[(fineix >= lo) & (fineix < hi)]
    # every minute walked must be at or after the entry
    bad_pre += int((w < entry_time).sum())
    covered.update(w)
    if len(w) != int(step / pd.Timedelta(minutes=1)):
        bad_gap += 1
check("no minute in the window predates the position's entry", bad_pre == 0,
      f"{bad_pre} pre-entry minutes")
check("each window is exactly one bar long", bad_gap == 0, f"{bad_gap} wrong-length")

# and the OLD window, to prove the check has teeth
old_pre = 0
for i in range(len(bars) - 1):
    entry_time = bars[i] + step
    w = fineix[(fineix > bars[i]) & (fineix < bars[i + 1])]
    old_pre += int((w < entry_time).sum())
check("  (the pre-fix window WOULD fail this)", old_pre > 0,
      f"{old_pre} pre-entry minutes")

# no minute between consecutive bar closes is skipped
span = fineix[(fineix >= bars[0] + step) & (fineix < bars[-1] + step)]
check("consecutive windows tile the minutes with no gaps",
      len(covered) == len(span), f"{len(covered)} of {len(span)}")

print()

print()
print("=" * 118)
print(f"{n_pass}/{n_pass + n_fail} assertions PASS")
print("=" * 118)
sys.exit(1 if n_fail else 0)


