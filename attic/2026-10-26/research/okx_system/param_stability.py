"""Which entry/exit parameters generalise, and which are noise?

Selecting the six stop levels on train and scoring on test gave a rank
correlation of -0.03: train's best stop came 4th on test. That result is about
ONE dimension at ONE entry threshold. Before settling any parameter it has to
be asked of each dimension separately -- entry width, take-profit fraction,
stop distance, holding horizon -- because they are not equally learnable. A
dimension whose train and test rankings agree can be set from this data. One
whose rankings are uncorrelated cannot, and picking its "best" value is
hindsight regardless of how large the gap looks.

Method: score the full grid on both splits, then for each dimension average
over the others and compare the two rankings. Averaging rather than taking the
best is deliberate -- the max of a noisy surface is itself a selection, which
is the thing under test.

Metric is mean net % of notional per trade under fixed sizing, where every
position has the same notional so the average is a meaningful number. Trade
count is reported too: a per-trade edge on 400 trades and on 40,000 trades are
not the same asset.
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


def build():
    d = rs.load()
    dates = np.sort(d.date.unique())
    split = dates[int(len(dates) * 0.6)]
    rows = []
    for e in ENTRY_GRID:
        tr = d[(d.date < split) & (d.absz >= e)]
        te = d[(d.date >= split) & (d.absz >= e)]
        for tp in TP_GRID:
            for stop in STOP_GRID:
                for h in HOR_GRID:
                    ntr, _, _, _ = rs.outcome(tr, tp, stop, h)
                    nte, _, wte, _ = rs.outcome(te, tp, stop, h)
                    rows.append(dict(entry=e, tp=tp, stop=stop, hor=h,
                                     train=ntr.mean(), test=nte.mean(),
                                     n_test=len(te), win=wte.mean() * 100))
        print(f"  entry {e} done", flush=True)
    return pd.DataFrame(rows)


def marginal(g, dim):
    m = g.groupby(dim)[["train", "test"]].mean()
    rho = stats.spearmanr(m["train"], m["test"]).statistic
    return m, rho


def main():
    g = build()
    g.to_parquet("research/param_grid.parquet", index=False)
    print(f"\n{len(g)} grid cells scored on both splits\n")

    print("=" * 88)
    print("WHICH DIMENSIONS GENERALISE?  (averaged over the other three)")
    print("=" * 88)
    verdicts = {}
    for dim, label in [("entry", "entry threshold"), ("tp", "take-profit fraction"),
                       ("stop", "stop distance"), ("hor", "holding horizon")]:
        m, rho = marginal(g, dim)
        verdicts[dim] = rho
        agree = "STABLE" if rho >= 0.7 else "unstable" if rho <= 0.3 else "partial"
        print(f"\n{label}   rank correlation train vs test = {rho:+.2f}   -> {agree}")
        print(f"  {'value':>8}{'train':>10}{'test':>10}")
        for v, r in m.iterrows():
            star = "  <- best on test" if r["test"] == m["test"].max() else ""
            print(f"  {v:>8}{r['train']:>+10.3f}{r['test']:>+10.3f}{star}")

    print("\n" + "=" * 88)
    print("TAKE-PROFIT: is full reversion (1.0) actually right?")
    print("=" * 88)
    sub = g[g.entry == 3.0].groupby("tp")[["train", "test"]].mean()
    print(f"  {'tp frac':>8}{'train':>10}{'test':>10}   (entry 3.0 only)")
    for v, r in sub.iterrows():
        print(f"  {v:>8}{r['train']:>+10.3f}{r['test']:>+10.3f}")

    print("\n" + "=" * 88)
    print("ENTRY THRESHOLD: edge per trade vs how many trades you get")
    print("=" * 88)
    e = g.groupby("entry").agg(train=("train", "mean"), test=("test", "mean"),
                               n_test=("n_test", "first")).reset_index()
    print(f"  {'entry':>7}{'train':>10}{'test':>10}{'n trades':>11}{'test x n':>12}")
    for _, r in e.iterrows():
        print(f"  {r['entry']:>7.1f}{r['train']:>+10.3f}{r['test']:>+10.3f}"
              f"{int(r['n_test']):>11,}{r['test']*r['n_test']/100:>+12.1f}")
    print("\n  last column = total % of notional earned across all trades,")
    print("  i.e. edge per trade multiplied by how often it is available.")


if __name__ == "__main__":
    main()
