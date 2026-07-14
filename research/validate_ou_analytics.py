import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
from ou_model import (
    ou_expected_spread,
    ou_spread_std,
    ou_confidence_interval,
    ou_reversion_probability,
    ou_expected_reversion_time,
)

theta = 0.0474
mu    = -0.0009
sigma = 0.0027
S0    = mu + 2 * (sigma / np.sqrt(2 * theta))

# ─────────────────────────────────────────────
# Part 1 — Analytical sanity checks
# ─────────────────────────────────────────────
print(f"=== Analytical Checks (theta={theta}, S0 ~ mu + 2*std) ===")
for tau in [6, 12, 24, 48]:
    e   = ou_expected_spread(S0, theta, mu, tau)
    s   = ou_spread_std(theta, sigma, tau)
    lo, hi = ou_confidence_interval(S0, theta, mu, sigma, tau)
    p   = ou_reversion_probability(S0, theta, mu, sigma, tau)
    rt  = ou_expected_reversion_time(S0, theta, mu)
    print(
        f"tau={tau:2d}h  E[S]={e:.6f}  std={s:.6f}  CI=({lo:.6f}, {hi:.6f})"
        f"  P(cross)={p:.4f}  E[revert]={rt:.2f} hrs"
    )

rt_default = ou_expected_reversion_time(S0, theta, mu, epsilon=1e-4)
print(f"Expected reversion time (epsilon=1e-4): {rt_default:.2f} hours")

# ─────────────────────────────────────────────
# Part 2 — Monotonicity checks
# ─────────────────────────────────────────────
taus = [1, 6, 12, 24, 48]

# Check 1 — E[S] moves toward mu as tau increases
es_vals = [ou_expected_spread(S0, theta, mu, t) for t in taus]
dists   = [abs(v - mu) for v in es_vals]
converges = all(dists[i] >= dists[i + 1] for i in range(len(dists) - 1))
if converges:
    print("E[S] converges to mu: PASS")
else:
    print(f"E[S] converges to mu: FAIL: {es_vals}")

# Check 2 — std increases with tau
std_vals   = [ou_spread_std(theta, sigma, t) for t in taus]
std_mono   = all(std_vals[i] <= std_vals[i + 1] for i in range(len(std_vals) - 1))
if std_mono:
    print("std increases with tau: PASS")
else:
    print(f"std increases with tau: FAIL: {std_vals}")

# Check 3 — P(cross) increases with tau
p_vals  = [ou_reversion_probability(S0, theta, mu, sigma, t) for t in taus]
p_mono  = all(p_vals[i] <= p_vals[i + 1] for i in range(len(p_vals) - 1))
if p_mono:
    print("P(cross) increases with tau: PASS")
else:
    print(f"P(cross) increases with tau: FAIL: {p_vals}")

# Check 4 — P(cross) at tau=0 is 0
p_tau0 = ou_reversion_probability(S0, theta, mu, sigma, 0)
if p_tau0 == 0.0:
    print("P(cross, tau=0) == 0: PASS")
else:
    print(f"P(cross, tau=0) == 0: FAIL: {p_tau0}")

# Check 5 — P(cross) at S0==mu is 1
p_at_mu = ou_reversion_probability(mu, theta, mu, sigma, 24)
if p_at_mu == 1.0:
    print("P(cross, S0==mu) == 1: PASS")
else:
    print(f"P(cross, S0==mu) == 1: FAIL: {p_at_mu}")

# Check 6 — E[revert] == 0 when S0==mu
rt_at_mu = ou_expected_reversion_time(mu, theta, mu)
if rt_at_mu == 0.0:
    print("E[revert]==0 at mu: PASS")
else:
    print(f"E[revert]==0 at mu: FAIL: {rt_at_mu}")

# ─────────────────────────────────────────────
# Part 3 — Monte Carlo verification
# ─────────────────────────────────────────────
n_paths   = 10_000
tau_hours = 24

np.random.seed(42)
crossed_count = 0
for _ in range(n_paths):
    S       = S0
    crossed = False
    for _t in range(tau_hours):
        eps = np.random.normal(0, 1)
        S   = S + theta * (mu - S) + sigma * eps
        if S <= mu:
            crossed = True
            break
    if crossed:
        crossed_count += 1

mc_prob       = crossed_count / n_paths
analytic_prob = ou_reversion_probability(S0, theta, mu, sigma, tau_hours)
diff          = abs(mc_prob - analytic_prob)

print(f"=== Monte Carlo Verification (n=10000, tau=24h) ===")
print(f"  Analytic P(cross) = {analytic_prob:.4f}")
print(f"  Monte Carlo P(cross) = {mc_prob:.4f}")
print(f"  Difference = {diff:.4f}")
if diff < 0.05:
    print("  Verdict: PASS — reflection principle accurate within 5%")
else:
    print("  Verdict: FAIL — difference exceeds 5%, investigate")
