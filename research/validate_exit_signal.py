"""Validate generate_exit_signal under the rolling-sigma geometry.

Run: python research/validate_exit_signal.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np

from signal_generator import generate_exit_signal

n_pass = n_fail = 0


def check(name, got, exp):
    global n_pass, n_fail
    ok = got == exp if isinstance(exp, (str, bool, type(None))) else abs(got - exp) < 1e-12
    n_pass, n_fail = n_pass + ok, n_fail + (not ok)
    print(f"{name + ':':56s} {str(got)[:22]:24s} {'PASS' if ok else 'FAIL (want ' + str(exp) + ')'}")


BETA, ALPHA = 1.0, 0.0
SIGMA = 0.01          # 7-day rolling std of the spread
MU = 0.0
STOP_SIGMA = 0.5
STOP_DIST = STOP_SIGMA * SIGMA   # 0.005


def sig(entry_spread, take_profit_pct=1.0):
    """Entry dict as generate_entry_signal now builds it."""
    return {
        "entry_spread":      entry_spread,
        "mu_at_entry":       MU,
        "sigma_at_entry":    SIGMA,
        "z_at_entry":        (entry_spread - MU) / SIGMA,
        "beta_at_entry":     BETA,
        "alpha_at_entry":    ALPHA,
        "theta_at_entry":    0.15,
        "take_profit_level": entry_spread - take_profit_pct * (entry_spread - MU),
    }


def run(entry, current_spread, hours=1.0, stop_sigma=STOP_SIGMA, max_hold=72.0):
    # With beta=1, alpha=0 the spread is price_a - price_b; hold b at 0.
    return generate_exit_signal(current_spread, 0.0, entry, hours,
                                stop_sigma=stop_sigma, max_hold_hours=max_hold)


# --------------------------------------------------------------------------
print("=" * 104)
print("1. Adverse move fires at exactly stop_sigma * rolling sigma FROM ENTRY")
print("=" * 104)
e = sig(0.03)   # entered 3.0 sigma above mu
check("at entry + 0.5*sigma exactly -> adverse_move",
      run(e, 0.03 + STOP_DIST)["exit_reason"], "adverse_move")
check("one tick inside the stop -> no exit",
      run(e, 0.03 + STOP_DIST - 1e-9), None)
check("well beyond the stop -> adverse_move",
      run(e, 0.03 + 3 * STOP_DIST)["exit_reason"], "adverse_move")

e_below = sig(-0.03)
check("below mu: at entry - 0.5*sigma -> adverse_move",
      run(e_below, -0.03 - STOP_DIST)["exit_reason"], "adverse_move")
check("below mu: one tick inside -> no exit",
      run(e_below, -0.03 - STOP_DIST + 1e-9), None)

# --------------------------------------------------------------------------
print()
print("=" * 104)
print("2. REGRESSION: the stop is a distance from entry, not a level from mu")
print("=" * 104)
print("   A fixed level from mu makes the stop tighter the further out you enter,")
print("   which manufactured a spurious entry-z / win-rate curve. Guard it.")
near, far = sig(0.03), sig(0.06)   # 3.0 sigma vs 6.0 sigma from mu
d_near = run(near, 0.03 + STOP_DIST)
d_far  = run(far,  0.06 + STOP_DIST)
check("entry at 3 sigma stops after 0.5 sigma of travel",
      d_near["exit_reason"], "adverse_move")
check("entry at 6 sigma stops after the SAME 0.5 sigma of travel",
      d_far["exit_reason"], "adverse_move")
check("far entry does not stop at the near entry's absolute level",
      run(far, 0.03 + STOP_DIST), None)

# --------------------------------------------------------------------------
print()
print("=" * 104)
print("3. Take profit at full reversion to mu (take_profit_pct = 1.0)")
print("=" * 104)
check("take_profit_level == mu", sig(0.03)["take_profit_level"], MU)
check("reaching mu from above -> take_profit",
      run(sig(0.03), MU)["exit_reason"], "take_profit")
check("past mu -> take_profit",
      run(sig(0.03), MU - 0.001)["exit_reason"], "take_profit")
check("90% of the way to mu -> no exit", run(sig(0.03), 0.003), None)
check("from below, reaching mu -> take_profit",
      run(sig(-0.03), MU)["exit_reason"], "take_profit")

# --------------------------------------------------------------------------
print()
print("=" * 104)
print("4. Flat 72h time stop (no per-trade model estimate binding first)")
print("=" * 104)
check("71.5h with nothing else triggered -> no exit", run(sig(0.03), 0.029, hours=71.5), None)
check("exactly 72h -> time_stop", run(sig(0.03), 0.029, hours=72.0)["exit_reason"], "time_stop")
check("beyond 72h -> time_stop", run(sig(0.03), 0.029, hours=100.0)["exit_reason"], "time_stop")
check("time stop wins over a simultaneous adverse move",
      run(sig(0.03), 0.03 + 3 * STOP_DIST, hours=80.0)["exit_reason"], "time_stop")
check("max_hold_hours is honoured when the caller sets it lower",
      run(sig(0.03), 0.029, hours=25.0, max_hold=24.0)["exit_reason"], "time_stop")

# --------------------------------------------------------------------------
print()
print("=" * 104)
print("5. Stop scales with the pair's own rolling sigma")
print("=" * 104)
wide = dict(sig(0.03)); wide["sigma_at_entry"] = 0.05   # 5x more volatile
check("wide-sigma pair: the tight pair's stop level does not fire",
      run(wide, 0.03 + STOP_DIST), None)
check("wide-sigma pair fires at its own 0.5 sigma",
      run(wide, 0.03 + 0.5 * 0.05)["exit_reason"], "adverse_move")

# --------------------------------------------------------------------------
print()
print("=" * 104)
print("6. Reported fields")
print("=" * 104)
out = run(sig(0.03), MU)
check("pnl_pct at full reversion == 1.0", out["pnl_pct"], 1.0)
check("entry_spread carried through", out["entry_spread"], 0.03)
check("current_spread reported", out["current_spread"], MU)
check("stop_sigma echoed on a take_profit too", out["stop_sigma"], STOP_SIGMA)
check("no exit condition -> None", run(sig(0.03), 0.029), None)

print()
print("=" * 104)
print(f"{n_pass}/{n_pass + n_fail} assertions PASS")
print("=" * 104)
sys.exit(1 if n_fail else 0)
