"""The bulk backtest screen must equal the live per-bar scan, exactly.

WHY THIS IS THE LOAD-BEARING CHECK

The backtest screens every pair once over the whole window; live screens every
pair at one bar. If those two disagree, the backtest measures a strategy that is
not the one that will trade, and the discrepancy would only surface months later
as unexplained divergence between paper and backtest. So this does not check the
bulk screen against hand-written expectations -- it checks it against
generate_entry_signal, the function live actually calls.

Run: python research/validate_backtest_screen.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd

from universe_panel import load_panel, usable_tickers, tradeable_pairs
from rolling_spread import min_bars_required
from signal_generator import generate_entry_signal
from scanner import scan
from backtest_screen import build_screen, rank_bar, theta_at

n_pass = n_fail = 0
BH, MIN_DEV = 0.5, 3.0
NEED = min_bars_required(BH)


def check(name, ok, detail=""):
    global n_pass, n_fail
    ok = bool(ok)
    n_pass, n_fail = n_pass + ok, n_fail + (not ok)
    print(f"{name + ':':58s} {str(detail)[:28]:30s} {'PASS' if ok else 'FAIL'}")


# A window small enough to also run the slow path on, for a like-for-like test.
N_EVAL = 6
panel = load_panel(tail_bars=NEED + N_EVAL)
tickers = usable_tickers(panel, BH)
pairs = tradeable_pairs(tickers)
arrays = {t: panel[t].to_numpy(dtype=float) for t in tickers}

print("=" * 104)
print(f"1. Bulk screen over {N_EVAL} bars vs the live scan, bar by bar")
print("=" * 104)
screen = build_screen(panel, pairs, NEED, MIN_DEV, BH, progress_every=0)
by_bar = {b: g for b, g in screen.groupby("bar", sort=False)}
print(f"   bulk screen: {len(screen)} candidate rows over {len(by_bar)} bars\n")

geom = ["entry_spread", "mu_at_entry", "sigma_at_entry", "z_at_entry",
        "beta_at_entry", "alpha_at_entry"]

# Relative, not absolute. pandas' rolling uses a streaming update, so a
# 671-element window and a longer series that CONTAINS that window accumulate
# in a different order and disagree in the last bits of float64. Measured across
# these fields the relative error tops out around 3e-11, on values of magnitude
# ~3. 1e-9 is ~30x looser than the observed round-off and still ~1e8 times
# tighter than any real logic difference would be: the largest z discrepancy is
# 1.5e-11 against a 3.0 threshold, so it would take 2e11 times that to flip one
# entry decision. An absolute tolerance cannot express this -- alpha runs to
# magnitude 10 while mu sits near 0.03.
GEOM_RTOL = 1e-9

# BUT A PURE RELATIVE TOLERANCE IS WRONG FOR THE SPREAD-SCALE FIELDS, and it
# took the 2026-09-24 estimator switch to expose it. entry_spread, mu and alpha
# are spread LEVELS in log units, and a level can pass through zero: after the
# switch HMSTR/KAITO's mu landed at 8.83e-08, where an absolute disagreement of
# 1.8e-14 -- pure float noise -- is a 2.0e-07 RELATIVE error. Nothing was wrong;
# the denominator had just vanished.
#
# So those three are compared in the unit every consumer actually reads them in.
# mu is only ever used as (spread - mu)/sigma and the stop is a multiple of
# sigma, so a disagreement in a spread level matters only relative to SIGMA.
#
# Measured worst disagreement, in sigma units, over 2,031 candidates:
#
#     entry_spread   1.17e-11 sigma
#     mu_at_entry    4.33e-12 sigma
#     alpha_at_entry 1.45e-09 sigma   <- alpha runs to magnitude 10, hence the
#                                        largest absolute round-off
#     z_at_entry     1.81e-11 absolute, against a 3.0 threshold
#
# 1e-6 sigma is ~692x the worst observed, so it will not flag round-off, and it
# would take ~2e11 times the worst z error to flip a single entry decision. Note
# a naive 1e-9 sigma is TOO TIGHT: alpha's own magnitude makes its round-off
# larger than mu's even though it matters less.
#
# sigma, z and beta keep the relative test: none of them goes near zero (sigma>0
# is enforced, |z|>=3 by construction, and the symmetric beta cannot reach zero
# except at exactly zero covariance).
SPREAD_SCALE_FIELDS = ("entry_spread", "mu_at_entry", "alpha_at_entry")
SIGMA_ATOL = 1e-6
total_live = total_bulk = mismatches = geom_errors = 0
for i in range(NEED, len(panel)):
    live = scan(panel.iloc[:i + 1].tail(NEED), pairs,
                min_deviation_sigma=MIN_DEV, bar_hours=BH)
    bulk = by_bar.get(i, pd.DataFrame(columns=screen.columns))
    live_set = {(str(r.ticker_a), str(r.ticker_b)) for r in live.itertuples(index=False)}
    bulk_set = {(str(r.ticker_a), str(r.ticker_b)) for r in bulk.itertuples(index=False)}
    total_live += len(live_set)
    total_bulk += len(bulk_set)
    mismatches += len(live_set ^ bulk_set)
    # Same pairs is necessary but not sufficient -- the numbers must match too.
    bl = {(str(r.ticker_a), str(r.ticker_b)): r
          for r in bulk.itertuples(index=False)}
    for r in live.itertuples(index=False):
        row = bl.get((str(r.ticker_a), str(r.ticker_b)))
        if row is None:
            continue
        for f in geom:
            x, y = getattr(r, f), getattr(row, f)
            if f in SPREAD_SCALE_FIELDS:
                # a fraction of a sigma, not a fraction of the level itself
                if abs(x - y) > SIGMA_ATOL * abs(getattr(row, "sigma_at_entry")):
                    geom_errors += 1
            elif not np.isclose(x, y, rtol=GEOM_RTOL, atol=1e-15):
                geom_errors += 1

check("same candidate SET at every bar", mismatches == 0,
      f"{mismatches} differing of {total_live}")
check("live and bulk found the same count", total_live == total_bulk,
      f"live {total_live} / bulk {total_bulk}")
check(f"every geometry field matches to {GEOM_RTOL:g} relative", geom_errors == 0,
      f"{geom_errors} field mismatches")
check("the test actually exercised candidates", total_live > 0, f"{total_live}")

print()
print("=" * 104)
print("2. theta: the lazy fit equals generate_entry_signal's")
print("=" * 104)
last = len(panel) - 1
live_last = scan(panel, pairs, min_deviation_sigma=MIN_DEV, bar_hours=BH)
ranked = rank_bar(by_bar.get(last, pd.DataFrame(columns=screen.columns)),
                  arrays, 1.0, BH)
errs = both_nan = 0
lut = {(str(r.ticker_a), str(r.ticker_b)): r.theta_at_entry
       for r in live_last.itertuples(index=False)}
for r in ranked.itertuples(index=False):
    exp = lut.get((str(r.ticker_a), str(r.ticker_b)))
    if exp is None:
        continue
    if np.isnan(exp) and np.isnan(r.theta_at_entry):
        both_nan += 1
    elif not np.isclose(exp, r.theta_at_entry, rtol=GEOM_RTOL, atol=1e-15):
        errs += 1
check("theta identical to the live path", errs == 0,
      f"{errs} of {len(ranked)} differ")
check("NaN theta agrees on both sides", True, f"{both_nan} both-NaN")
check("take_profit_level == mu at tp=1.0",
      bool(np.allclose(ranked.take_profit_level, ranked.mu_at_entry)))

print()
print("=" * 104)
print("3. Ranking contract matches scanner.scan()")
print("=" * 104)
th = ranked["theta_at_entry"]
check("ranked block sorted descending", th.dropna().is_monotonic_decreasing,
      f"{th.notna().sum()} ranked")
n_nan = int(th.isna().sum())
check("NaN theta kept, sorted last",
      bool(th.tail(n_nan).isna().all()) if n_nan else True, f"{n_nan} unranked")
check("columns Portfolio.fill_slots needs are present",
      all(c in ranked.columns for c in
          ["ticker_a", "ticker_b", "entry_spread", "mu_at_entry",
           "sigma_at_entry", "z_at_entry", "beta_at_entry", "alpha_at_entry",
           "theta_at_entry", "take_profit_level"]))

print()
print("=" * 104)
print("4. No look-ahead: truncating the future cannot change a past bar")
print("=" * 104)
cut = len(panel) - 2
short = build_screen(panel.iloc[:cut + 1], pairs, NEED, MIN_DEV, BH, progress_every=0)
a_rows = screen[screen.bar <= cut].reset_index(drop=True)
b_rows = short[short.bar <= cut].reset_index(drop=True)
check("same rows for bars that both runs cover", len(a_rows) == len(b_rows),
      f"{len(a_rows)} vs {len(b_rows)}")
if len(a_rows) == len(b_rows) and len(a_rows):
    # This one IS exact: both sides run the same bulk code path, so the only
    # difference is the trailing rows, and round-off cannot enter.
    same = all(np.allclose(a_rows[f].to_numpy(float), b_rows[f].to_numpy(float),
                           rtol=0, atol=0) for f in geom)
    check("geometry BIT-IDENTICAL with the future removed", same)
    check("same pairs, same order",
          a_rows.ticker_a.astype(str).tolist() == b_rows.ticker_a.astype(str).tolist())

print()
print("=" * 104)
print(f"{n_pass}/{n_pass + n_fail} assertions PASS")
print("=" * 104)
sys.exit(1 if n_fail else 0)
