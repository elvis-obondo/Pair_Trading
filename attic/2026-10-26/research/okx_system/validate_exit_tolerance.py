"""Validate grace and debounce inside the Portfolio. PASS/FAIL, repo convention.

WHY A SECOND VALIDATOR. validate_sweep_exits.py checks the STANDALONE walk used
by the stage-1 sweep. This checks the ENGINE's copy of the same rule. They are
two implementations of one idea, and the whole study rests on them agreeing --
stage 1 finds the candidates, stage 2 prices them, and if the two rules differ
then stage 2 is not confirming stage 1, it is answering a different question.

The last section asserts that agreement directly.

Run: python research/validate_exit_tolerance.py
"""
from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta

import numpy as np

from portfolio import Portfolio, Position
from sweep_exits import walk, REASON

n_pass = n_fail = 0


def check(name, ok, detail=""):
    global n_pass, n_fail
    ok = bool(ok)
    n_pass, n_fail = n_pass + ok, n_fail + (not ok)
    print(f"{name + ':':74s} {str(detail)[:20]:22s} {'PASS' if ok else 'FAIL'}")


SG, MU, STOP = 0.02, 0.0, 0.5
ENTRY = MU + 3.5 * SG                      # above mu -> short the spread
SIG = {"entry_spread": ENTRY, "mu_at_entry": MU, "sigma_at_entry": SG,
       "z_at_entry": 3.5, "beta_at_entry": 1.0, "alpha_at_entry": 0.0,
       "theta_at_entry": 0.2, "take_profit_level": MU}
SZG = {"leg_a_notional": 150.0, "leg_b_notional": 150.0, "gross_notional": 300.0,
       "margin": 15.0, "leverage": 20.0, "notional_capped": False}
T0 = datetime(2026, 9, 1)
BEYOND = ENTRY + STOP * SG * 1.2
INSIDE = ENTRY + STOP * SG * 0.2


def book(debounce=0.0, grace=0.0):
    pf = Portfolio(equity=300.0, max_slots=1, stop_sigma=STOP,
                   debounce_minutes=debounce, grace_minutes=grace)
    pf.open_positions.append(Position(1, "A", "B", SIG, SZG, T0, STOP))
    return pf


def walk_pf(pf, path):
    """path = [(minute, spread)]; leg B held at 0 so spread == log price A."""
    for m, sp in path:
        if pf.open_positions:
            pf.evaluate_exits({"A": sp, "B": 0.0}, T0 + timedelta(minutes=m))
    return pf


print("=" * 118)
print("1. Both knobs off reproduces the old behaviour exactly")
print("=" * 118)
pf = walk_pf(book(), [(1, BEYOND)])
check("no grace, no debounce: exits on the first breach", len(pf.closed) == 1,
      pf.closed[0]["exit_reason"] if pf.closed else "held")

print()
print("=" * 118)
print("2. GRACE — the stop does not exist early, and is at full strength after")
print("=" * 118)
pf = walk_pf(book(grace=30), [(m, BEYOND) for m in range(1, 29)])
check("grace 30 holds through a 28-minute breach", len(pf.closed) == 0,
      f"{len(pf.open_positions)} open")
pf = walk_pf(book(grace=30), [(m, BEYOND) for m in range(1, 60)])
check("  ... and fires at minute 30", len(pf.closed) == 1
      and pf.closed[0]["closed_at"] == T0 + timedelta(minutes=30),
      pf.closed[0]["closed_at"].strftime("%H:%M") if pf.closed else "-")
# A breach entirely inside the grace must leave NO residue.
pf = walk_pf(book(grace=30), [(m, BEYOND) for m in range(1, 20)]
             + [(m, INSIDE) for m in range(20, 90)])
check("a breach that ends inside the grace never fires", len(pf.closed) == 0,
      f"{len(pf.open_positions)} open")
pf = walk_pf(book(grace=30), [(m, INSIDE) for m in range(1, 60)]
             + [(m, BEYOND) for m in range(60, 70)])
check("grace does NOT loosen the stop afterwards", len(pf.closed) == 1
      and pf.closed[0]["closed_at"] == T0 + timedelta(minutes=60),
      pf.closed[0]["closed_at"].strftime("%H:%M") if pf.closed else "-")

print()
print("=" * 118)
print("3. DEBOUNCE — persistence required, clock resets on recovery")
print("=" * 118)
pf = walk_pf(book(debounce=15), [(1, BEYOND)] + [(m, INSIDE) for m in range(2, 60)])
check("debounce 15 survives a 1-minute poke", len(pf.closed) == 0, "held")
pf = walk_pf(book(debounce=15), [(m, BEYOND) for m in range(1, 60)])
check("  ... fires when the breach holds", len(pf.closed) == 1,
      pf.closed[0]["exit_reason"] if pf.closed else "-")
check("  ... at first breach + debounce", pf.closed
      and pf.closed[0]["closed_at"] == T0 + timedelta(minutes=16),
      pf.closed[0]["closed_at"].strftime("%H:%M") if pf.closed else "-")
pf = walk_pf(book(debounce=15),
             [(m, BEYOND) for m in range(1, 14)] + [(14, INSIDE)]
             + [(m, BEYOND) for m in range(15, 28)] + [(m, INSIDE) for m in range(28, 80)])
check("two 13-minute breaches split by a recovery do NOT add up", len(pf.closed) == 0,
      "held")

print()
print("=" * 118)
print("4. Take profit and the time stop are never graced or debounced")
print("=" * 118)
pf = walk_pf(book(debounce=30, grace=60), [(1, MU)])
check("take_profit fires at minute 1 despite grace 60 / debounce 30",
      len(pf.closed) == 1 and pf.closed[0]["exit_reason"] == "take_profit",
      pf.closed[0]["exit_reason"] if pf.closed else "held")
pf = book(debounce=30, grace=60)
pf.evaluate_exits({"A": INSIDE, "B": 0.0}, T0 + timedelta(hours=73))
check("time_stop fires regardless", len(pf.closed) == 1
      and pf.closed[0]["exit_reason"] == "time_stop",
      pf.closed[0]["exit_reason"] if pf.closed else "held")

print()
print("=" * 118)
print("5. A graced or debounced fill is the OBSERVED spread, never a model")
print("=" * 118)
pf = Portfolio(equity=300.0, max_slots=1, stop_sigma=STOP,
               grace_minutes=30, stop_fill_overshoot=1.04)
pf.open_positions.append(Position(1, "A", "B", SIG, SZG, T0, STOP))
far = ENTRY + STOP * SG * 3.0
walk_pf(pf, [(m, far) for m in range(1, 40)])
check("stop_fill_overshoot is ignored once a knob is on", len(pf.closed) == 1, "closed")
if pf.closed:
    modelled = ENTRY + STOP * SG * 1.04
    check("  ... books the real spread, not the 1.04x level",
          abs(pf.closed[0]["exit_spread"] - far) < 1e-12
          and abs(pf.closed[0]["exit_spread"] - modelled) > 1e-6,
          f"{pf.closed[0]['exit_spread']:.5f}")

print()
print("=" * 118)
print("6. THE ENGINE AND THE STAGE-1 WALK AGREE — or stage 2 confirms nothing")
print("=" * 118)
rng = np.random.default_rng(11)
mismatch = 0
for trial in range(300):
    grace = (0, 15, 30, 60)[trial % 4]
    deb = (0, 5, 15)[trial % 3]
    path = np.concatenate([[ENTRY], ENTRY + np.cumsum(rng.normal(0, 0.3 * SG, 300))])
    t, s, code = walk(path, ENTRY, MU, -1.0, STOP * SG, deb, grace, 4320)

    pf = book(debounce=deb, grace=grace)
    walk_pf(pf, list(enumerate(path))[1:])
    if pf.closed:
        got = (int((pf.closed[0]["closed_at"] - T0).total_seconds() // 60),
               pf.closed[0]["exit_reason"])
    else:
        got = (len(path) - 1, None)
    exp = (int(t), REASON[code]) if code else (len(path) - 1, None)
    if got != exp:
        mismatch += 1
check("300 random paths x (grace, debounce) agree exactly", mismatch == 0,
      f"{mismatch} mismatches")

print()
print("=" * 118)
print(f"{n_pass}/{n_pass + n_fail} assertions PASS")
print("=" * 118)
sys.exit(1 if n_fail else 0)
