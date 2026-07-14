import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
from position_sizer import compute_position_size


entry_signal = {
    "sigma_at_entry": 0.002722,
    "theta_at_entry": 0.0474,
    "beta_at_entry":  1.2,
    "entry_spread":   0.010,
    "mu_at_entry":   -0.001,
}


# =============================================================================
# Test 1 — Normal case: verify all five output fields
# =============================================================================

capital         = 1000.0
risk_budget_pct = 0.01
stop_sigma      = 2.5

# sigma_stationary = 0.002722 / sqrt(2 * 0.0474)
#                  = 0.002722 / sqrt(0.0948)
#                  = 0.002722 / 0.307923...
#                  ≈ 0.008840
#
# risk_unit        = 2.5 * 0.008840 ≈ 0.022099
#
# fraction         = 0.01 / 0.022099 ≈ 0.452527
#
# leg_a_notional   = 0.452527 * 100_000 ≈ 45_252.70
# leg_b_notional   = 1.2 * 0.452527 * 100_000 ≈ 54_303.24
# total_deployed   = 45_252.70 + 54_303.24 ≈ 99_555.94

result = compute_position_size(
    entry_signal    = entry_signal,
    capital         = capital,
    risk_budget_pct = risk_budget_pct,
    stop_sigma      = stop_sigma,
)

expected_sigma_stationary = 0.002722 / np.sqrt(2.0 * 0.0474)
expected_fraction         = 0.01 / (2.5 * expected_sigma_stationary)
expected_leg_a            = expected_fraction * capital
expected_leg_b            = 1.2 * expected_fraction * capital
expected_total            = expected_leg_a + expected_leg_b

print("=== Test 1: Normal case ===")
for field, exp, tol, fmt in [
    ("sigma_stationary", expected_sigma_stationary, 1e-6,  "X.XXXXXX"),
    ("fraction",         expected_fraction,         1e-6,  "X.XXXXXX"),
    ("leg_a_notional",   expected_leg_a,            0.01,  "XXXXX.XX"),
    ("leg_b_notional",   expected_leg_b,            0.01,  "XXXXX.XX"),
    ("total_deployed",   expected_total,            0.01,  "XXXXX.XX"),
]:
    res_val = result[field]
    status  = "PASS" if abs(res_val - exp) < tol else "FAIL"
    print(f"{field + ':':20s} result={res_val:.6f}  expected={exp:.6f}  {status}")


# =============================================================================
# Test 2 — Degenerate inputs return None
# =============================================================================

print("\n=== Test 2: Degenerate inputs ===")

bad_signal_a = dict(entry_signal)
bad_signal_a["theta_at_entry"] = 0.0
result_a = compute_position_size(bad_signal_a, capital=capital)
print(f"Sub-case A (theta=0.0):         result={result_a}  {'PASS' if result_a is None else 'FAIL'}")

bad_signal_b = dict(entry_signal)
bad_signal_b["sigma_at_entry"] = np.nan
result_b = compute_position_size(bad_signal_b, capital=capital)
print(f"Sub-case B (sigma=nan):         result={result_b}  {'PASS' if result_b is None else 'FAIL'}")

result_c = compute_position_size(entry_signal, capital=-50_000.0)
print(f"Sub-case C (capital=-50000):    result={result_c}  {'PASS' if result_c is None else 'FAIL'}")


# =============================================================================
# Test 3 — stop_sigma sensitivity: wider stop → smaller fraction
# =============================================================================

result_tight = compute_position_size(
    entry_signal    = entry_signal,
    capital         = capital,
    risk_budget_pct = 0.01,
    stop_sigma      = 2.0,
)
result_wide = compute_position_size(
    entry_signal    = entry_signal,
    capital         = capital,
    risk_budget_pct = 0.01,
    stop_sigma      = 3.0,
)

# Wider stop → larger risk_unit → smaller fraction needed to keep dollar risk fixed.
# A trade sized to a 3-sigma stop risks the same dollar amount as one sized to a
# 2-sigma stop, but the position is smaller because the stop is further away.

direction_ok = result_tight["fraction"] > result_wide["fraction"]

print("\n=== Test 3: stop_sigma sensitivity ===")
print(f"fraction at stop_sigma=2.0: {result_tight['fraction']:.6f}")
print(f"fraction at stop_sigma=3.0: {result_wide['fraction']:.6f}")
print(f"Direction correct (tight > wide): {'PASS' if direction_ok else 'FAIL'}")
