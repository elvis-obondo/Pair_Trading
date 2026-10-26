"""Validate the stored-path exit walk. PASS/FAIL, repo convention.

THE ONE THING THAT MATTERS. At debounce 0 and grace 0, walking a path minute by
minute must reproduce what generate_exit_signal would decide at those same
minutes. If it does not, every number the sweep produces is measuring a different
strategy from the one the engine runs, and the whole study is void.

Run: python research/validate_sweep_exits.py
"""
from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np

from sweep_exits import walk, REASON
from signal_generator import generate_exit_signal

n_pass = n_fail = 0


def check(name, ok, detail=""):
    global n_pass, n_fail
    ok = bool(ok)
    n_pass, n_fail = n_pass + ok, n_fail + (not ok)
    print(f"{name + ':':74s} {str(detail)[:20]:22s} {'PASS' if ok else 'FAIL'}")


SG, MU = 0.02, 0.0
ENTRY_SHORT = MU + 3.5 * SG          # above mu -> short the spread, direction -1
ENTRY_LONG = MU - 3.5 * SG           # below mu -> long the spread,  direction +1
HORIZON = 4320


def sig(entry):
    return {"entry_spread": entry, "mu_at_entry": MU, "sigma_at_entry": SG,
            "z_at_entry": (entry - MU) / SG, "beta_at_entry": 1.0,
            "alpha_at_entry": 0.0, "theta_at_entry": 0.2, "take_profit_level": MU}


print("=" * 118)
print("1. AGREEMENT WITH THE ENGINE — same path, same verdict, minute by minute")
print("=" * 118)
rng = np.random.default_rng(7)
mismatch = first_bad = 0
for trial in range(400):
    entry = ENTRY_SHORT if trial % 2 else ENTRY_LONG
    d = -1.0 if entry > MU else 1.0
    stop_sigma = (0.5, 1.0, 1.5)[trial % 3]
    path = np.concatenate([[entry], entry + np.cumsum(rng.normal(0, 0.3 * SG, 400))])
    t, s, code = walk(path, entry, MU, d, stop_sigma * SG, 0, 0, HORIZON)

    # What the engine would have said at each minute, walking the same path.
    want_t = want_reason = None
    for i in range(1, len(path)):
        ex = generate_exit_signal(current_price_a=path[i], current_price_b=0.0,
                                  entry_signal=sig(entry), hours_elapsed=i / 60.0,
                                  stop_sigma=stop_sigma, max_hold_hours=HORIZON / 60.0)
        if ex is not None:
            want_t, want_reason = i, ex["exit_reason"]
            break
    got = (t, REASON[code]) if code else (len(path) - 1, None)
    exp = (want_t, want_reason) if want_t is not None else (len(path) - 1, None)
    if got != exp:
        mismatch += 1
        if first_bad == 0:
            first_bad = trial
check("400 random paths agree exactly with generate_exit_signal",
      mismatch == 0, f"{mismatch} mismatches")

print()
print("=" * 118)
print("2. THE DEBOUNCE — persistence required, clock resets on recovery")
print("=" * 118)
e = ENTRY_SHORT
stop = 0.5 * SG
beyond = e + stop * 1.2
inside = e + stop * 0.2
flat = np.full(200, inside); flat[0] = e

p = flat.copy(); p[10] = beyond
t, s, c = walk(p, e, MU, -1.0, stop, 0, 0, HORIZON)
check("debounce 0 fires on the first breach", c == 1 and t == 10, f"min {t}")

p = flat.copy(); p[10] = beyond
t, s, c = walk(p, e, MU, -1.0, stop, 15, 0, HORIZON)
check("debounce 15 survives a 1-minute poke", c == 0, REASON[c])

p = flat.copy(); p[10:24] = beyond          # 14 minutes, one short
t, s, c = walk(p, e, MU, -1.0, stop, 15, 0, HORIZON)
check("  ... and a 14-minute breach under a 15-minute debounce", c == 0, REASON[c])

p = flat.copy(); p[10:60] = beyond
t, s, c = walk(p, e, MU, -1.0, stop, 15, 0, HORIZON)
check("debounce 15 fires when the breach holds", c == 1, REASON[c])
check("  ... at first breach + debounce, not before", t == 25, f"min {t}")

p = flat.copy(); p[10:24] = beyond; p[24] = inside; p[25:39] = beyond
t, s, c = walk(p, e, MU, -1.0, stop, 15, 0, HORIZON)
check("two 14-minute breaches split by a recovery do NOT add up", c == 0, REASON[c])

print()
print("=" * 118)
print("3. ENTRY GRACE — suppresses the stop only at the START")
print("=" * 118)
p = flat.copy(); p[5:200] = beyond
t, s, c = walk(p, e, MU, -1.0, stop, 0, 0, HORIZON)
check("no grace stops at minute 5", c == 1 and t == 5, f"min {t}")
t, s, c = walk(p, e, MU, -1.0, stop, 0, 30, HORIZON)
check("grace 30 delays that to minute 30", c == 1 and t == 30, f"min {t}")

p = flat.copy(); p[5:20] = beyond           # breach entirely inside the grace
t, s, c = walk(p, e, MU, -1.0, stop, 0, 30, HORIZON)
check("a breach that ends inside the grace never fires", c == 0, REASON[c])

p = flat.copy(); p[100:200] = beyond        # long after the grace
t, s, c = walk(p, e, MU, -1.0, stop, 0, 30, HORIZON)
check("grace does NOT loosen the stop later on", c == 1 and t == 100, f"min {t}")

print()
print("=" * 118)
print("4. TAKE PROFIT is never graced, never debounced")
print("=" * 118)
p = flat.copy(); p[3] = MU
t, s, c = walk(p, e, MU, -1.0, stop, 30, 60, HORIZON)
check("take_profit fires at minute 3 despite grace 60 / debounce 30",
      c == 2 and t == 3, f"{REASON[c]} min {t}")

# ... and it wins the race when both are live in the same minute.
p = flat.copy(); p[10:60] = beyond; p[40] = MU
t, s, c = walk(p, e, MU, -1.0, stop, 60, 0, HORIZON)
check("a reversion DURING a debounce window books as take_profit",
      c == 2 and t == 40, f"{REASON[c]} min {t}")

print()
print("=" * 118)
print("5. BOTH DIRECTIONS, and NaN minutes are never decided on")
print("=" * 118)
el = ENTRY_LONG
flat_l = np.full(200, el - stop * 0.2); flat_l[0] = el
p = flat_l.copy(); p[10:60] = el - stop * 1.2       # adverse for a LONG is down
t, s, c = walk(p, el, MU, 1.0, stop, 0, 0, HORIZON)
check("a long-spread position stops on a FALL", c == 1 and t == 10, f"min {t}")
p = flat_l.copy(); p[10] = MU
t, s, c = walk(p, el, MU, 1.0, stop, 0, 0, HORIZON)
check("  ... and takes profit on a RISE to mu", c == 2 and t == 10, f"min {t}")

p = flat.copy(); p[10:60] = np.nan; p[12] = beyond   # unreachable: it is NaN
p[10:60] = np.nan
t, s, c = walk(p, e, MU, -1.0, stop, 0, 0, HORIZON)
check("NaN minutes are skipped, not decided on", c == 0, REASON[c])
check("  ... and no NaN is ever returned as a fill", s == s, f"{s:.5f}")

print()
print("=" * 118)
print("6. TIME STOP binds at the horizon")
print("=" * 118)
p = np.full(200, inside); p[0] = e
t, s, c = walk(p, e, MU, -1.0, stop, 0, 0, 100)
check("time_stop fires at the horizon", c == 3 and t == 100, f"{REASON[c]} min {t}")

print()
print("=" * 118)
print("7. MARGIN SURVIVAL — the column that says whether the position lived to earn it")
print("=" * 118)

import pandas as pd
from sweep_exits import score

# Two trades from one entry. #1 dips 0.4 sigma against and reverts to mu.
# #2 RAMPS to 3 sigma at 0.05 sigma a minute, so a stop set at 0.5 sigma has a
# minute it can actually fire on. A path that jumps straight to 3 sigma would
# gap through every level at once and the stop would book the full loss -- real,
# and the reason overshoot exists, but it tests nothing about the drawdown
# column. leg A is the whole gross, so 1 sigma is exactly 0.02 * 300 = $6.
N = 600
p1 = np.full(N, ENTRY_SHORT + 0.4 * SG); p1[0] = ENTRY_SHORT; p1[200:] = MU - 0.01 * SG
p2 = ENTRY_SHORT + np.minimum(np.arange(N) * 0.05, 3.0) * SG
spreads = np.concatenate([p1, p2])
sm = pd.DataFrame({
    "trade_num": [1, 2],
    "entry_spread": [ENTRY_SHORT, ENTRY_SHORT], "mu_at_entry": [MU, MU],
    "sigma_at_entry": [SG, SG],
    "leg_a_notional": [300.0, 300.0], "leg_b_notional": [0.0, 0.0],
    "gross_notional": [300.0, 300.0],
    "margin": [15.0, 15.0],                       # 20x: liquidation at $15
    "path_start": [0, N], "path_len": [N, N],
})

# No stop. #1 peaks at 0.4 sigma = $2.40, safe. #2 sits at 3 sigma = $18, past $15.
r = score(spreads, sm, float("inf"), 0, 0, HORIZON, check_every=1)
check("drawdown is dollars, not sigma", abs(r.worst_drawdown[0] - 2.40) < 1e-6,
      f"${r.worst_drawdown[0]:.2f}")
check("the safe trade is not liquidated", not r.liquidated[0], r.worst_drawdown[0])
check("the runaway IS liquidated", r.liquidated[1], f"${r.worst_drawdown[1]:.2f}")
check("liquidated is exactly drawdown > margin",
      bool((r.worst_drawdown > sm.margin).equals(r.liquidated)), "consistent")

# THE POINT OF MEASURING TO THE EXIT. A 0.5-sigma stop closes #2 at minute 1,
# at $3 of loss -- the position no longer exists to be liquidated at minute 2.
r2 = score(spreads, sm, 0.5, 0, 0, HORIZON, check_every=1)
check("a stop that fires early caps the drawdown", r2.worst_drawdown[1] < 15.0,
      f"${r2.worst_drawdown[1]:.2f}")
check("  ... so it is NOT counted as liquidated", not r2.liquidated[1], "survived")
check("a tight stop never liquidates more than a wide one",
      r2.liquidated.sum() <= r.liquidated.sum(),
      f"{r2.liquidated.sum()} <= {r.liquidated.sum()}")

print()
print("=" * 118)
print(f"{n_pass}/{n_pass + n_fail} assertions PASS")
print("=" * 118)
sys.exit(1 if n_fail else 0)
