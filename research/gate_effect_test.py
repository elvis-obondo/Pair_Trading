"""Does requiring MORE entry gates help? Exit rule held fixed.

run_risk_sweep's table D let every cell choose its own take-profit/stop/horizon
on its own training subset. Those subsets shrink fast -- 292k rows at zero gates
down to 408 at five -- so the later cells pick an exit rule from very little
data and the column stops being a gate comparison. The tell was 2-sigma, where
the win rate jumps from 3.9% at four gates to 37.6% at five: a different exit
rule, not a different filter.

Here the exit rule is chosen ONCE per entry threshold, on the zero-gate training
set (the largest, so the least overfit), then frozen across every gate count.
Only the gate requirement varies. A bootstrap CI on the per-trade mean says
whether any difference survives the shrinking sample.
"""
import sys
sys.path.insert(0,'/Users/elvisobondo/Pair_Trading/research')
import numpy as np
import risk_sim as rs

d = rs.load()
dates = np.sort(d.date.unique()); split = dates[int(len(dates)*0.6)]
rng = np.random.default_rng(0)

for thr in [1.0, 2.0, 3.0]:
    base = lambda x: x[(x.absz >= thr)]
    F, S, H = rs.pick_config(base(d[d.date < split]))
    print(f"\n{'='*104}")
    print(f"ENTRY {thr} sigma   |   exit rule frozen at tp{F} stop{S} {H}h "
          f"(chosen on the 0-gate train set)")
    print('='*104)
    print(f"{'gates':>6}{'n test':>9}{'per-trade':>11}{'95% CI':>22}{'win%':>7}"
          f"{'med x':>8}{'P(prof)':>9}{'sig?':>6}")
    print('-'*104)
    rows = []
    for k in range(6):
        mk = (lambda kk: (lambda x: x[(x.absz >= thr) & (x.n_gates >= kk)]))(k)
        te = rs.prep(d, split, mk, F, S, H, min_rows=40)
        if te is None:
            print(f"{k:>6}{'too few test rows':>30}"); continue
        n = te.net_pct.to_numpy()
        boot = np.array([rng.choice(n, len(n)).mean() for _ in range(400)])
        lo, hi = np.percentile(boot, [2.5, 97.5])
        f,_,_,_ = rs.simulate(te, 5, sizing="vol_frac", risk_frac=0.02, n_sims=250)
        sig = "yes" if (lo > 0 or hi < 0) else "no"
        print(f"{k:>6}{len(te):>9}{n.mean():>+11.3f}   [{lo:>+7.3f},{hi:>+7.3f}]"
              f"{te.win.mean()*100:>7.1f}{np.median(f):>8.2f}{np.mean(f>1)*100:>8.0f}%{sig:>6}")
        rows.append((k, n))
    # is 5 gates different from 0 gates?
    if len(rows) >= 2:
        k0, n0 = rows[0]; k5, n5 = rows[-1]
        diff = np.array([rng.choice(n5, len(n5)).mean() - rng.choice(n0, len(n0)).mean()
                         for _ in range(400)])
        l, h = np.percentile(diff, [2.5, 97.5])
        verdict = "gates HELP" if l > 0 else "gates HURT" if h < 0 else "no detectable effect"
        print(f"  {rows[-1][0]} gates minus 0 gates: {diff.mean():+.3f}pp  "
              f"CI [{l:+.3f},{h:+.3f}]  ->  {verdict}")
