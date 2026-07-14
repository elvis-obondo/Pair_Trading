import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
import pandas as pd
from data_loader import get_price_levels
from signal_generator import generate_entry_signal
from trade_diagnostics import spread_volatility_regime
from pair_analysis import compute_spread
from ou_model import fit_ou

df     = get_price_levels()
cutoff = df.index.max() - pd.Timedelta(days=30)
df     = df[df.index >= cutoff]
pair   = df[["AVAX", "LINK"]].dropna()
price_a = pair["AVAX"].values
price_b = pair["LINK"].values
params  = fit_ou(price_a, price_b)

# ── TEST 1 — coint gate ──────────────────────────────────────
np.random.seed(0)
rw_a = np.cumsum(np.random.normal(0, 1, 500)) + 100
rw_b = np.cumsum(np.random.normal(0, 1, 500)) + 100

from trade_diagnostics import pre_entry_coint_check
coint_p = pre_entry_coint_check(rw_a, rw_b)
result  = generate_entry_signal(rw_a, rw_b)
print("=== TEST 1: coint gate ===")
print(f"  coint_p: {coint_p:.4f}  (should be >> 0.10)")
print(f"  result:  {result}  (should be None)")
print(f"  {'PASS' if result is None and coint_p > 0.10 else 'FAIL'}")

# ── TEST 2 — regime gate ─────────────────────────────────────
np.random.seed(1)
noisy_a = price_a.copy()
noisy_a[-168:] = noisy_a[-168:] + np.random.normal(
    0, params.sigma * 10, 168
)
noisy_spread, _beta, _alpha = compute_spread(noisy_a, price_b)
actual_regime   = spread_volatility_regime(noisy_spread, params.sigma)

result = generate_entry_signal(
    noisy_a, price_b,
    coint_p_threshold=1.0,   # Gate 1 disabled
    theta_p_threshold=1.0,   # Gate 3 disabled
    prob_threshold=0.0,      # Gate 5 disabled
    regime_threshold=1.1,    # Gate 4 active — this should fire
)
print("\n=== TEST 2: regime gate ===")
print(f"  actual regime log ratio: {actual_regime:.4f}  (should be > 1.1)")
print(f"  result: {result}  (should be None)")
print(f"  {'PASS' if result is None and actual_regime > 1.1 else 'FAIL'}")

# ── TEST 3 — prob gate ───────────────────────────────────────
from ou_model import ou_reversion_probability
spread_arr, _beta, _alpha = compute_spread(price_a, price_b)
S             = np.asarray(spread_arr, dtype=float)
S             = S[np.isfinite(S)]
S0            = float(S[-1])
tau           = np.log(1.0 / 0.20) / params.theta
prob          = ou_reversion_probability(
                    S0, params.theta, params.mu, params.sigma, tau)

result = generate_entry_signal(
    price_a, price_b,
    prob_threshold=0.9999,   # Gate 5 active — this should fire
    coint_p_threshold=1.0,   # Gate 1 disabled
    theta_p_threshold=1.0,   # Gate 3 disabled
    regime_threshold=999.0,  # Gate 4 disabled
)
print("\n=== TEST 3: prob gate ===")
print(f"  actual prob: {prob:.4f}  (should be < 0.9999)")
print(f"  result: {result}  (should be None)")
print(f"  {'PASS' if result is None and prob < 0.9999 else 'FAIL'}")