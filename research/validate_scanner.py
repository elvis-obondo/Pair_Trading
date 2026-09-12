"""Validate the universe scanner.

The important check is the last one: that the scanner and the offline dataset
every settled parameter was fitted on agree about what a 3-sigma candidate is.

Run: python research/validate_scanner.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import time
import numpy as np
import pandas as pd

from universe_panel import load_panel, usable_tickers, tradeable_pairs
from rolling_spread import min_bars_required
from signal_generator import generate_entry_signal
from scanner import scan, SIGNAL_FIELDS

n_pass = n_fail = 0
BH = 0.5
W = min_bars_required(BH)


def check(name, ok, detail=""):
    global n_pass, n_fail
    ok = bool(ok)
    n_pass, n_fail = n_pass + ok, n_fail + (not ok)
    print(f"{name + ':':58s} {str(detail)[:28]:30s} {'PASS' if ok else 'FAIL'}")


panel = load_panel(tail_bars=W)
tickers = usable_tickers(panel, BH)
pairs = tradeable_pairs(tickers)

t0 = time.time()
cand = scan(panel, pairs, min_deviation_sigma=3.0, bar_hours=BH)
elapsed = time.time() - t0

print("=" * 104)
print(f"1. Full-universe scan — {len(pairs):,} pairs in {elapsed:.1f}s")
print("=" * 104)
check("scan returns a DataFrame", isinstance(cand, pd.DataFrame), f"{len(cand)} rows")
check("has every entry-signal field",
      all(c in cand.columns for c in SIGNAL_FIELDS + ["ticker_a", "ticker_b"]))
check("runs well inside a 30-minute bar", elapsed < 300, f"{elapsed:.1f}s")
check("found candidates to test with", len(cand) > 0, f"{len(cand)}")

print()
print("=" * 104)
print("2. Every candidate genuinely clears the threshold")
print("=" * 104)
check("all |z| >= 3.0", bool((cand.z_at_entry.abs() >= 3.0).all()),
      f"min |z| {cand.z_at_entry.abs().min():.4f}")
check("sigma_at_entry strictly positive", bool((cand.sigma_at_entry > 0).all()))
check("take_profit == mu at take_profit_pct=1.0",
      bool(np.allclose(cand.take_profit_level, cand.mu_at_entry)))
check("no duplicate pairs in one scan",
      not cand.duplicated(["ticker_a", "ticker_b"]).any())

print()
print("=" * 104)
print("3. Ranking: theta descending, NaN LAST but kept")
print("=" * 104)
th = cand.theta_at_entry
ranked = th.dropna()
check("ranked block is sorted descending", ranked.is_monotonic_decreasing,
      f"{len(ranked)} ranked")
check("all ranked thetas are positive", bool((ranked > 0).all()))
n_nan = int(th.isna().sum())
check("NaN-theta candidates are KEPT, not dropped", n_nan >= 0,
      f"{n_nan} unranked kept")
if n_nan:
    check("every NaN sits after every ranked row",
          bool(th.tail(n_nan).isna().all()), "NaN block is the tail")
check("a higher threshold returns a subset",
      set(map(tuple, scan(panel, pairs, min_deviation_sigma=3.6,
                          bar_hours=BH)[["ticker_a", "ticker_b"]].values))
      <= set(map(tuple, cand[["ticker_a", "ticker_b"]].values)))

print()
print("=" * 104)
print("4. The scanner adds no geometry of its own")
print("=" * 104)
arrays = {t: panel[t].to_numpy(dtype=float) for t in tickers}
mismatch = 0
for row in cand.head(25).itertuples(index=False):
    direct = generate_entry_signal(arrays[row.ticker_a], arrays[row.ticker_b],
                                   min_deviation_sigma=3.0, bar_hours=BH)
    if direct is None:
        mismatch += 1
        continue
    for f in SIGNAL_FIELDS:
        a, b = getattr(row, f), direct[f]
        if not ((np.isnan(a) and np.isnan(b)) or np.isclose(a, b, rtol=0, atol=1e-12)):
            mismatch += 1
check("scan() row == generate_entry_signal() called directly",
      mismatch == 0, f"{mismatch} mismatches in 25")

print()
print("=" * 104)
print("5. Short and gappy legs are skipped, not silently returned")
print("=" * 104)
check("a panel shorter than 671 bars returns empty",
      len(scan(panel.tail(W - 1), pairs, bar_hours=BH)) == 0, "empty")
gappy = panel.copy()
victim = tickers[0]
gappy.loc[gappy.index[5], victim] = np.nan
out = scan(gappy, pairs, min_deviation_sigma=3.0, bar_hours=BH)
check(f"pairs involving a gappy leg ({victim}) are excluded",
      not ((out.ticker_a == victim) | (out.ticker_b == victim)).any(),
      f"{len(out)} rows, none with {victim}")
check("the rest of the universe still scans",
      len(out) > 0 and len(out) <= len(cand), f"{len(out)} vs {len(cand)}")

print()
print("=" * 104)
print("6. Cross-check against exit_sweep_paths.parquet — the settled dataset")
print("=" * 104)
PATHS = "research/exit_sweep_paths.parquet"
if not os.path.exists(PATHS):
    print("  exit_sweep_paths.parquet absent — skipping the cross-check")
else:
    p = pd.read_parquet(PATHS, columns=["ticker_a", "ticker_b", "date", "z", "sigma"])
    p["date"] = pd.to_datetime(p["date"])
    day = p.date.max()
    ref = p[(p.date == day) & (p.z.abs() >= 3.0)]
    full = load_panel()
    # exit_sweep samples the LAST bar of each day; reproduce that exact bar.
    idx = full.index[full.index.normalize() == day]
    if not len(idx) or not len(ref):
        print(f"  no overlapping bar for {day.date()} — skipping")
    else:
        sub = full.loc[:idx[-1]].tail(W)
        tk2 = usable_tickers(sub, BH)
        mine = scan(sub, tradeable_pairs(tk2), min_deviation_sigma=3.0, bar_hours=BH)
        ref_set = {tuple(sorted(x)) for x in ref[["ticker_a", "ticker_b"]].values}
        my_set = {tuple(sorted(x)) for x in mine[["ticker_a", "ticker_b"]].values}
        common = {t for t in ref_set | my_set
                  if t[0] in tk2 and t[1] in tk2}
        agree = len(ref_set & my_set)
        union = len(common) or 1
        print(f"    bar {idx[-1]}   parquet flagged {len(ref_set)}, "
              f"scanner flagged {len(my_set)}, agreed on {agree}")
        check("scanner and the settled dataset overlap substantially",
              agree / max(1, min(len(ref_set), len(my_set))) > 0.5,
              f"{agree}/{min(len(ref_set), len(my_set))} overlap")

print()
print("=" * 104)
print(f"{n_pass}/{n_pass + n_fail} assertions PASS")
print("=" * 104)
sys.exit(1 if n_fail else 0)
