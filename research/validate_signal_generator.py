"""Validate generate_entry_signal under the rolling-sigma geometry.

Run: python research/validate_signal_generator.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np

from signal_generator import generate_entry_signal
from rolling_spread import rolling_spread_stats, entry_window_bars

n_pass = n_fail = 0


def check(name, got, exp, tol=1e-10):
    global n_pass, n_fail
    if isinstance(exp, (str, bool, type(None))):
        ok = got == exp
    else:
        ok = got is not None and abs(got - exp) <= tol
    n_pass, n_fail = n_pass + ok, n_fail + (not ok)
    print(f"{name + ':':52s} {str(got)[:26]:28s} {'PASS' if ok else 'FAIL (want ' + str(exp) + ')'}")


BAR_HOURS = 0.5
W = entry_window_bars(BAR_HOURS)


def ou_pair(n=900, theta=0.05, sigma=0.01, beta=1.0, shock=0.0, seed=0):
    """A cointegrated pair: b is a random walk, a = beta*b + a mean-reverting spread.

    `shock` is added to the final bar's leg A, which pushes the spread out by a
    known amount so the entry threshold can be exercised deterministically.
    """
    rng = np.random.default_rng(seed)
    b = np.cumsum(rng.normal(0, 0.01, n)) + 5.0
    s = np.zeros(n)
    for t in range(1, n):
        s[t] = s[t - 1] + theta * (0.0 - s[t - 1]) + rng.normal(0, sigma)
    a = beta * b + s
    a[-1] += shock
    return a, b


# --------------------------------------------------------------------------
print("=" * 110)
print("1. The entry threshold is |z| in 7-day ROLLING sigma")
print("=" * 110)
a, b = ou_pair()
r = rolling_spread_stats(a, b, BAR_HOURS)
z_now = float(r.z[-1])
print(f"   constructed pair sits at z = {z_now:+.3f} rolling sigma\n")

thr_below = abs(z_now) - 0.25
thr_above = abs(z_now) + 0.25
s_fire = generate_entry_signal(a, b, min_deviation_sigma=thr_below, bar_hours=BAR_HOURS)
s_hold = generate_entry_signal(a, b, min_deviation_sigma=thr_above, bar_hours=BAR_HOURS)
check(f"threshold {thr_below:.2f} < |z| -> fires", s_fire is not None, True)
check(f"threshold {thr_above:.2f} > |z| -> None", s_hold, None)

# --------------------------------------------------------------------------
print()
print("=" * 110)
print("2. Reported geometry matches rolling_spread exactly")
print("=" * 110)
check("z_at_entry", s_fire["z_at_entry"], z_now)
check("sigma_at_entry == rolling std", s_fire["sigma_at_entry"], float(r.sigma[-1]))
check("mu_at_entry == rolling mean", s_fire["mu_at_entry"], float(r.mu[-1]))
check("beta_at_entry == rolling beta", s_fire["beta_at_entry"], float(r.beta[-1]))
check("alpha_at_entry == rolling alpha", s_fire["alpha_at_entry"], float(r.alpha[-1]))
check("entry_spread == rolling spread", s_fire["entry_spread"], float(r.spread[-1]))
check("z == (spread - mu) / sigma",
      s_fire["z_at_entry"],
      (s_fire["entry_spread"] - s_fire["mu_at_entry"]) / s_fire["sigma_at_entry"])

# --------------------------------------------------------------------------
print()
print("=" * 110)
print("3. sigma_at_entry is the ROLLING std, not the OU stationary sigma")
print("=" * 110)
from ou_model import fit_ou_ewma
sf = a[-W:] - s_fire["beta_at_entry"] * b[-W:] - s_fire["alpha_at_entry"]
p = fit_ou_ewma(a[-W:], b[-W:], bar_hours=BAR_HOURS, spread=sf)
stationary = p.sigma / np.sqrt(2.0 * p.theta)
print(f"   rolling std      = {s_fire['sigma_at_entry']:.6f}")
print(f"   OU stationary    = {stationary:.6f}   (ratio {s_fire['sigma_at_entry']/stationary:.2f}x)")
differs = abs(s_fire["sigma_at_entry"] - stationary) > 1e-6
check("the two are genuinely different quantities", differs, True)
check("the reported one is the rolling std", s_fire["sigma_at_entry"], float(r.sigma[-1]))

# --------------------------------------------------------------------------
print()
print("=" * 110)
print("4. take_profit_pct = 1.0 targets mu itself")
print("=" * 110)
check("take_profit_level == mu_at_entry",
      s_fire["take_profit_level"], s_fire["mu_at_entry"])
s80 = generate_entry_signal(a, b, min_deviation_sigma=thr_below,
                            take_profit_pct=0.8, bar_hours=BAR_HOURS)
gap = s80["entry_spread"] - s80["mu_at_entry"]
check("take_profit_pct = 0.8 captures 80% of the gap",
      s80["take_profit_level"], s80["entry_spread"] - 0.8 * gap)

# --------------------------------------------------------------------------
print()
print("=" * 110)
print("5. theta survives as the ranking key, and a bad fit still declines")
print("=" * 110)
check("theta_at_entry is finite and positive",
      bool(np.isfinite(s_fire["theta_at_entry"]) and s_fire["theta_at_entry"] > 0), True)
fast_a, fast_b = ou_pair(theta=0.30, seed=7)
slow_a, slow_b = ou_pair(theta=0.02, seed=7)
f = generate_entry_signal(fast_a, fast_b, min_deviation_sigma=0.0, bar_hours=BAR_HOURS)
s = generate_entry_signal(slow_a, slow_b, min_deviation_sigma=0.0, bar_hours=BAR_HOURS)
check("a faster-reverting pair reports a larger theta",
      f["theta_at_entry"] > s["theta_at_entry"], True)

# --------------------------------------------------------------------------
print()
print("=" * 110)
print("6. Declines rather than raising on unusable input")
print("=" * 110)
short_a, short_b = ou_pair(n=100)
check("fewer bars than one 7-day window -> None",
      generate_entry_signal(short_a, short_b, bar_hours=BAR_HOURS), None)
const_b = np.ones(900)
check("constant regressor -> None",
      generate_entry_signal(a, const_b, bar_hours=BAR_HOURS), None)
nan_a = a.copy(); nan_a[10] = np.nan
check("NaN in a leg -> None",
      generate_entry_signal(nan_a, b, bar_hours=BAR_HOURS), None)

# --------------------------------------------------------------------------
print()
print("=" * 110)
print("7. The returned dict is exactly what the exit and sizer read")
print("=" * 110)
expected_keys = {
    "entry_spread", "mu_at_entry", "sigma_at_entry", "z_at_entry",
    "beta_at_entry", "alpha_at_entry", "theta_at_entry", "take_profit_level",
    "r2_at_entry",
}
check("key set matches the documented contract", set(s_fire) == expected_keys, True)
for gone in ("reversion_probability", "expected_reversion_time",
             "regime_log_ratio", "deviation_sigma", "min_deviation_sigma"):
    check(f"removed field absent: {gone}", gone in s_fire, False)

print()
print("=" * 110)
print(f"{n_pass}/{n_pass + n_fail} assertions PASS")
print("=" * 110)
sys.exit(1 if n_fail else 0)
