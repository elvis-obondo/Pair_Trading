"""Can we pick the good candidates instead of taking them at random?

At 3 sigma the pool is ~322 candidates a day and ten slots take about nine of
them, so 97% of the pool is declined already. The portfolio simulation declines
them AT RANDOM, which means every result so far is what an uninformed chooser
gets. If any observable feature ranks candidates by realised outcome, the same
number of trades earns more -- and that is worth more than any parameter tweak,
because it costs no extra capital and no extra exposure.

Method: for each day, sort that day's candidates by a feature, take the top N,
and compare their mean realised net to a random N from the same day. Same day,
same count, so market conditions and trade volume are held fixed and the only
difference is the choice rule. Both sort directions are tried, since for most
of these features there is no prior about which end is better.

Checked on train and on test separately. A feature that ranks well on one split
and not the other is noise, and with 29 test days that is the likely outcome
for most of them -- the point of the table is to find out which, not to pick
the winner off the test column.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd

import risk_sim as rs

ENTRY, TP, STOP, HOR = 3.0, 1.0, 0.5, 72
SLOTS = 9                     # ~10 concurrent positions at a 28h average hold

FEATURES = [
    ("absz",             "dislocation size |z|"),
    ("sigma",            "spread volatility"),
    ("theta",            "mean-reversion speed"),
    ("rev_prob",         "reversion probability"),
    ("dev_sigma",        "deviation in stationary sigma"),
    ("regime",           "volatility regime"),
    ("theta_p",          "theta significance p"),
    ("p_value",          "cointegration p-value"),
    ("age_days",         "days since pair detected"),
    ("sigma_stationary", "stationary sigma"),
]


def topk_vs_random(df, col, ascending, k, n_rand=200, seed=0):
    """Mean realised net for the top-k by `col` each day, and for random k."""
    rng = np.random.default_rng(seed)
    sel, rnd = [], []
    for _, g in df.groupby("date"):
        g = g[np.isfinite(g[col])]
        if len(g) < k + 1:
            continue
        order = g.sort_values(col, ascending=ascending)
        sel.append(order.net_pct.to_numpy()[:k].mean())
        vals = g.net_pct.to_numpy()
        rnd.append(np.mean([rng.choice(vals, k, replace=False).mean()
                            for _ in range(n_rand // 20)]))
    if not sel:
        return np.nan, np.nan, 0
    return float(np.mean(sel)), float(np.mean(rnd)), len(sel)


def main():
    d = rs.load()
    dates = np.sort(d.date.unique())
    split = dates[int(len(dates) * 0.6)]
    mk = lambda x: x[x.absz >= ENTRY]

    def make(lo, hi):
        sub = d[(d.date >= lo) & (d.date < hi)] if hi is not None else d[d.date >= lo]
        sub = mk(sub).copy()
        net, xb, win, sp = rs.outcome(sub, TP, STOP, HOR)
        sub["net_pct"], sub["exit_bar"], sub["win"], sub["stop_pct"] = net, xb, win, sp
        return sub

    tr = make(dates[0], split)
    te = make(split, None)
    print(f"entry {ENTRY} sigma | tp {TP} | stop {STOP} | {HOR}h | take top {SLOTS}/day")
    print(f"train {len(tr):,} candidates over {tr.date.nunique()} days | "
          f"test {len(te):,} over {te.date.nunique()} days\n")

    print("=" * 104)
    print("DOES ANY FEATURE BEAT RANDOM SELECTION?   (mean net % of notional on the chosen trades)")
    print("=" * 104)
    print("%-34s%-9s%10s%10s%9s%10s%10s%9s"
          % ("rank candidates by", "take", "TRAIN sel", "TRAIN rnd", "edge",
             "TEST sel", "TEST rnd", "edge"))
    print("-" * 104)

    out = []
    for col, label in FEATURES:
        if col not in te.columns:
            continue
        for asc, tag in [(False, "highest"), (True, "lowest")]:
            s_tr, r_tr, _ = topk_vs_random(tr, col, asc, SLOTS)
            s_te, r_te, _ = topk_vs_random(te, col, asc, SLOTS)
            if not np.isfinite(s_tr) or not np.isfinite(s_te):
                continue
            e_tr, e_te = s_tr - r_tr, s_te - r_te
            out.append((label, tag, e_tr, e_te, s_te))
            flag = "  <-" if (e_tr > 0 and e_te > 0) else ""
            print("%-34s%-9s%+10.3f%+10.3f%+9.3f%+10.3f%+10.3f%+9.3f%s"
                  % (label, tag, s_tr, r_tr, e_tr, s_te, r_te, e_te, flag))

    print("\n" + "=" * 104)
    print("FEATURES THAT BEAT RANDOM ON BOTH SPLITS  (the only ones worth trusting)")
    print("=" * 104)
    both = [o for o in out if o[2] > 0 and o[3] > 0]
    if not both:
        print("  none. Random selection is not beaten by any single feature on both splits.")
    else:
        for label, tag, e_tr, e_te, s_te in sorted(both, key=lambda o: -o[3]):
            print("  %-34s %-8s train %+0.3f  test %+0.3f  (chosen trades net %+0.3f%%)"
                  % (label, tag, e_tr, e_te, s_te))


if __name__ == "__main__":
    main()
