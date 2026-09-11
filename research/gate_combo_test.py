"""Which COMBINATION of entry gates works at 3-sigma, under fixed sizing?

Counting gates ("at least k of 5") assumes they are interchangeable. They are
not: cointegration, OU fit quality, theta significance, volatility regime and
reversion probability measure different things, and a count cannot tell you
whether 2 gates worked because of WHICH two. This enumerates all 31 non-empty
subsets instead.

Fixed at 3-sigma entry because the count sweep already showed the gate effect
reverses with entry width -- gates help at 1 sigma and hurt at 3 -- so mixing
entry thresholds in here would confound the comparison again.

SIZING: fixed CAPITAL_PER_TRADE x LEVERAGE_CAP ($30 x 20 = $600), the live
rule, NOT the vol-sized rule. Under fixed sizing the per-trade percent is a
meaningful number again (every trade has the same notional), and ruin is back
on the table, so P(ruin) is reported next to every return.

DISLOCATION FILTER: the universe-wide count of >=3-sigma dislocations that day
is used here as a TRADE / DO-NOT-TRADE switch, not as a sizing input. Both
directions are tested -- sitting out the busy days and trading only the busy
days -- because an earlier run found the spike days carry both the worst losses
and the biggest winners, so it is not obvious which side is right. Thresholds
come from the TRAIN split only.

EXIT RULE IS FROZEN across every row, chosen once on the 3-sigma ungated train
set. Letting each subset pick its own take-profit/stop/horizon on its own
shrinking training sample is what made the earlier gate table incoherent: win
rates jumped between adjacent cells because the exit rule changed underneath,
not the filter.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import itertools
import numpy as np
import pandas as pd

import risk_sim as rs

ENTRY = 3.0
MAX_CONCURRENT = 10
N_SIMS = 300

GATES = [("COI", "g_coint",  "cointegration p<=0.10"),
         ("OU",  "g_oufit",  "OU fit, theta>0"),
         ("THE", "g_theta",  "theta significance p<=0.05"),
         ("REG", "g_regime", "volatility regime<=1.1"),
         ("PRB", "g_prob",   "reversion probability>=0.60")]


def mask_for(subset, dislo=None, thresholds=None):
    """Rows at >=ENTRY sigma passing every gate in `subset`, plus the day filter."""
    cols = [c for _, c, _ in subset]

    def f(x):
        m = x.absz >= ENTRY
        for c in cols:
            m &= x[c]
        if dislo == "calm":
            m &= x.n_wide <= thresholds["p75"]
        elif dislo == "very_calm":
            m &= x.n_wide <= thresholds["p50"]
        elif dislo == "busy":
            m &= x.n_wide >= thresholds["p75"]
        return x[m]
    return f


def main():
    d = rs.load()
    dates = np.sort(d.date.unique())
    split = dates[int(len(dates) * 0.6)]
    per_day = d[d.date < split].groupby("date")["n_wide"].first()
    th = {"p50": per_day.quantile(0.50), "p75": per_day.quantile(0.75)}

    # Exit rule frozen on the ungated 3-sigma train set.
    base_tr = d[(d.date < split) & (d.absz >= ENTRY)]
    F, S, H = rs.pick_config(base_tr)

    print("entry %.1f sigma | fixed $%.0f x %.0fx = $%.0f per position | %d concurrent | "
          "cost %.4f%% | slippage %.2fx"
          % (ENTRY, rs.CAPITAL_PER_TRADE, rs.LEVERAGE_CAP,
             rs.CAPITAL_PER_TRADE * rs.LEVERAGE_CAP, MAX_CONCURRENT,
             rs.MEASURED_COST * 100, rs.STOP_SLIP))
    print("exit rule frozen for every row: take-profit %.1f, stop %.2f sigma, %dh" % (F, S, H))
    print("dislocation thresholds from TRAIN: median %.0f/day, upper quartile %.0f/day\n"
          % (th["p50"], th["p75"]))
    for a, _, desc in GATES:
        print("  %-4s %s" % (a, desc))
    print()

    rng = np.random.default_rng(0)

    def evaluate(subset, dislo=None):
        te = rs.prep(d, split, mask_for(subset, dislo, th), F, S, H, min_rows=30)
        if te is None:
            return None
        n = te.net_pct.to_numpy()
        boot = np.array([rng.choice(n, len(n)).mean() for _ in range(300)])
        lo, hi = np.percentile(boot, [2.5, 97.5])
        f, dd, ruin, _ = rs.simulate(te, MAX_CONCURRENT, sizing="fixed", n_sims=N_SIMS)
        return dict(n=len(te), per=n.mean(), lo=lo, hi=hi,
                    win=te.win.mean() * 100, med=np.median(f),
                    ruin=ruin * 100, prof=np.mean(f > 1) * 100,
                    p5=np.percentile(f, 5), dd=np.median(dd) * 100)

    # ---------- every non-empty subset, all days ----------
    print("=" * 108)
    print("ALL 31 GATE COMBINATIONS, every day traded (no dislocation filter)")
    print("=" * 108)
    print("%-22s%5s%8s%9s%20s%7s%8s%8s%8s"
          % ("gates required", "k", "n test", "per-trade", "95% CI", "win%",
             "med x", "P(ruin)", "P(prof)"))
    print("-" * 108)

    results = []
    base = evaluate([])
    if base:
        print("%-22s%5d%8d%+9.3f   [%+6.3f,%+6.3f]%7.1f%8.2f%7.0f%%%7.0f%%"
              % ("(none)", 0, base["n"], base["per"], base["lo"], base["hi"],
                 base["win"], base["med"], base["ruin"], base["prof"]))
        print("-" * 108)

    for k in range(1, 6):
        for subset in itertools.combinations(GATES, k):
            r = evaluate(list(subset))
            label = "+".join(a for a, _, _ in subset)
            if r is None:
                print("%-22s%5d%8s" % (label, k, "too few"))
                continue
            r["label"], r["k"], r["subset"] = label, k, subset
            results.append(r)
            print("%-22s%5d%8d%+9.3f   [%+6.3f,%+6.3f]%7.1f%8.2f%7.0f%%%7.0f%%"
                  % (label, k, r["n"], r["per"], r["lo"], r["hi"],
                     r["win"], r["med"], r["ruin"], r["prof"]))
        print()

    # ---------- dislocation filter on the strongest combinations ----------
    ranked = sorted(results, key=lambda r: -r["med"])[:6]
    print("=" * 108)
    print("DISLOCATION FILTER: does sitting out (or only trading) busy days help?")
    print("=" * 108)
    print("%-22s%-12s%8s%9s%7s%8s%8s%8s"
          % ("gates", "days traded", "n test", "per-trade", "win%", "med x",
             "P(ruin)", "P(prof)"))
    print("-" * 108)
    for r in ranked:
        for dislo, name in [(None, "all"), ("calm", "calm only"),
                            ("very_calm", "quietest half"), ("busy", "busy only")]:
            rr = evaluate(list(r["subset"]), dislo)
            if rr is None:
                print("%-22s%-12s%8s" % (r["label"], name, "too few"))
                continue
            print("%-22s%-12s%8d%+9.3f%7.1f%8.2f%7.0f%%%7.0f%%"
                  % (r["label"], name, rr["n"], rr["per"], rr["win"],
                     rr["med"], rr["ruin"], rr["prof"]))
        print()


if __name__ == "__main__":
    main()
