"""Run the SETTLED SPEC walk-forward, end to end, and report what the account does.

param_walkforward.py answered a narrower question -- can the parameters be
learned from history -- by sweeping a grid and measuring the average candidate
trade. It deliberately did not apply the rest of the configuration, so its
+0.489% is "the typical 3-sigma opportunity", not "what the strategy earns".
Three things it left out are the three most likely to matter:

  ranking   nine slots take nine of ~300 daily candidates. Choosing them at
            random is not the strategy; the spec ranks by mean-reversion speed.
  sizing    every position risking the same DOLLARS, not carrying the same
            notional. This is the change that took ruin from 10% to 0%.
  limits    ten concurrent positions, with total margin bounded by equity.

This applies all of it, fold by fold, on the two-year panel, and reports the
account outcome rather than a per-trade average -- because under risk-based
sizing the per-trade percent is actively misleading: position size is set
inversely to the stop distance, so a large percentage loss is taken on a
correspondingly small position.

Each fold is a fresh account. No parameter is fitted here -- the spec is fixed
in SPEC below, so every fold is genuinely out of sample.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd

import risk_sim as rs

SPEC = dict(entry=3.0, tp=1.0, stop=0.5, hor=72, slots=10, risk_frac=0.02)
FOLD_DAYS = 60
THETA_PATH = "research/candidate_theta.parquet"


def main():
    d = rs.load(require_gates=False)
    d = d[d.absz >= SPEC["entry"]].copy()

    # load() creates placeholder gate columns (theta among them) when the gate
    # table is absent, so the merge below would silently produce theta_x/theta_y
    # and the ranking would read neither.
    d = d.drop(columns=[c for c in ("theta", "sigma_stationary", "dev_sigma",
                                    "theta_p", "regime", "rev_prob")
                        if c in d.columns])
    th = pd.read_parquet(THETA_PATH)
    th["date"] = pd.to_datetime(th["date"])
    d = d.merge(th, on=["ticker_a", "ticker_b", "date"], how="left")
    print(f"{len(d):,} candidates at >={SPEC['entry']} sigma | "
          f"theta present on {d.theta.notna().mean()*100:.1f}%")

    net, xb, win, sp = rs.outcome(d, SPEC["tp"], SPEC["stop"], SPEC["hor"])
    d["net_pct"], d["exit_bar"], d["win"], d["stop_pct"] = net, xb, win, sp

    days = np.sort(d.date.unique())
    start, end = pd.Timestamp(days[0]), pd.Timestamp(days[-1])
    cuts = []
    t = start
    while t + pd.Timedelta(days=FOLD_DAYS) <= end:
        cuts.append(t)
        t += pd.Timedelta(days=FOLD_DAYS)

    print(f"\nspec: entry {SPEC['entry']} sigma, take-profit {SPEC['tp']}, "
          f"stop {SPEC['stop']}, {SPEC['hor']}h, {SPEC['slots']} slots, "
          f"risk {SPEC['risk_frac']*100:.0f}% of equity per trade")
    print(f"{len(cuts)} independent {FOLD_DAYS}-day folds, fresh $300 account each\n")

    print("=" * 104)
    print("%-14s%8s%9s%9s%10s%9s%10s%9s%9s"
          % ("fold from", "n cand", "RANDOM", "P(ruin)", "BY THETA", "P(ruin)",
             "P(prof)", "p5 x", "p95 x"))
    print("-" * 104)

    rnd_all, th_all, rr, tr_ = [], [], [], []
    for cut in cuts:
        f = d[(d.date >= cut) & (d.date < cut + pd.Timedelta(days=FOLD_DAYS))]
        if f.date.nunique() < 20 or len(f) < 300:
            continue
        a, _, ruin_a, _ = rs.simulate(f, SPEC["slots"], sizing="vol_frac",
                                      risk_frac=SPEC["risk_frac"], n_sims=300)
        b, _, ruin_b, _ = rs.simulate(f, SPEC["slots"], sizing="vol_frac",
                                      risk_frac=SPEC["risk_frac"], n_sims=300,
                                      rank_by=("theta", False, 3.0))
        rnd_all.append(np.median(a)); th_all.append(np.median(b))
        rr.append(ruin_a); tr_.append(ruin_b)
        print("%-14s%8d%9.2f%8.0f%%%10.2f%8.0f%%%9.0f%%%9.2f%9.2f"
              % (str(cut.date()), len(f), np.median(a), ruin_a * 100,
                 np.median(b), ruin_b * 100, np.mean(b > 1) * 100,
                 np.percentile(b, 5), np.percentile(b, 95)))

    print("-" * 104)
    r, t2 = np.array(rnd_all), np.array(th_all)
    print("%-14s%8s%9.2f%8.0f%%%10.2f%8.0f%%"
          % ("MEDIAN FOLD", "", np.median(r), np.mean(rr) * 100,
             np.median(t2), np.mean(tr_) * 100))
    print(f"\n  folds where ranking by theta beat random: {np.mean(t2 > r)*100:.0f}% "
          f"({int(np.sum(t2 > r))} of {len(t2)})")
    print(f"  folds ending profitable, ranked: {np.mean(t2 > 1)*100:.0f}%")
    print(f"  compounded across all folds, ranked: {np.prod(t2):.2f}x "
          f"| random: {np.prod(r):.2f}x")


if __name__ == "__main__":
    main()
