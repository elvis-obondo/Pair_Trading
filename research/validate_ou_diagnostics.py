import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
import pandas as pd
from data_loader import get_price_levels
from ou_model import fit_ou, ou_residual_diagnostics

# --- Part 1: Synthetic OU regression test ---

theta_true = 0.05
mu_true    = 0.0
sigma_true = 0.003
n_steps    = 720

np.random.seed(42)

S   = np.zeros(n_steps)
eps = np.random.normal(0, 1, n_steps)
for t in range(1, n_steps):
    S[t] = S[t-1] + theta_true * (mu_true - S[t-1]) + sigma_true * eps[t]

price_b = np.cumsum(np.random.normal(0, 0.01, n_steps)) + 10.0
price_a = price_b + S

p = fit_ou(price_a, price_b)

print("Synthetic test:")
print(f"  {'theta_true='+f'{theta_true:.4f}':<19}recovered={p.theta:.4f}  diff={abs(p.theta - theta_true):.4f}")
print(f"  {'mu_true='+f'{mu_true:.4f}':<19}recovered={p.mu:.4f}  diff={abs(p.mu - mu_true):.4f}")
print(f"  {'sigma_true='+f'{sigma_true:.4f}':<19}recovered={p.sigma:.4f}  diff={abs(p.sigma - sigma_true):.4f}")

failures = []
if abs(p.theta - theta_true) >= 0.02:
    failures.append("theta")
if abs(p.mu - mu_true) >= 0.5:
    failures.append("mu")
if abs(p.sigma - sigma_true) >= 0.002:
    failures.append("sigma")

if not failures:
    print("Synthetic test: PASS")
else:
    print(f"Synthetic test: FAIL — {', '.join(failures)}")

# --- Part 2: Live pair diagnostics ---

print()

df     = get_price_levels()
cutoff = df.index.max() - pd.Timedelta(days=30)
df     = df[df.index >= cutoff]

# TODO: replace with current top tradeable pair from pair_analysis.py
pair    = df[["AVAX", "LINK"]].dropna()
price_a = pair["AVAX"].values
price_b = pair["LINK"].values

p              = fit_ou(price_a, price_b)
half_life_days = np.log(2) / p.theta / 24

print("Live pair: AVAX/LINK (last 30 days)")
print(f"  theta={p.theta:.4f}  mu={p.mu:.4f}  sigma={p.sigma:.4f}")
print(f"  implied half-life={half_life_days:.2f} days")

diag = ou_residual_diagnostics(price_a, price_b)
print("Residual diagnostics:")
print(f"  jb_stat={diag.jb_stat:.4f}    jb_p={diag.jb_p:.4f}")
print(f"  lb_stat={diag.lb_stat:.4f}    lb_p={diag.lb_p:.4f}")
print(f"  skewness={diag.skewness:.4f}   excess_kurtosis={diag.excess_kurtosis:.4f}")
print(f"  theta_tstat={diag.theta_tstat:.4f}  theta_p={diag.theta_p:.4f}")
