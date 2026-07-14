import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
from signal_generator import generate_exit_signal

expected_reversion_time = 34.0
sigma_at_entry          = 0.002722

# ── Test 1: take profit fires, spread above mu (short direction) ──────────────

entry_signal = {
    "entry_spread":            0.010,
    "mu_at_entry":            -0.001,
    "take_profit_level":       0.002,
    "expected_reversion_time": expected_reversion_time,
    "beta_at_entry":           1.0,
    "alpha_at_entry":          0.0,
    "sigma_at_entry":          sigma_at_entry,
    "theta_at_entry":          0.0474,
    "reversion_probability":   0.80,
    "regime_log_ratio":        0.40,
}

result = generate_exit_signal(
    current_price_a = 0.001,
    current_price_b = 0.0,
    entry_signal    = entry_signal,
    hours_elapsed   = 10.0,
)

print("=== Test 1: take profit fires (spread above mu) ===")
print(f"exit_reason:    {result['exit_reason']}")
print(f"current_spread: {result['current_spread']:.6f}")
print(f"pnl_pct:        {result['pnl_pct']:.4f}")
pass1 = (result["exit_reason"] == "take_profit" and
         abs(result["pnl_pct"] - 0.8182) < 0.001)
print("PASS" if pass1 else "FAIL")

# ── Test 2: take profit fires, spread below mu (long direction) ───────────────

entry_signal = {
    "entry_spread":            -0.010,
    "mu_at_entry":             -0.001,
    "take_profit_level":       -0.002,
    "expected_reversion_time":  expected_reversion_time,
    "beta_at_entry":            1.0,
    "alpha_at_entry":           0.0,
    "sigma_at_entry":           sigma_at_entry,
    "theta_at_entry":           0.0474,
    "reversion_probability":    0.80,
    "regime_log_ratio":         0.40,
}

result = generate_exit_signal(
    current_price_a = -0.001,
    current_price_b =  0.0,
    entry_signal    = entry_signal,
    hours_elapsed   = 10.0,
)

print("\n=== Test 2: take profit fires (spread below mu) ===")
print(f"exit_reason:    {result['exit_reason']}")
print(f"current_spread: {result['current_spread']:.6f}")
print(f"pnl_pct:        {result['pnl_pct']:.4f}")
pass2 = (result["exit_reason"] == "take_profit" and
         abs(result["pnl_pct"] - 1.0) < 0.001)
print("PASS" if pass2 else "FAIL")

# ── Test 3: time stop fires unconditionally ───────────────────────────────────

entry_signal = {
    "entry_spread":            0.010,
    "mu_at_entry":            -0.001,
    "take_profit_level":       0.002,
    "expected_reversion_time": expected_reversion_time,
    "beta_at_entry":           1.0,
    "alpha_at_entry":          0.0,
    "sigma_at_entry":          sigma_at_entry,
    "theta_at_entry":          0.0474,
    "reversion_probability":   0.80,
    "regime_log_ratio":        0.40,
}

result = generate_exit_signal(
    current_price_a = 0.009,
    current_price_b = 0.0,
    entry_signal    = entry_signal,
    hours_elapsed   = 34.0,
)

print("\n=== Test 3: time stop fires unconditionally ===")
print(f"exit_reason:    {result['exit_reason']}")
print(f"current_spread: {result['current_spread']:.6f}")
print(f"pnl_pct:        {result['pnl_pct']:.4f}")
pass3 = (result["exit_reason"] == "time_stop" and
         abs(result["pnl_pct"] - 0.0909) < 0.001)
print("PASS" if pass3 else "FAIL")

# ── Test 4: no exit condition met, returns None ───────────────────────────────

entry_signal = {
    "entry_spread":            0.010,
    "mu_at_entry":            -0.001,
    "take_profit_level":       0.002,
    "expected_reversion_time": expected_reversion_time,
    "beta_at_entry":           1.0,
    "alpha_at_entry":          0.0,
    "sigma_at_entry":          sigma_at_entry,
    "theta_at_entry":          0.0474,
    "reversion_probability":   0.80,
    "regime_log_ratio":        0.40,
}

result = generate_exit_signal(
    current_price_a = 0.008,
    current_price_b = 0.0,
    entry_signal    = entry_signal,
    hours_elapsed   = 10.0,
)

print("\n=== Test 4: no exit condition met ===")
print(f"result: {result}")
pass4 = result is None
print("PASS" if pass4 else "FAIL")

# ── Tests 5 and 6: shared constants ──────────────────────────────────────────

sigma_stationary = 0.002722 / np.sqrt(2.0 * 0.0474)  # ≈ 0.00884
stop_distance    = 2.5 * sigma_stationary              # ≈ 0.02209

# ── Test 5: adverse move fires, spread above mu ───────────────────────────────

entry_signal_5 = {
    "entry_spread":            0.010,
    "mu_at_entry":            -0.001,
    "take_profit_level":       0.002,
    "expected_reversion_time": 34.0,
    "beta_at_entry":           1.0,
    "alpha_at_entry":          0.0,
    "sigma_at_entry":          0.002722,
    "theta_at_entry":          0.0474,
    "reversion_probability":   0.80,
    "regime_log_ratio":        0.40,
}

result = generate_exit_signal(
    current_price_a = 0.033,
    current_price_b = 0.0,
    entry_signal    = entry_signal_5,
    hours_elapsed   = 10.0,
    stop_sigma      = 2.5,
)

print("\n=== Test 5: adverse move fires (spread above mu) ===")
print(f"exit_reason:    {result['exit_reason']}")
print(f"current_spread: {result['current_spread']:.6f}")
print(f"pnl_pct:        {result['pnl_pct']:.4f}")
print(f"stop_sigma:     {result['stop_sigma']}")
pass5 = (result["exit_reason"] == "adverse_move" and
         result["stop_sigma"] == 2.5 and
         abs(result["pnl_pct"] - 2.0909) < 0.001)
print("PASS" if pass5 else "FAIL")

# ── Test 6: adverse move fires, spread below mu ───────────────────────────────

entry_signal_6 = {
    "entry_spread":            -0.010,
    "mu_at_entry":             -0.001,
    "take_profit_level":       -0.002,
    "expected_reversion_time":  34.0,
    "beta_at_entry":            1.0,
    "alpha_at_entry":           0.0,
    "sigma_at_entry":           0.002722,
    "theta_at_entry":           0.0474,
    "reversion_probability":    0.80,
    "regime_log_ratio":         0.40,
}

result = generate_exit_signal(
    current_price_a = -0.033,
    current_price_b =  0.0,
    entry_signal    = entry_signal_6,
    hours_elapsed   = 10.0,
    stop_sigma      = 2.5,
)

print("\n=== Test 6: adverse move fires (spread below mu) ===")
print(f"exit_reason:    {result['exit_reason']}")
print(f"current_spread: {result['current_spread']:.6f}")
print(f"pnl_pct:        {result['pnl_pct']:.4f}")
print(f"stop_sigma:     {result['stop_sigma']}")
pass6 = (result["exit_reason"] == "adverse_move" and
         result["stop_sigma"] == 2.5 and
         abs(result["pnl_pct"] - 2.5556) < 0.001)
print("PASS" if pass6 else "FAIL")
