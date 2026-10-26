"""CHOP-DRIFT: is the sign-flip gap drift away from mu, or chop?

    OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 .venv/bin/python -u \
        research/dislocation_model/chopdrift.py > research/dislocation_model/logs/chopdrift.log 2>&1

The user's decision (NUMBERS.md, DECISIONS): record chop versus drift as a small
measurement, a sign-flip null on 5-minute and 30-minute steps.

THE QUESTION. Real dislocations reach mu within 10h less often than the same
1-minute steps with random signs (23% vs 30%). Two explanations predict that:
  DRIFT  the path's expected move goes away from mu.
  CHOP   successive steps cancel (negative autocorrelation), so the path covers
         less net distance than its own steps would with independent signs.
Flipping signs destroys BOTH. Coarser steps separate them: summing 1-minute
steps into 5- or 30-minute blocks absorbs short-range cancellation inside
each block, so under CHOP the real-minus-flipped gap shrinks as blocks grow;
under pure DRIFT it does not, and the mean move is away from mu.

DATA. The matched 53,757; the folded move toward mu from t0's close, minutes
0..600 (reachmu's path: mu and sigma frozen at t0; need = |z at t0|). Missing
minutes are bridged by carrying the last traded value forward (whyscreen's
bridging). For block size B in {1, 5, 30} minutes the path is read at minutes
0, B, 2B, ..., 600; its increments are the B-minute steps.
  real reach_B   max over the grid points >= need (the same grid the null sees,
                 so sampling is matched; at B = 1 it equals the saved target
                 up to the bridging, reported)
  chance_B       each episode's B-minute increments get random signs, 50 seeds
                 (1000..1049); the share of flipped paths reaching need
  gap_B          real reach_B - chance_B, mean over episodes
  VR_B           mean(final^2) / mean(sum of squared B-minute steps): 1 for
                 independent steps, below 1 when steps cancel
  final          the move toward mu at minute 600 (sigma units); its mean is
                 the drift
Day-clustered 95% intervals (envelope.day_boot, 300 resamples). Shown for all
rows and for train, val, HO1 and HO2.

READING RULES (fixed before the run; on ALL 53,757; "clears" = the 95% interval
excludes the reference). Each is read separately; both, one or neither may hold.
  DRIFT AWAY     mean final move toward mu has its interval wholly below 0.
  DRIFT TOWARD   wholly above 0.
  CHOP           VR_1 has its interval wholly below 1, AND the gap shrinks
                 toward zero with coarser steps: gap_30 - gap_1 has its
                 interval wholly above 0 (gap_1 being negative).
  If the 30-minute gap's interval still lies wholly below 0, some of the
  shortfall survives 30-minute aggregation, and that is reported as such.
No model, no target change. Nothing written to the registry or the live system.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd

import harness
from envelope import HO_BOUNDARY, day_boot, load_1m_series, one_min_paths
from reachmu import PATHS_OUT, population

BLOCKS = (1, 5, 30)
SEEDS = range(1000, 1050)


def main():
    t0 = time.time()
    Y, meta, rows = population()
    PZ = np.load(PATHS_OUT)
    e = Y[rows, 0]
    s = np.sign(e)
    s[s == 0] = 1.0
    need = np.abs(e)
    series = load_1m_series(sorted(set(meta.ticker_a.iloc[rows]) | set(meta.ticker_b.iloc[rows])), False)
    P, _ = one_min_paths(meta, rows, series)
    del series
    move = -(P - e[:, None]) * s[:, None]
    del P
    last = pd.DataFrame(move).ffill(axis=1).to_numpy()
    del move
    day = meta.day.to_numpy()[rows]
    sp = harness.Split(day, e)
    groups = {"ALL": np.ones(len(rows), bool), "train": sp.train, "val": sp.val,
              "HO1": sp.test & (day < HO_BOUNDARY), "HO2": sp.test & (day >= HO_BOUNDARY)}
    print("=" * 112)
    print("CHOP-DRIFT -- sign-flip null on 1-, 5- and 30-minute steps")
    print("=" * 112)
    print(f"  {len(rows):,} episodes; path read at t0 close + 0..600 min; missing minutes bridged forward")
    if not np.isfinite(last[:, 0]).all():
        raise SystemExit("[CHOP] the t0 close is missing on some rows.")
    final = last[:, 600]
    res = {}
    for B in BLOCKS:
        G = last[:, ::B]                                 # minutes 0, B, ..., 600
        inc = np.diff(G, axis=1)
        real = np.nanmax(G[:, 1:], 1) >= need
        hits = np.zeros(len(rows))
        for sd in SEEDS:
            sg = np.random.default_rng(sd).choice([-1.0, 1.0], size=inc.shape)
            pth = np.cumsum(sg * inc, axis=1)
            hits += np.nanmax(pth, 1) >= need
        chance = hits / len(SEEDS)
        res[B] = dict(real=real.astype(float), chance=chance, ss=(inc ** 2).sum(1))
        agree = np.mean(real == PZ["reach"]) if B == 1 else np.nan
        print(f"  B={B:>2} min: {inc.shape[1]} steps; real reach {real.mean():.4f}; chance {chance.mean():.4f}"
              + (f"; agreement with the saved target {agree:.4f}" if B == 1 else "") + f"   [{time.time()-t0:.0f}s]",
              flush=True)
    print()
    print(f"  {'group':<6}{'n':>7}  {'mean final move toward mu [95%]':>34}"
          + "".join(f"{f'B={B}: real / chance / gap [95%]':>44}" for B in BLOCKS)
          + "".join(f"{f'VR_{B} [95%]':>24}" for B in BLOCKS))
    R = {}
    for g, m in groups.items():
        ix = np.flatnonzero(m)
        bt = day_boot(day[ix])
        f_ = final[ix]
        mf = (np.nanmean(f_), *np.percentile([np.nanmean(f_[i]) for i in bt], [2.5, 97.5]))
        cells, vrs = [], []
        out = {"final": mf}
        for B in BLOCKS:
            r = res[B]
            gp = r["real"][ix] - r["chance"][ix]
            gci = np.percentile([gp[i].mean() for i in bt], [2.5, 97.5])
            vr = np.nanmean(f_ ** 2) / r["ss"][ix].mean()
            vci = np.percentile([np.nanmean(f_[i] ** 2) / r["ss"][ix][i].mean() for i in bt], [2.5, 97.5])
            out[B] = dict(gap=(gp.mean(), *gci), vr=(vr, *vci))
            cells.append(f"{r['real'][ix].mean():.4f} / {r['chance'][ix].mean():.4f} / {gp.mean():+.4f} "
                         f"[{gci[0]:+.4f},{gci[1]:+.4f}]")
            vrs.append(f"{vr:.3f} [{vci[0]:.3f},{vci[1]:.3f}]")
        d30 = res[30]["real"][ix] - res[30]["chance"][ix] - (res[1]["real"][ix] - res[1]["chance"][ix])
        out["d30_1"] = (d30.mean(), *np.percentile([d30[i].mean() for i in bt], [2.5, 97.5]))
        R[g] = out
        print(f"  {g:<6}{len(ix):>7,}  {f'{mf[0]:+.4f} [{mf[1]:+.4f},{mf[2]:+.4f}]':>34}"
              + "".join(f"{c:>44}" for c in cells) + "".join(f"{v:>24}" for v in vrs))
    print()
    print("  gap_30 - gap_1 (paired, + = the shortfall shrinks with 30-minute steps):")
    for g, out in R.items():
        d_ = out["d30_1"]
        print(f"    {g:<6} {d_[0]:+.4f} [{d_[1]:+.4f}, {d_[2]:+.4f}]")
    A = R["ALL"]
    print()
    print("  READING RULES (all 53,757)")
    print(f"    DRIFT AWAY (mean final move wholly < 0):   {'YES' if A['final'][2] < 0 else 'NO'}")
    print(f"    DRIFT TOWARD (wholly > 0):                 {'YES' if A['final'][1] > 0 else 'NO'}")
    chop = A[1]["vr"][2] < 1 and A["d30_1"][1] > 0
    print(f"    CHOP (VR_1 wholly < 1 AND gap_30 - gap_1 wholly > 0): {'YES' if chop else 'NO'}   "
          f"(VR_1 upper {A[1]['vr'][2]:.3f}; gap_30 - gap_1 lower {A['d30_1'][1]:+.4f})")
    print(f"    shortfall surviving 30-minute steps (gap_30 wholly < 0): {'YES' if A[30]['gap'][2] < 0 else 'NO'}")
    print("  Nothing written to the registry or the live system.")
    print(f"  [{time.time()-t0:.0f}s]")
    print("=" * 112)


if __name__ == "__main__":
    main()
