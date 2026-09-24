"""Prove rolling_spread.py reproduces exit_sweep.py's geometry exactly.

WHY THIS IS THE IMPORTANT VALIDATION

Every settled parameter -- 3.0 entry, 0.5 stop, take-profit at mu -- was scored
against candidate trades built by exit_sweep.build_pair_paths. If the live path
computes its beta/mu/sigma even slightly differently, those thresholds are being
applied to a different quantity than the one they were calibrated on, and no
amount of downstream testing would reveal it. So this does not test
rolling_spread against hand-written expectations; it tests it against the
research code's own inline computation, on real prices.

Run: python research/validate_rolling_spread.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd

from rolling_spread import (
    rolling_spread_stats, last_bar, entry_window_bars, ENTRY_WINDOW_DAYS,
)
from reversion_dataset import ENTRY_WINDOW_BARS
import hedge_estimators as he

TOL = 1e-12
n_pass = n_fail = 0


def check(name, got, exp, tol=TOL):
    global n_pass, n_fail
    if isinstance(got, np.ndarray):
        both_nan = np.isnan(got) & np.isnan(exp)
        close = np.isclose(got, exp, rtol=0, atol=tol, equal_nan=True)
        ok = bool((close | both_nan).all())
        detail = f"max|diff|={np.nanmax(np.abs(got - exp)):.3e}" if ok else "MISMATCH"
    else:
        ok = (np.isnan(got) and np.isnan(exp)) or abs(got - exp) <= tol
        detail = f"got={got!r} expected={exp!r}"
    n_pass, n_fail = n_pass + ok, n_fail + (not ok)
    print(f"{name + ':':46s} {detail:34s} {'PASS' if ok else 'FAIL'}")


# --------------------------------------------------------------------------
# 1. Window constants agree with the research datasets
# --------------------------------------------------------------------------
print("=" * 92)
print("1. Window constants")
print("=" * 92)
check("entry_window_bars(0.5) == 336", float(entry_window_bars(0.5)), 336.0)
check("matches reversion_dataset ENTRY_WINDOW_BARS",
      float(entry_window_bars(0.5)), float(ENTRY_WINDOW_BARS))
check("ENTRY_WINDOW_DAYS == 7", float(ENTRY_WINDOW_DAYS), 7.0)

# --------------------------------------------------------------------------
# 2. Against exit_sweep.build_pair_paths' inline computation, on real prices
# --------------------------------------------------------------------------
print()
print("=" * 92)
print("2. Against exit_sweep's own inline geometry (real prices)")
print("=" * 92)

from data_loader import get_price_levels

df = get_price_levels(align=False)
# Pick the two most-covered tickers so the joint window is long and real.
cov = df.notna().sum().sort_values(ascending=False)
a, b = cov.index[0], cov.index[1]
pair = df[[a, b]].dropna()
pa, pb = pair[a].to_numpy(), pair[b].to_numpy()
print(f"pair = {a}/{b}, {len(pair)} joint bars\n")

# THE HEDGE RATIO DIVERGED FROM exit_sweep ON 2026-09-24, DELIBERATELY.
#
# exit_sweep fitted OLS of A on B, and 3.0/0.5 were scored on that geometry. The
# shipped estimator is now the symmetric vol-matched ratio, because the OLS
# left-hand side was chosen alphabetically by itertools.combinations and that
# arbitrary choice moved end equity across a $626 band. So the old equality
# CANNOT hold any more, and asserting it would mean reverting the change.
#
# What is checked instead, in order of what would actually go wrong:
#   1. everything downstream of beta is still built from the shipped beta the
#      same way exit_sweep built it from its own -- same alpha, same spread,
#      same rolling mean, same ddof=1 std, same z. Only the ratio changed.
#   2. the new invariant that replaces the old identity: the estimator is
#      exactly symmetric, so the pair is unordered.
#   3. the divergence from the calibration geometry is REPORTED, not hidden, so
#      nobody reads a threshold as calibrated when it is not.
r = rolling_spread_stats(pa, pb, bar_hours=0.5)

# 1. the pipeline around beta, rebuilt from the SHIPPED beta using exit_sweep's
#    own inline steps (exit_sweep.py:101-105, 118).
spread_exp = pa - r.beta * pb - r.alpha
s_roll = pd.Series(spread_exp)
mu_exp = s_roll.rolling(ENTRY_WINDOW_BARS).mean().to_numpy()
sg_exp = s_roll.rolling(ENTRY_WINDOW_BARS).std().to_numpy()
z_exp = np.where(sg_exp > 0, (spread_exp - mu_exp) / sg_exp, np.nan)
check("alpha == mean(a) - beta*mean(b)", r.alpha,
      pd.Series(pa).rolling(ENTRY_WINDOW_BARS).mean().to_numpy()
      - r.beta * pd.Series(pb).rolling(ENTRY_WINDOW_BARS).mean().to_numpy())
check("spread == a - beta*b - alpha", r.spread, spread_exp)
check("mu (rolling mean, exit_sweep's step)", r.mu, mu_exp)
check("sigma (rolling std, ddof=1)", r.sigma, sg_exp)
check("z == (spread - mu) / sigma", r.z, z_exp)

# 2. the invariant that replaces beta(A|B)*beta(B|A) = r2.
rev = rolling_spread_stats(pb, pa, bar_hours=0.5)
m = np.isfinite(r.beta) & np.isfinite(rev.beta)
check("beta(a,b) * beta(b,a) == 1 (the labelling cannot matter)",
      r.beta[m] * rev.beta[m], np.ones(int(m.sum())), tol=1e-9)
check("r2 is unchanged by swapping the legs", r.r2[m], rev.r2[m])

# 3. report the divergence from the geometry 3.0 and 0.5 were calibrated on.
#    The reference MUST be hedge_estimators' explicit "ols", not
#    reversion_dataset.rolling_beta_alpha -- that name is re-exported FROM this
#    module (reversion_dataset.py:81), so using it compares the shipped
#    estimator against itself and reports x1.000 no matter what changed.
beta_ols = he.rolling_beta(pa, pb, ENTRY_WINDOW_BARS, "ols")
mo = np.isfinite(beta_ols) & np.isfinite(r.beta)
ratio = np.abs(r.beta[mo]) / np.abs(beta_ols[mo])
print(f"\n  [INFO] shipped |beta| vs exit_sweep's OLS |beta|: median x{np.median(ratio):.3f}")
print(f"  [INFO] shipped sigma vs the same on OLS beta: "
      f"median x{np.nanmedian(r.sigma[mo] / pd.Series(pa - beta_ols*pb - (pd.Series(pa).rolling(ENTRY_WINDOW_BARS).mean().to_numpy() - beta_ols*pd.Series(pb).rolling(ENTRY_WINDOW_BARS).mean().to_numpy())).rolling(ENTRY_WINDOW_BARS).std().to_numpy()[mo]):.3f}")
print("  [INFO] 3.0 and 0.5 were scored on the OLS geometry. They have NOT been")
print("  [INFO] re-derived; the switch was justified PAIRED at each stop width.")

# --------------------------------------------------------------------------
# 3. No look-ahead: truncating the history must not change earlier bars
# --------------------------------------------------------------------------
print()
print("=" * 92)
print("3. No look-ahead (a bar's stats never depend on later bars)")
print("=" * 92)
cut = len(pa) // 2
r_cut = rolling_spread_stats(pa[:cut], pb[:cut], bar_hours=0.5)
check("sigma[:cut] unchanged when future is removed", r_cut.sigma, r.sigma[:cut])
check("beta[:cut] unchanged when future is removed", r_cut.beta, r.beta[:cut])
check("z[:cut] unchanged when future is removed", r_cut.z, r.z[:cut])

# --------------------------------------------------------------------------
# 4. last_bar agrees with the array form, and declines when undetermined
# --------------------------------------------------------------------------
print()
print("=" * 92)
print("4. last_bar helper")
print("=" * 92)
lb = last_bar(pa, pb, bar_hours=0.5)
check("last_bar.sigma == sigma[-1]", lb.sigma, float(r.sigma[-1]))
check("last_bar.z == z[-1]", lb.z, float(r.z[-1]))
check("last_bar.beta == beta[-1]", lb.beta, float(r.beta[-1]))

short = last_bar(pa[:100], pb[:100], bar_hours=0.5)
print(f"{'short input (100 bars < 336) -> None:':46s} "
      f"{'got ' + repr(short):34s} {'PASS' if short is None else 'FAIL'}")
n_pass, n_fail = n_pass + (short is None), n_fail + (short is not None)

# --------------------------------------------------------------------------
# 5. Degenerate input returns NaN rather than raising
# --------------------------------------------------------------------------
print()
print("=" * 92)
print("5. Degenerate input declines instead of raising")
print("=" * 92)
w = entry_window_bars(0.5)
for label, xa, xb in [
    ("all-NaN leg", np.full(w + 10, np.nan), pb[:w + 10]),
    ("constant regressor", pa[:w + 10], np.ones(w + 10)),
    ("mismatched lengths", pa[:w + 10], pb[:w + 5]),
]:
    try:
        out = rolling_spread_stats(xa, xb, bar_hours=0.5)
        ok = bool(np.isnan(out.sigma).all())
        detail = "all-NaN sigma" if ok else "returned finite values"
    except Exception as exc:
        ok, detail = False, f"RAISED {type(exc).__name__}"
    n_pass, n_fail = n_pass + ok, n_fail + (not ok)
    print(f"{label + ':':46s} {detail:34s} {'PASS' if ok else 'FAIL'}")

print()
print("=" * 92)
print(f"{n_pass}/{n_pass + n_fail} assertions PASS")
print("=" * 92)
sys.exit(1 if n_fail else 0)
