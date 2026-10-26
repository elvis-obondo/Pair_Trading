"""Do the parameters hold up across regimes? Walk-forward, not one split.

param_stability.py answered this on a single 60/40 split of an 89-day window
and found a train-test rank correlation of -0.03 on the stop dimension: train's
best stop came 4th on test. That is one number from one split of one quiet
quarter, and it could mean either "the parameter is unlearnable" or "43 days is
too few to learn anything". Those have opposite implications and the data could
not tell them apart.

With 714 days there is enough calendar to ask properly. This walks a rolling
origin: fit on everything before a cut, score the next FOLD_DAYS, step forward,
repeat. For each fold and each parameter dimension it records the train ranking
and the test ranking, then reports how often they agree ACROSS folds.

The statistic that matters is not any single fold's correlation -- that is what
was already measured and found to be noise -- but the distribution over folds:

  - a dimension whose train and test rankings agree in most folds is learnable,
    and its best value can be set from data
  - a dimension whose correlation scatters around zero is not, and picking its
    "best" value is hindsight no matter how large the gap looks in one fold

Also reported per fold: the test score of the value TRAIN would have picked,
against the best available in hindsight. That gap is the real cost of not
knowing, and it is the number to quote rather than the hindsight optimum.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd
from scipy import stats

import risk_sim as rs

ENTRY_GRID = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5]
TP_GRID = [0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0]
STOP_GRID = [0.5, 0.75, 1.0, 1.5, 2.0, 3.0]
HOR_GRID = [24, 48, 72]

FOLD_DAYS = 60
MIN_TRAIN_DAYS = 120


def score_grid(sub):
    """Mean net % of notional for every grid cell on one slice of rows."""
    out = []
    for e in ENTRY_GRID:
        s = sub[sub.absz >= e]
        if len(s) < 200:
            continue
        for tp in TP_GRID:
            for stop in STOP_GRID:
                for h in HOR_GRID:
                    n, _, _, _ = rs.outcome(s, tp, stop, h)
                    out.append((e, tp, stop, h, n.mean(), len(s)))
    return pd.DataFrame(out, columns=["entry", "tp", "stop", "hor", "mean", "n"])


def main():
    d = rs.load(require_gates=False)
    d = d[["date", "absz", "sigma"]
          + [c for c in d.columns if c.startswith(("tp_bar_", "stop_bar_", "prog_at_"))]]
    days = np.sort(d.date.unique())
    start, end = pd.Timestamp(days[0]), pd.Timestamp(days[-1])
    print(f"{len(d):,} rows | {start.date()} -> {end.date()} | {len(days)} days")

    cuts = []
    t = start + pd.Timedelta(days=MIN_TRAIN_DAYS)
    while t + pd.Timedelta(days=FOLD_DAYS) <= end:
        cuts.append(t)
        t += pd.Timedelta(days=FOLD_DAYS)
    print(f"{len(cuts)} walk-forward folds of {FOLD_DAYS} days "
          f"(expanding train, min {MIN_TRAIN_DAYS} days)\n")

    dims = ["entry", "tp", "stop", "hor"]
    rhos = {k: [] for k in dims}
    picks = {k: [] for k in dims}
    fold_rows = []

    for i, cut in enumerate(cuts, 1):
        tr = d[d.date < cut]
        te = d[(d.date >= cut) & (d.date < cut + pd.Timedelta(days=FOLD_DAYS))]
        if len(tr) < 5000 or len(te) < 2000:
            continue
        gtr, gte = score_grid(tr), score_grid(te)
        if gtr.empty or gte.empty:
            continue
        m = gtr.merge(gte, on=["entry", "tp", "stop", "hor"],
                      suffixes=("_tr", "_te"))
        if len(m) < 20:
            continue
        row = {"fold": i, "test_from": cut.date(), "n_test": int(te.shape[0])}
        for k in dims:
            agg = m.groupby(k)[["mean_tr", "mean_te"]].mean()
            if len(agg) < 3:
                continue
            rho = stats.spearmanr(agg.mean_tr, agg.mean_te).statistic
            rhos[k].append(rho)
            chosen = agg.mean_tr.idxmax()                 # what train would pick
            best = agg.mean_te.idxmax()                   # hindsight best
            picks[k].append((chosen, best, agg.mean_te[chosen], agg.mean_te.max()))
            row[f"rho_{k}"] = rho
            row[f"pick_{k}"] = chosen
        fold_rows.append(row)
        print(f"  fold {i:>2} test from {cut.date()}  "
              + "  ".join(f"{k}: rho {row.get('rho_'+k, float('nan')):+.2f} "
                          f"pick {row.get('pick_'+k, '?')}" for k in dims), flush=True)

    print("\n" + "=" * 96)
    print(f"AGREEMENT ACROSS {len(fold_rows)} FOLDS -- does train predict test?")
    print("=" * 96)
    print(f"{'dimension':12}{'mean rho':>10}{'median':>9}{'folds rho>0':>13}"
          f"{'train pick = hindsight':>24}{'verdict':>14}")
    print("-" * 96)
    for k in dims:
        r = np.array(rhos[k], dtype=float)
        r = r[np.isfinite(r)]
        if not len(r):
            continue
        same = np.mean([c == b for c, b, _, _ in picks[k]]) * 100
        pos = np.mean(r > 0) * 100
        verdict = ("LEARNABLE" if np.mean(r) > 0.5 and pos >= 70
                   else "noise" if abs(np.mean(r)) < 0.25
                   else "partial")
        print(f"{k:12}{np.mean(r):>+10.2f}{np.median(r):>+9.2f}{pos:>12.0f}%"
              f"{same:>23.0f}%{verdict:>14}")

    print("\n" + "=" * 96)
    print("COST OF NOT KNOWING: test score of train's pick vs hindsight best")
    print("=" * 96)
    print(f"{'dimension':12}{'train pick':>26}{'its test score':>16}"
          f"{'hindsight best':>16}{'gap':>9}")
    print("-" * 96)
    for k in dims:
        if not picks[k]:
            continue
        got = np.mean([g for _, _, g, _ in picks[k]])
        bst = np.mean([b for _, _, _, b in picks[k]])
        from collections import Counter
        c = Counter(str(x) for x, _, _, _ in picks[k]).most_common(2)
        modal = ", ".join(f"{v} ({n}/{len(picks[k])})" for v, n in c)
        print(f"{k:12}{modal:>26}{got:>+16.3f}{bst:>+16.3f}{bst-got:>+9.3f}")

    pd.DataFrame(fold_rows).to_csv("research/param_walkforward_folds.csv", index=False)
    print("\nper-fold detail -> research/param_walkforward_folds.csv")


if __name__ == "__main__":
    main()
