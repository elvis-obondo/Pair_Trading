"""Sweep gates, concurrency and position sizing; print the tables.

Run order matters and is fixed here on purpose:

  A  how big the stop actually is, pair by pair. This is the fact that makes
     the rest of the report necessary -- under a fixed notional the dollar
     risk of a trade is set by which pair showed up, not by the signal.
  B  sizing rules at a fixed concurrency, so sizing is compared with
     everything else held still.
  C  concurrency under the old and new sizing rules, so the two effects are
     not confounded.
  D  how many entry gates to require, which is only answerable once sizing is
     no longer the dominant term.

Everything is out of sample: the exit rule is chosen on the train split and
scored on the test split, and the stress threshold is a train quantile.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd

from risk_sim import (load, outcome, prep, pick_config, simulate, GATES,
                      START_EQUITY, LEVERAGE_CAP, MEASURED_COST, STOP_SLIP,
                      CAPITAL_PER_TRADE)

HAVE_GATES = os.path.exists(GATES)
d = load(require_gates=False)
dates = np.sort(d.date.unique())
split = dates[int(len(dates) * 0.6)]
te_days = (pd.Timestamp(dates[-1]) - pd.Timestamp(split)).days

print("test window %s -> %s (%d days) | cost %.4f%% | stop slippage %.2fx | "
      "leverage cap %.0fx | start equity $%.0f"
      % (pd.Timestamp(split).date(), pd.Timestamp(dates[-1]).date(), te_days,
         MEASURED_COST * 100, STOP_SLIP, LEVERAGE_CAP, START_EQUITY))
print("entry gates table: %s\n" % ("loaded" if HAVE_GATES else "NOT BUILT -- section D skipped"))

BASE = lambda x: x[x.absz >= 3.0]
tr = BASE(d[d.date < split])
F, S, H = pick_config(tr)
te = prep(d, split, BASE, F, S, H)
print("exit rule chosen on TRAIN: take-profit %.1f, stop %.2f sigma, %dh cap" % (F, S, H))
print("test trades %d | per-trade net %+.3f%% of notional | win rate %.1f%%\n"
      % (len(te), te.net_pct.mean(), te.win.mean() * 100))

# ---------------------------------------------------------------- A
print("=" * 100)
print("A. HOW BIG IS THE STOP? (planned loss as %% of notional, per candidate)")
print("=" * 100)
q = np.percentile(te.stop_pct, [5, 25, 50, 75, 95, 99])
print("  p5 %.2f   p25 %.2f   median %.2f   p75 %.2f   p95 %.2f   p99 %.2f   max %.1f"
      % (q[0], q[1], q[2], q[3], q[4], q[5], te.stop_pct.max()))
fixed_notional = CAPITAL_PER_TRADE * LEVERAGE_CAP
print("  under a FIXED $%.0f notional that is a dollar loss of:" % fixed_notional)
print("    median $%.0f   p95 $%.0f   p99 $%.0f   worst $%.0f   (equity is $%.0f)"
      % (q[2] / 100 * fixed_notional, q[4] / 100 * fixed_notional,
         q[5] / 100 * fixed_notional, te.stop_pct.max() / 100 * fixed_notional,
         START_EQUITY))
print("  ratio p99/median = %.1fx -- two trades that look identical, %.1fx the risk\n"
      % (q[5] / q[2], q[5] / q[2]))

# ---------------------------------------------------------------- B
print("=" * 100)
print("B. SIZING RULES, at 10 concurrent positions (signal held constant)")
print("=" * 100)
print("%-32s%8s%9s%9s%9s%9s%8s%8s%9s"
      % ("rule", "med x", "P(prof)", "P(ruin)", "P(-50%)", "med DD", "p5 x", "p95 x", "med lev"))
print("-" * 100)
RULES = [
    ("fixed $30 x 20x  (current)",  dict(sizing="fixed")),
    ("vol, $3 risk/trade",          dict(sizing="vol_fixed", risk_dollars=3.0)),
    ("vol, $6 risk/trade",          dict(sizing="vol_fixed", risk_dollars=6.0)),
    ("vol, $15 risk/trade",         dict(sizing="vol_fixed", risk_dollars=15.0)),
    ("vol, 1% of equity/trade",     dict(sizing="vol_frac", risk_frac=0.01)),
    ("vol, 2% of equity/trade",     dict(sizing="vol_frac", risk_frac=0.02)),
    ("vol, 3% of equity/trade",     dict(sizing="vol_frac", risk_frac=0.03)),
    ("vol, 5% of equity/trade",     dict(sizing="vol_frac", risk_frac=0.05)),
]
for name, kw in RULES:
    f, dd, ruin, lev = simulate(te, 10, n_sims=400, **kw)
    print("%-32s%8.2f%8.0f%%%8.0f%%%8.0f%%%8.0f%%%8.2f%8.2f%9.1fx"
          % (name, np.median(f), np.mean(f > 1) * 100, ruin * 100,
             np.mean(f < 0.5) * 100, np.median(dd) * 100,
             np.percentile(f, 5), np.percentile(f, 95), lev))

# ---------------------------------------------------------------- C
print()
print("=" * 100)
print("C. HOW MANY POSITIONS AT ONCE")
print("=" * 100)
print("%16s | %-30s | %-32s" % ("", "FIXED $600 notional", "VOL-SIZED, 2% equity risk"))
print("%16s | %9s%9s%9s | %9s%9s%9s%9s"
      % ("max concurrent", "med x", "P(ruin)", "P(prof)",
         "med x", "P(ruin)", "P(prof)", "med lev"))
print("-" * 100)
for mc in [1, 2, 3, 5, 8, 10, 15, 20]:
    f1, _, r1, _ = simulate(te, mc, sizing="fixed", n_sims=400)
    f2, _, r2, l2 = simulate(te, mc, sizing="vol_frac", risk_frac=0.02, n_sims=400)
    print("%16d | %9.2f%8.0f%%%8.0f%% | %9.2f%8.0f%%%8.0f%%%8.1fx"
          % (mc, np.median(f1), r1 * 100, np.mean(f1 > 1) * 100,
             np.median(f2), r2 * 100, np.mean(f2 > 1) * 100, l2))

# ---------------------------------------------------------------- D
if HAVE_GATES:
    print()
    print("=" * 100)
    print("D. HOW MANY ENTRY GATES TO REQUIRE (vol-sized 2%, 5 positions)")
    print("=" * 100)
    print("   gates counted: cointegration, OU fit, theta significance, "
          "vol regime, reversion prob")
    print("   (minimum deviation is the entry threshold, swept across columns)\n")
    print("%6s%8s%10s%11s%8s%9s%9s%9s"
          % ("entry", "gates", "n test", "per-trade", "win%", "med x", "P(ruin)", "P(prof)"))
    print("-" * 100)
    for thr in [1.0, 2.0, 3.0]:
        for k in range(6):
            mk = (lambda t, kk: (lambda x: x[(x.absz >= t) & (x.n_gates >= kk)]))(thr, k)
            tr_k = mk(d[d.date < split])
            if len(tr_k) < 300:
                print("%6.1f%8d%10s" % (thr, k, "too few train rows"))
                continue
            Fk, Sk, Hk = pick_config(tr_k)
            te_k = prep(d, split, mk, Fk, Sk, Hk, min_rows=60)
            if te_k is None:
                print("%6.1f%8d%10s" % (thr, k, "too few test rows"))
                continue
            f, _, ruin, _ = simulate(te_k, 5, sizing="vol_frac",
                                     risk_frac=0.02, n_sims=300)
            print("%6.1f%8d%10d%+11.3f%8.1f%9.2f%8.0f%%%8.0f%%"
                  % (thr, k, len(te_k), te_k.net_pct.mean(),
                     te_k.win.mean() * 100, np.median(f), ruin * 100,
                     np.mean(f > 1) * 100))
        print()
