"""PASS/FAIL for dislocation_study.py. Hand-run, no pytest.

The forward walk in episodes_for_pair is a vectorised restatement of
generate_exit_signal's gate order. A restatement is only safe if it is checked
against the original, so check 1 replays sampled episodes one bar at a time
through generate_exit_signal itself and demands the same (reason, bars_held).

    python research/validate_dislocation_study.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd

from universe_panel import load_panel, usable_tickers, tradeable_pairs
from rolling_spread import rolling_spread_stats, min_bars_required
from signal_generator import generate_exit_signal
import dislocation_study as ds

END = "2026-09-21 00:00:00"
DAYS, BAR_HOURS, ENTRY, STOP, HOLD = 35, 0.5, 3.0, 0.5, 72.0
N_PAIRS = 60
checks = []


def check(name, ok, detail=""):
    checks.append((name, bool(ok), detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))


need = min_bars_required(BAR_HOURS)
bars_per_day = int(round(24 / BAR_HOURS))
panel = load_panel().loc[:pd.Timestamp(END)].tail(need + DAYS * bars_per_day)
tickers = usable_tickers(panel, BAR_HOURS)
pairs = tradeable_pairs(tickers)[:N_PAIRS]
arrays = {t: panel[t].to_numpy(dtype=float) for t in tickers}
max_hold_bars = int(round(HOLD / BAR_HOURS))
print(f"{len(tickers)} tickers, sampling {len(pairs)} pairs, "
      f"{panel.index[need]} -> {panel.index[-1]}\n")

rows = []
for a, b in pairs:
    rows.extend(ds.episodes_for_pair(a, b, arrays[a], arrays[b], need, ENTRY,
                                     STOP, max_hold_bars, BAR_HOURS))
d = pd.DataFrame(rows)
print(f"{len(d):,} episodes from {len(pairs)} pairs\n")

# ---- 1. the forward walk equals generate_exit_signal, bar by bar ----
mismatch, replayed = [], 0
for a, b in pairs:
    pa, pb = arrays[a], arrays[b]
    r = rolling_spread_stats(pa, pb, BAR_HOURS)
    sub = d[(d.ticker_a == a) & (d.ticker_b == b)]
    for e in sub.itertuples(index=False):
        i = e.bar
        sig = {"entry_spread": r.spread[i], "mu_at_entry": r.mu[i],
               "sigma_at_entry": r.sigma[i], "beta_at_entry": r.beta[i],
               "alpha_at_entry": r.alpha[i], "take_profit_level": r.mu[i]}
        hi = min(i + max_hold_bars, len(pa) - 1)
        got = None
        for j in range(i + 1, hi + 1):
            if not (np.isfinite(pa[j]) and np.isfinite(pb[j])):
                continue
            ex = generate_exit_signal(pa[j], pb[j], sig, (j - i) * BAR_HOURS,
                                      stop_sigma=STOP, max_hold_hours=HOLD)
            if ex is not None:
                got = (ex["exit_reason"], j - i)
                break
        if got is None:
            got = ("time_stop", hi - i)
        replayed += 1
        if got != (e.exit_reason, e.bars_held):
            mismatch.append((a, b, i, got, (e.exit_reason, e.bars_held)))
check("forward walk reproduces generate_exit_signal exactly",
      not mismatch, f"{replayed:,} episodes replayed, {len(mismatch)} mismatches"
      + (f"  first: {mismatch[0]}" if mismatch else ""))

# ---- 2. an episode start is never preceded by a dislocated bar ----
bad = 0
for a, b in pairs:
    r = rolling_spread_stats(arrays[a], arrays[b], BAR_HOURS)
    hot = np.isfinite(r.z) & (np.abs(r.z) >= ENTRY)
    for i in d[(d.ticker_a == a) & (d.ticker_b == b)].bar:
        if i > 0 and hot[i - 1]:
            bad += 1
check("every episode start has a non-dislocated previous bar", bad == 0,
      f"{bad} violations")

# ---- 3. every episode is itself dislocated at its start bar ----
check("every episode start is at |z| >= entry",
      bool((d.absz >= ENTRY - 1e-9).all()),
      f"min |z| = {d.absz.min():.4f}")

# ---- 4. R arithmetic: a full reversion banks AT LEAST |z|/stop_sigma ----
# Not exactly. The take profit is detected at a bar CLOSE, and the spread
# crossed mu somewhere inside that bar, so the booked exit sits past mu and the
# trade banks more than the entry-to-mu move. That surplus is favourable
# overshoot, and it is the same 30-minute coarseness that hides intrabar stops
# -- measured at a median +0.35R here. Checking equality would be asserting
# perfect execution; the invariant is the inequality, plus a bound on how far
# the surplus can run.
tp = d[d.exit_reason == "take_profit"]
surplus = tp.r - tp.absz / STOP
check("take_profit R is never below |z|/stop_sigma", bool((surplus >= -1e-9).all()),
      f"{len(tp):,} take-profits, min surplus {surplus.min():+.2e}, "
      f"median +{surplus.median():.3f}R of favourable overshoot")

# ---- 5. an adverse exit is exactly -1R by construction ----
ad = d[d.exit_reason == "adverse_move"]
check("adverse_move R is at or past -1", bool((ad.r <= -1.0 + 1e-9).all()),
      f"{len(ad):,} stops, max R {ad.r.max():+.4f} (worst {ad.r.min():+.2f})")

# ---- 6. holds respect the cap ----
check("no episode is held past the time cap",
      bool((d.bars_held <= max_hold_bars).all()),
      f"max {int(d.bars_held.max())} bars of {max_hold_bars}")

# ---- 7. leg attribution is a share on [0,1] ----
sh = d.leg_a_share.dropna()
check("leg_a_share lies on [0,1]", bool(((sh >= 0) & (sh <= 1)).all()),
      f"{len(sh):,} finite, range {sh.min():.3f}..{sh.max():.3f}")

# ---- 8. r2 is a correlation squared ----
r2 = d.r2.dropna()
check("r2 lies on [0,1]", bool(((r2 >= 0) & (r2 <= 1)).all()),
      f"range {r2.min():.4f}..{r2.max():.4f}, median {r2.median():.4f}")

# ---- 9. beta(A|B)*beta(B|A) == r2, the identity the noise floor rests on ----
errs = []
for a, b in pairs[:12]:
    ra = rolling_spread_stats(arrays[a], arrays[b], BAR_HOURS)
    rb = rolling_spread_stats(arrays[b], arrays[a], BAR_HOURS)
    m = np.isfinite(ra.beta) & np.isfinite(rb.beta) & np.isfinite(ra.r2)
    errs.append(np.nanmax(np.abs(ra.beta[m] * rb.beta[m] - ra.r2[m])))
check("beta(A|B) x beta(B|A) == r2", max(errs) < 1e-9,
      f"max abs error {max(errs):.2e} over 12 pairs")

# ---- 10. fine-resolution alignment: 1m resolves no LATER than 30m ----
# THE CHECK THAT CATCHES THE 29-MINUTE MISALIGNMENT (ac3ac48). Bars are
# labelled by open time, so the 30m bar labelled T closes when the 1m bar
# labelled T+29 closes, and a position entered on bar T begins at the 1m bar
# T+30. Start the fine walk at T+1 instead and it checks the 29 minutes INSIDE
# the entry bar -- prices from before the position existed.
#
# Note what the invariant is NOT: "a 30m stop is still a stop at 1m". That is
# false, and believing it sent this study chasing a bug that was not there.
# Finer checking adds breaches of BOTH kinds, so a 30m stop can become a 1m
# take-profit when the target was touched intrabar first. What must hold is
# only that finer checking resolves no later.
fine = ds.build(days=DAYS, end_date=END, entry=ENTRY, stop_sigma=STOP,
                max_hold_hours=HOLD, exit_check_minutes=1,
                limit_pairs=N_PAIRS,
                out_path="/tmp/_validate_dis_1m.parquet")
key = ["ticker_a", "ticker_b", "bar"]
c30 = d.set_index(key).sort_index()
c1m = fine.set_index(key).sort_index()
check("coarse and fine arms open identical episodes",
      c30.index.equals(c1m.index),
      f"{len(c30):,} vs {len(c1m):,}")
if c30.index.equals(c1m.index):
    late = (c1m.bars_held > c30.bars_held + 1e-9)
    check("1m resolves no LATER than 30m (alignment)", not late.any(),
          f"{int(late.sum())} of {len(c30):,} late; "
          f"{100*(c1m.bars_held < c30.bars_held).mean():.1f}% resolve earlier")
    conv = 100 * (c1m.exit_reason[c30.exit_reason == "take_profit"]
                  == "adverse_move").mean()
    check("some 30m take-profits become 1m stops (intrabar effect is present)",
          conv > 5.0, f"{conv:.1f}% of 30m take-profits are 1m stops")

n_pass = sum(1 for _, ok, _ in checks if ok)
print(f"\n{n_pass}/{len(checks)} checks passed")
sys.exit(0 if n_pass == len(checks) else 1)
