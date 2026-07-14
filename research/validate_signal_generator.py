import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
import pandas as pd
from data_loader import get_price_levels
from signal_generator import generate_entry_signal

df     = get_price_levels()
cutoff = df.index.max() - pd.Timedelta(days=30)
df     = df[df.index >= cutoff]

pair    = df[["AVAX", "LINK"]].dropna()
price_a = pair["AVAX"].values
price_b = pair["LINK"].values

# ── Part 1: Gate isolation tests ──────────────────────────────────────────────

print("=== Part 1: Gate Isolation Tests ===")

# Test 1 — coint gate fires on non-cointegrated pair
np.random.seed(0)
rw_a = np.cumsum(np.random.normal(0, 1, 500)) + 100
rw_b = np.cumsum(np.random.normal(0, 1, 500)) + 100
result = generate_entry_signal(rw_a, rw_b)
status = "PASS" if result is None else "FAIL"
print(f"Gate 1 (coint) fires on random walks: {status}")

# Test 2 — regime gate fires on genuinely elevated volatility
from ou_model import fit_ou
from trade_diagnostics import spread_volatility_regime
from pair_analysis import compute_spread
params = fit_ou(price_a, price_b)
np.random.seed(1)
noisy_a = price_a + np.random.normal(0, params.sigma * 10, len(price_a))
result = generate_entry_signal(noisy_a, price_b)
noisy_spread, _beta, _alpha = compute_spread(noisy_a, price_b)
actual_regime = spread_volatility_regime(noisy_spread, params.sigma)
print(f"Gate 4 (regime) fires on elevated volatility:")
print(f"  actual regime log ratio: {actual_regime:.4f}")
print(f"  threshold: 1.1")
if result is None and actual_regime > 1.1:
    print("  PASS")
else:
    print("  FAIL")

# Test 3 — prob gate fires when threshold set impossibly high
result = generate_entry_signal(price_a, price_b, prob_threshold=0.9999)
status = "PASS" if result is None else "FAIL"
print(f"Gate 5 (prob) fires when threshold=0.9999: {status}")

# ── Part 2: Live signal check on AVAX/LINK ────────────────────────────────────

print()
print("=== Part 2: Live Signal Check (AVAX/LINK, default thresholds) ===")

signal = generate_entry_signal(price_a, price_b)

if signal is not None:
    print("Signal generated for AVAX/LINK:")
    print(f"  entry_spread:            {signal['entry_spread']:.6f}")
    print(f"  reversion_probability:   {signal['reversion_probability']:.4f}")
    print(f"  expected_reversion_time: {signal['expected_reversion_time']:.2f} hours")
    print(f"  mu_at_entry:             {signal['mu_at_entry']:.6f}")
    print(f"  sigma_at_entry:          {signal['sigma_at_entry']:.6f}")
    print(f"  take_profit_level:       {signal['take_profit_level']:.6f}")
    print(f"  regime_log_ratio:        {signal['regime_log_ratio']:.4f}")
    relaxed_signal = signal
else:
    print("No signal for AVAX/LINK at current defaults.")
    print("Relaxed-threshold pair state:")
    relaxed_signal = generate_entry_signal(
        price_a, price_b,
        prob_threshold=0.0,
        coint_p_threshold=1.0,
        regime_threshold=999.0,
        theta_p_threshold=1.0,
    )
    if relaxed_signal is not None:
        print(f"  entry_spread:            {relaxed_signal['entry_spread']:.6f}")
        print(f"  reversion_probability:   {relaxed_signal['reversion_probability']:.4f}")
        print(f"  expected_reversion_time: {relaxed_signal['expected_reversion_time']:.2f} hours")
        print(f"  mu_at_entry:             {relaxed_signal['mu_at_entry']:.6f}")
        print(f"  sigma_at_entry:          {relaxed_signal['sigma_at_entry']:.6f}")
        print(f"  take_profit_level:       {relaxed_signal['take_profit_level']:.6f}")
        print(f"  regime_log_ratio:        {relaxed_signal['regime_log_ratio']:.4f}")
    else:
        print("  (relaxed signal also returned None — OU fit likely failed)")

# ── Part 3: Take-profit sanity check ─────────────────────────────────────────

print()
print("=== Part 3: Take-Profit Sanity Check ===")

if relaxed_signal is not None:
    tp  = relaxed_signal["take_profit_level"]
    S0  = relaxed_signal["entry_spread"]
    mu  = relaxed_signal["mu_at_entry"]

    pct_captured = abs(S0 - tp) / abs(S0 - mu)

    print(f"Take profit sanity check:")
    print(f"  S0={S0:.6f}  mu={mu:.6f}  tp={tp:.6f}")
    print(f"  pct_captured={pct_captured:.4f}")
    if abs(pct_captured - 0.80) < 0.001:
        print("  PASS")
    else:
        print("  FAIL")
else:
    print("Skipped (no relaxed signal available).")
