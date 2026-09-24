"""PASS/FAIL for hedge_estimators.py. Hand-run, no pytest.

    python research/validate_hedge_estimators.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd

from universe_panel import load_panel, usable_tickers, tradeable_pairs
from rolling_spread import (rolling_beta_alpha as rs_beta_alpha,
                            rolling_r2, min_bars_required)
import hedge_estimators as he

W = 336
checks = []


def check(name, ok, detail=""):
    checks.append((name, bool(ok)))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))


panel = load_panel().loc[:"2026-09-21 00:00:00"].tail(min_bars_required(0.5) + 35 * 48)
tk = usable_tickers(panel, 0.5)
pairs = tradeable_pairs(tk)[:40]
arr = {t: panel[t].to_numpy(dtype=float) for t in tk}
print(f"{len(tk)} tickers, {len(pairs)} pairs sampled\n")

# ---- 1. ols reproduces the shipped rolling_spread implementation exactly ----
# If this drifts, the comparison is against a straw man rather than the live rule.
worst = 0.0
for a, b in pairs:
    got = he.rolling_beta(arr[a], arr[b], W, "ols")
    want, _ = rs_beta_alpha(arr[a], arr[b], W)
    m = np.isfinite(got) & np.isfinite(want)
    worst = max(worst, float(np.abs(got[m] - want[m]).max()))
check("ols matches rolling_spread.rolling_beta_alpha", worst < 1e-12,
      f"max abs diff {worst:.2e}")

# ---- 2. alpha matches too ----
worst = 0.0
for a, b in pairs:
    _, ga = he.rolling_beta_alpha(arr[a], arr[b], W, "ols")
    _, wa = rs_beta_alpha(arr[a], arr[b], W)
    m = np.isfinite(ga) & np.isfinite(wa)
    worst = max(worst, float(np.abs(ga[m] - wa[m]).max()))
check("ols alpha matches rolling_spread", worst < 1e-12, f"max abs diff {worst:.2e}")

# ---- 3. THE HEADLINE: symmetry is exact for tls and ratio ----
# beta(a,b)*beta(b,a) == 1 means the pair is genuinely unordered, which is what
# collapses the $626 labelling band. Anything short of exact is not symmetry.
for est in he.SYMMETRIC:
    worst = 0.0
    for a, b in pairs:
        f = he.rolling_beta(arr[a], arr[b], W, est)
        r = he.rolling_beta(arr[b], arr[a], W, est)
        m = np.isfinite(f) & np.isfinite(r)
        worst = max(worst, float(np.abs(f[m] * r[m] - 1.0).max()))
    check(f"{est}: beta(a,b) * beta(b,a) == 1 exactly", worst < 1e-9,
          f"max abs deviation {worst:.2e}")

# ---- 4. and ols is NOT symmetric -- it equals r2, the identity behind the band ----
worst = 0.0
for a, b in pairs:
    f = he.rolling_beta(arr[a], arr[b], W, "ols")
    r = he.rolling_beta(arr[b], arr[a], W, "ols")
    r2 = rolling_r2(arr[a], arr[b], W)
    m = np.isfinite(f) & np.isfinite(r) & np.isfinite(r2)
    worst = max(worst, float(np.abs(f[m] * r[m] - r2[m]).max()))
check("ols: beta(a,b) * beta(b,a) == r2", worst < 1e-9, f"max abs diff {worst:.2e}")

# ---- 5. tls brackets ols: |tls| >= |ols|, the attenuation correction ----
bad, n = 0, 0
for a, b in pairs:
    o = he.rolling_beta(arr[a], arr[b], W, "ols")
    t = he.rolling_beta(arr[a], arr[b], W, "tls")
    m = np.isfinite(o) & np.isfinite(t)
    n += int(m.sum())
    bad += int((np.abs(t[m]) < np.abs(o[m]) - 1e-12).sum())
check("|tls| >= |ols| everywhere (errors-in-variables correction)", bad == 0,
      f"{bad} of {n:,} violations")

# ---- 6. every estimator agrees on the SIGN -- symmetry cannot fix a negative beta
bad = 0
for a, b in pairs:
    bs = {e: he.rolling_beta(arr[a], arr[b], W, e) for e in he.ESTIMATORS}
    m = np.all([np.isfinite(v) for v in bs.values()], axis=0)
    sg = [np.sign(v[m]) for v in bs.values()]
    bad += int((~((sg[0] == sg[1]) & (sg[1] == sg[2]))).sum())
check("all three estimators share beta's sign", bad == 0, f"{bad} disagreements")

# ---- 7. nothing looks forward ----
worst = 0.0
cut = len(panel) - 400
for a, b in pairs[:10]:
    for est in he.ESTIMATORS:
        full = he.rolling_beta(arr[a], arr[b], W, est)
        part = he.rolling_beta(arr[a][:cut], arr[b][:cut], W, est)
        m = np.isfinite(part)
        worst = max(worst, float(np.abs(full[:cut][m] - part[m]).max()))
check("truncating the future leaves earlier bars unchanged", worst < 1e-12,
      f"max abs diff {worst:.2e}")

# ---- 8. cost and liquidation algebra ----
check("cost_in_spread_units grows with |beta|",
      float(he.cost_in_spread_units(3.0, 0.001)) > float(he.cost_in_spread_units(0.4, 0.001)),
      f"beta 0.4 -> {float(he.cost_in_spread_units(0.4, 0.001)):.6f}, "
      f"beta 3.0 -> {float(he.cost_in_spread_units(3.0, 0.001)):.6f}")
check("liquidation_distance = (1+|beta|)/leverage",
      abs(float(he.liquidation_distance(1.0, 20.0)) - 0.10) < 1e-12,
      f"beta 1, 20x -> {float(he.liquidation_distance(1.0, 20.0)):.4f}")
check("a negative beta uses |beta| in both",
      abs(float(he.liquidation_distance(-2.0, 20.0))
          - float(he.liquidation_distance(2.0, 20.0))) < 1e-15)

# ---- 9. an unknown estimator is refused, not silently defaulted ----
try:
    he.rolling_beta(arr[pairs[0][0]], arr[pairs[0][1]], W, "pca")
    ok = False
except ValueError:
    ok = True
check("an unknown estimator name raises", ok)

n_pass = sum(1 for _, ok in checks if ok)
print(f"\n{n_pass}/{len(checks)} checks passed")
sys.exit(0 if n_pass == len(checks) else 1)
